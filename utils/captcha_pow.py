# language: Python, file: captcha_pow.py
"""
Proof-of-Work (PoW) Pure Python Captcha Engine.
Solves modern non-interactive/lightweight PoW captchas without external paid APIs or local ML models:
1. Altcha (SHA-256 / SHA-512)
2. Friendly Captcha v1/v2 (Blake2b-256)
3. Hashcash / Leading-zeros PoW

Zero-cost, ultra-fast CPython C-accelerated hashing (OpenSSL / hashlib).
"""

import time
import hashlib
import struct
import base64
import json
import re
from typing import Dict, Any, Optional, List


from html.parser import HTMLParser

SUPPORTED_ALTCHA_ALGORITHMS = {
    "SHA256": ("SHA-256", hashlib.sha256),
    "SHA-256": ("SHA-256", hashlib.sha256),
    "SHA512": ("SHA-512", hashlib.sha512),
    "SHA-512": ("SHA-512", hashlib.sha512),
}


def solve_altcha(
    challenge: str,
    salt: str,
    max_number: int = 1_000_000,
    algorithm: str = "SHA-256"
) -> Optional[Dict[str, Any]]:
    """
    Solves an Altcha PoW challenge:
    Finds integer `n` in [0, max_number] such that HASH(salt + str(n)) == challenge.
    BUG-004 fix: Explicit allowlist validation for supported algorithms.
    """
    if not isinstance(algorithm, str):
        return None

    algo_norm = algorithm.strip().upper()
    if algo_norm not in SUPPORTED_ALTCHA_ALGORITHMS:
        return None

    canonical_name, hasher_func = SUPPORTED_ALTCHA_ALGORITHMS[algo_norm]

    if not isinstance(challenge, str) or not isinstance(salt, str):
        return None
    if not isinstance(max_number, int) or isinstance(max_number, bool) or max_number < 0:
        return None

    t0 = time.perf_counter()
    salt_bytes = salt.encode("utf-8")
    challenge_lower = challenge.strip().lower()

    for n in range(max_number + 1):
        h = hasher_func(salt_bytes + str(n).encode("ascii")).hexdigest()
        if h == challenge_lower:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            hash_rate = int((n + 1) / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else 0
            return {
                "solution": n,
                "hashes_computed": n + 1,
                "elapsed_ms": round(elapsed_ms, 2),
                "hash_rate": hash_rate,
                "algorithm": canonical_name
            }
    return None


def create_altcha_payload(challenge_data: Dict[str, Any], solution_number: int) -> str:
    """
    Creates the base64-encoded JSON payload expected by the target form in the 'altcha' field.
    """
    payload = {
        "algorithm": challenge_data.get("algorithm", "SHA-256"),
        "challenge": challenge_data["challenge"],
        "number": solution_number,
        "salt": challenge_data.get("salt", ""),
        "signature": challenge_data.get("signature", "")
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def solve_friendly_captcha(
    puzzle: str,
    max_iterations: int = 2_000_000
) -> Optional[Dict[str, Any]]:
    """
    Solves a Friendly Captcha PoW puzzle (v1 specification).
    Wire format: '<signature>.<base64_puzzle_buffer>' or raw base64 buffer.
    Result token: '<signature>.<base64_puzzle>.<base64_solutions>.<base64_diagnostics>'
    
    Resolves:
    - BUG-002: Accurate offsets (byte 14 = num_solutions, byte 15 = difficulty).
    - BUG-003: Documented 4-field token with 3-byte diagnostics serialization.
    - BUG-005: Strict base64 and bounded v1 buffer length checks (must be 32 to 128 bytes).
    - BUG-007: Protocol version validation (rejects unsupported non-v1 buffers).
    """
    if not isinstance(puzzle, str) or not puzzle.strip():
        return None

    cleaned_puzzle = puzzle.strip()
    parts = cleaned_puzzle.split(".")

    if len(parts) == 2:
        sig, b64_buf = parts[0], parts[1]
    elif len(parts) == 1:
        sig, b64_buf = "", parts[0]
    else:
        return None

    if len(b64_buf) > 256 or len(b64_buf) < 16:
        return None

    rem = len(b64_buf) % 4
    if rem > 0:
        b64_buf += "=" * (4 - rem)

    try:
        raw_buf = base64.b64decode(b64_buf, validate=True)
    except Exception:
        return None

    if len(raw_buf) < 32 or len(raw_buf) > 128:
        return None

    version = raw_buf[12]
    if version != 1:
        return None

    num_solutions = raw_buf[14]
    difficulty = raw_buf[15]

    if num_solutions < 1:
        return None

    threshold = int(2.0 ** ((255.999 - difficulty) / 8.0))

    buf = bytearray(128)
    buf[:len(raw_buf)] = raw_buf

    t0 = time.perf_counter()
    solutions: List[int] = []
    total_hashes = 0
    nonce = 0

    for _ in range(num_solutions):
        found = False
        while nonce < max_iterations:
            total_hashes += 1
            buf[120:128] = struct.pack("<Q", nonce)
            digest = hashlib.blake2b(buf, digest_size=32).digest()
            val = struct.unpack("<I", digest[:4])[0]
            if val < threshold:
                solutions.append(nonce)
                nonce += 1
                found = True
                break
            nonce += 1
        if not found:
            return None

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    hash_rate = int(total_hashes / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else 0

    sol_bytes = b"".join(struct.pack("<Q", s) for s in solutions)
    sol_b64 = base64.b64encode(sol_bytes).decode("ascii").rstrip("=")

    t_sec = min(65535, int(elapsed_ms / 1000.0))
    diag_bytes = bytes([1, (t_sec >> 8) & 0xFF, t_sec & 0xFF])
    diag_b64 = base64.b64encode(diag_bytes).decode("ascii").rstrip("=")

    puzzle_clean_b64 = parts[1].rstrip("=") if len(parts) == 2 else parts[0].rstrip("=")
    if sig:
        response_token = f"{sig}.{puzzle_clean_b64}.{sol_b64}.{diag_b64}"
    else:
        response_token = f"{puzzle_clean_b64}.{sol_b64}.{diag_b64}"

    return {
        "solutions": solutions,
        "solution_token": response_token,
        "hashes_computed": total_hashes,
        "elapsed_ms": round(elapsed_ms, 2),
        "hash_rate": hash_rate
    }


def solve_hashcash(
    salt: str,
    required_zero_bits: int = 16,
    max_iterations: int = 2_000_000
) -> Optional[Dict[str, Any]]:
    """
    Solves generic Hashcash PoW (finding nonce where SHA-256(salt + nonce) has N leading zero bits).
    BUG-001 fix: Validates integer [0, 256] and checks exact leading bit count via integer comparison.
    """
    if not isinstance(required_zero_bits, int) or isinstance(required_zero_bits, bool):
        return None
    if required_zero_bits < 0 or required_zero_bits > 256:
        return None
    if not isinstance(salt, str):
        return None

    if required_zero_bits == 0:
        return {
            "nonce": 0,
            "hash": hashlib.sha256(salt.encode("utf-8") + b"0").hexdigest(),
            "hashes_computed": 1,
            "elapsed_ms": 0.0,
            "hash_rate": 0
        }

    t0 = time.perf_counter()
    salt_bytes = salt.encode("utf-8")
    target_threshold = 1 << (256 - required_zero_bits)

    for n in range(max_iterations):
        digest = hashlib.sha256(salt_bytes + str(n).encode("ascii")).digest()
        val = int.from_bytes(digest, byteorder="big")
        if val < target_threshold:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            hash_rate = int((n + 1) / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else 0
            return {
                "nonce": n,
                "hash": digest.hex(),
                "hashes_computed": n + 1,
                "elapsed_ms": round(elapsed_ms, 2),
                "hash_rate": hash_rate
            }
    return None


class _PoWDetectorParser(HTMLParser):
    """HTML Parser for robust attribute-order-independent detection (BUG-006)."""
    def __init__(self):
        super().__init__()
        self.found: Optional[Dict[str, str]] = None

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        if self.found:
            return
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag_lower in ("altcha-widget", "div"):
            c_url = attr_dict.get("challengeurl") or attr_dict.get("data-challengeurl")
            if c_url:
                self.found = {"type": "altcha", "challenge_url": c_url}
                return

        classes = attr_dict.get("class", "").split()
        if "frc-captcha" in classes:
            sitekey = attr_dict.get("data-sitekey")
            if sitekey:
                self.found = {"type": "friendly_captcha", "sitekey": sitekey}
                return


def detect_pow_type(html: str) -> Optional[Dict[str, str]]:
    """
    Inspects HTML for PoW captcha widgets (Altcha or Friendly Captcha).
    BUG-006 fix: Uses standard library HTMLParser for robust attribute ordering and token matching.
    """
    if not html or not isinstance(html, str):
        return None

    try:
        parser = _PoWDetectorParser()
        parser.feed(html)
        return parser.found
    except Exception:
        return None