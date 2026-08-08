# Additional ported mass checkers and helper routines for Telethon
import os
import re
import json
import time
import random
import asyncio
import aiofiles
import string
import aiohttp
from telethon import events, Button

SKKEYS_FILE = os.path.join(os.path.dirname(__file__), "skkeys.json")
STSITE_FILE = os.path.join(os.path.dirname(__file__), "stsite.json")

def get_user_sk(user_id: int):
    if os.path.exists(SKKEYS_FILE):
        try:
            with open(SKKEYS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(str(user_id))
        except Exception:
            pass
    return None

def save_user_sk(user_id: int, sk: str, pk: str):
    data = {}
    if os.path.exists(SKKEYS_FILE):
        try:
            with open(SKKEYS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[str(user_id)] = {"sk": sk, "pk": pk}
    with open(SKKEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_user_stsites(user_id: int):
    if os.path.exists(STSITE_FILE):
        try:
            with open(STSITE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(str(user_id), [])
        except Exception:
            pass
    return []

def add_user_stsite(user_id: int, site: str):
    data = {}
    if os.path.exists(STSITE_FILE):
        try:
            with open(STSITE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    sites = data.get(str(user_id), [])
    if site not in sites:
        sites.append(site)
    data[str(user_id)] = sites
    with open(STSITE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def remove_user_stsite(user_id: int, site: str):
    if os.path.exists(STSITE_FILE):
        try:
            with open(STSITE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            sites = data.get(str(user_id), [])
            if site in sites:
                sites.remove(site)
                data[str(user_id)] = sites
                with open(STSITE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                return True
        except Exception:
            pass
    return False

# ==================== LICENSE KEYS & PREMIUM ACCESS ====================
KEYS_FILE = os.path.join(os.path.dirname(__file__), "keys.json")
PREMIUM_FILE = os.path.join(os.path.dirname(__file__), "premium.json")

def generate_key(days: int = 1, max_uses: int = 1, created_by: int = 0) -> str:
    data = {}
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    
    charset = string.ascii_uppercase + string.digits
    rand_part = "".join(random.choices(charset, k=16))
    key = f"FREAKY-{rand_part}"
    
    data[key] = {
        "days": days,
        "created_by": created_by,
        "created_at": int(time.time()),
        "max_uses": max_uses,
        "redeemed_by": []
    }
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return key

def redeem_key(user_id: int, key: str) -> tuple[bool, str]:
    if not os.path.exists(KEYS_FILE):
        return False, "Key not found!"
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys_data = json.load(f)
    except Exception:
        return False, "Key system error!"

    if key not in keys_data:
        return False, "Invalid or expired key!"

    kinfo = keys_data[key]
    redeemed_by = kinfo.get("redeemed_by", [])
    if user_id in redeemed_by:
        return False, "You already redeemed this key!"

    if len(redeemed_by) >= kinfo.get("max_uses", 1):
        return False, "Key maximum usages reached!"

    days = kinfo.get("days", 1)
    redeemed_by.append(user_id)
    kinfo["redeemed_by"] = redeemed_by
    keys_data[key] = kinfo

    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(keys_data, f, indent=2)

    # Grant premium access in premium.json
    pdata = {}
    if os.path.exists(PREMIUM_FILE):
        try:
            with open(PREMIUM_FILE, "r", encoding="utf-8") as f:
                pdata = json.load(f)
        except Exception:
            pdata = {}

    current_exp = pdata.get(str(user_id), {}).get("expires", int(time.time()))
    base_time = max(current_exp, int(time.time()))
    new_exp = base_time + (days * 86400)

    pdata[str(user_id)] = {
        "expires": new_exp,
        "authorized_at": int(time.time()),
        "key_used": key
    }

    with open(PREMIUM_FILE, "w", encoding="utf-8") as f:
        json.dump(pdata, f, indent=2)

    return True, f"Key redeemed successfully! Granted {days} day(s) Premium access."

# ==================== BATCH MERCHANT SITE TESTING ====================
async def test_merchant_site(url: str) -> tuple[bool, str]:
    if not url.startswith("http"):
        url = "https://" + url
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, ssl=False) as resp:
                if resp.status < 400:
                    return True, f"HTTP {resp.status} - Active"
                return False, f"HTTP {resp.status} - Inactive"
    except Exception as e:
        return False, str(e)[:60]

# ==================== CC CLEANER & FILTER UTILITY ====================
def extract_and_clean_ccs(text: str) -> list[str]:
    pattern = r'\b(\d{15,16})[|/:,\s]+(\d{1,2})[|/:,\s]+(\d{2,4})[|/:,\s]+(\d{3,4})\b'
    matches = re.findall(pattern, text)
    cleaned = []
    seen = set()
    for cc, mm, yy, cvc in matches:
        mm = mm.zfill(2)
        if len(yy) == 2:
            yy = f"20{yy}"
        card_str = f"{cc}|{mm}|{yy}|{cvc}"
        if card_str not in seen:
            seen.add(card_str)
            cleaned.append(card_str)
    return cleaned

def filter_ccs_by_brand(ccs: list[str], brand_filter: str) -> list[str]:
    brand_filter = brand_filter.lower().strip()
    filtered = []
    for card in ccs:
        bin_num = card.split("|")[0]
        first_digit = bin_num[0]
        if brand_filter in ("visa", "v") and first_digit == "4":
            filtered.append(card)
        elif brand_filter in ("mastercard", "mc", "m") and first_digit in ("5", "2"):
            filtered.append(card)
        elif brand_filter in ("amex", "american express", "a") and bin_num[:2] in ("34", "37"):
            filtered.append(card)
        elif brand_filter in ("discover", "d") and bin_num[:2] in ("60", "65"):
            filtered.append(card)
    return filtered

# ==================== SYSTEM ANALYTICS & STATS ====================
USERS_FILE = os.path.join(os.path.dirname(__file__), "users.txt")

def get_all_user_ids() -> list[int]:
    users = set()
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.isdigit():
                        users.add(int(line))
        except Exception:
            pass
    return sorted(list(users))

def get_system_telemetry() -> dict:
    all_users = get_all_user_ids()
    total_users = len(all_users)
    
    premium_count = 0
    if os.path.exists(PREMIUM_FILE):
        try:
            with open(PREMIUM_FILE, "r", encoding="utf-8") as f:
                pdata = json.load(f)
                now = time.time()
                for uid, info in pdata.items():
                    exp = info.get("expires", 0)
                    if exp == 0 or exp > now:
                        premium_count += 1
        except Exception:
            pass

    proxy_file = os.path.join(os.path.dirname(__file__), "proxy.json")
    proxy_count = 0
    if os.path.exists(proxy_file):
        try:
            with open(proxy_file, "r", encoding="utf-8") as f:
                pdata = json.load(f)
                if isinstance(pdata, list):
                    proxy_count = len(pdata)
        except Exception:
            pass

    return {
        "total_users": total_users,
        "premium_users": premium_count,
        "proxy_count": proxy_count,
    }


