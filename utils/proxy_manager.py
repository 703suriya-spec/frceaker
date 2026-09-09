"""
Dynamic Proxy Pool Health Manager
Provides asynchronous proxy validation, sticky domain pinning, latency sorting, and dead node ejection.
"""
import os
import json
import time
import random
import asyncio
from pathlib import Path
from curl_cffi.requests import AsyncSession

HEALTH_FILE = Path(__file__).parent.parent / "data" / "proxy_health.json"
PROBE_URL = "https://api.ipify.org/?format=json"

def _format_proxy_url(p: str) -> str:
    ps = p.strip()
    if ps.startswith(("http://", "https://", "socks5://", "socks4://", "socks5h://", "socks4a://")):
        return ps
    parts = ps.split(":")
    if len(parts) == 4:
        if parts[1].isdigit():
            return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif parts[3].isdigit():
            return f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
    elif len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    return f"http://{ps}"

class ProxyManager:
    """Manages proxy validation, latency health tracking, and sticky session domain binding."""
    def __init__(self, raw_proxies: list[str] | None = None):
        self.entries: list[dict] = []
        seen = set()
        for p in raw_proxies or []:
            formatted = _format_proxy_url(p)
            if formatted and formatted not in seen:
                seen.add(formatted)
                self.entries.append({
                    "url": formatted,
                    "alive": True,
                    "latency_ms": None,
                    "fail_count": 0,
                    "last_check": 0
                })
        self._sticky: dict[str, str] = {}
        self._load_health()

    def _load_health(self):
        if HEALTH_FILE.exists():
            try:
                with open(HEALTH_FILE, "r", encoding="utf-8") as f:
                    saved = {h["url"]: h for h in json.load(f) if isinstance(h, dict) and "url" in h}
                for e in self.entries:
                    h = saved.get(e["url"])
                    if h:
                        e.update({k: h[k] for k in ("latency_ms", "fail_count", "alive") if k in h})
            except Exception:
                pass

    def _save_health(self):
        try:
            HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(HEALTH_FILE, "w", encoding="utf-8") as f:
                json.dump([
                    {k: e[k] for k in ("url", "alive", "latency_ms", "fail_count", "last_check")}
                    for e in self.entries
                ], f, indent=2)
        except Exception:
            pass

    async def _probe_node(self, entry: dict, sem: asyncio.Semaphore):
        async with sem:
            t0 = time.perf_counter()
            try:
                async with AsyncSession(impersonate="chrome124", verify=False, proxy=entry["url"]) as s:
                    r = await s.get(PROBE_URL, timeout=4)
                    ok = r.status_code == 200
            except Exception:
                ok = False

            lat = int((time.perf_counter() - t0) * 1000)
            entry["last_check"] = int(time.time())
            if ok:
                entry["alive"] = True
                entry["latency_ms"] = lat
                entry["fail_count"] = 0
            else:
                entry["alive"] = False
                entry["fail_count"] += 1

    async def validate_all(self, concurrency: int = 50) -> tuple[int, int]:
        total = len(self.entries)
        if total == 0:
            return 0, 0
        sem = asyncio.Semaphore(concurrency)
        await asyncio.gather(*[self._probe_node(e, sem) for e in self.entries])
        self._save_health()
        alive = sum(1 for e in self.entries if e["alive"])
        return alive, total

    def pick(self, sticky_key: str | None = None) -> str | None:
        alive = [e for e in self.entries if e.get("alive") is True and e.get("fail_count", 0) < 3]
        if not alive:
            return None

        if sticky_key and sticky_key in self._sticky:
            st_url = self._sticky[sticky_key]
            if any(e["url"] == st_url for e in alive):
                return st_url
            self._sticky.pop(sticky_key, None)

        # Sort by lowest latency
        sorted_alive = sorted(alive, key=lambda x: x.get("latency_ms") or 9999)
        top_tier = sorted_alive[:max(5, int(len(sorted_alive) * 0.3))]
        chosen = random.choice(top_tier)

        if sticky_key:
            self._sticky[sticky_key] = chosen["url"]
        return chosen["url"]

    def mark_bad(self, proxy_url: str | None):
        if not proxy_url:
            return
        for e in self.entries:
            if e["url"] == proxy_url:
                e["fail_count"] += 1
                if e["fail_count"] >= 3:
                    e["alive"] = False
                    for k, v in list(self._sticky.items()):
                        if v == proxy_url:
                            self._sticky.pop(k, None)
        self._save_health()
