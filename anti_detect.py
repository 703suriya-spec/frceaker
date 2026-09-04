"""
Anti-Detection & TLS Fingerprint Synchronization Engine for Alone Checker Bot.

Synchronizes TLS Client Hello (JA3/JA4) with L7 HTTP headers (User-Agent,
sec-ch-ua, sec-ch-ua-mobile, sec-ch-ua-platform) to prevent bot detection
and WAF filtering (Cloudflare, Akamai, DataDome, Stripe Radar).
"""

from typing import Dict, Any, Optional
from curl_cffi.requests import AsyncSession

# Locked Profiles: TLS Stack <-> HTTP Header Mapping
PROFILES = {
    "chrome124": {
        "impersonate": "chrome124",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec_ch_ua_mobile": "?0",
        "sec_ch_ua_platform": '"Windows"',
    },
    "chrome120": {
        "impersonate": "chrome120",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec_ch_ua_mobile": "?0",
        "sec_ch_ua_platform": '"Windows"',
    },
}

DEFAULT_PROFILE = "chrome124"


def get_profile(name: str = DEFAULT_PROFILE) -> Dict[str, str]:
    """Return the synchronized browser identity."""
    return PROFILES.get(name, PROFILES[DEFAULT_PROFILE])


def get_browser_headers(profile_name: str = DEFAULT_PROFILE, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Generate HTTP headers that strictly match the TLS impersonation target.
    Prevents JA4 vs User-Agent mismatch flags.
    """
    prof = get_profile(profile_name)
    headers = {
        "User-Agent": prof["user_agent"],
        "sec-ch-ua": prof["sec_ch_ua"],
        "sec-ch-ua-mobile": prof["sec_ch_ua_mobile"],
        "sec-ch-ua-platform": prof["sec_ch_ua_platform"],
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }
    if additional_headers:
        headers.update(additional_headers)
    return headers


def create_anti_detect_session(
    profile_name: str = DEFAULT_PROFILE,
    proxy: Optional[str] = None,
    timeout: int = 30
) -> AsyncSession:
    """
    Instantiate a curl_cffi AsyncSession with 100% matched TLS & L7 fingerprints.
    """
    prof = get_profile(profile_name)
    proxies = {"http": proxy, "https": proxy} if proxy else None
    
    session = AsyncSession(
        impersonate=prof["impersonate"],
        timeout=timeout,
        proxies=proxies,
        headers=get_browser_headers(profile_name)
    )
    return session
