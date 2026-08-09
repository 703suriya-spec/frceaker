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
    try:
        from db import get_db_user_stsites
        return get_db_user_stsites(user_id)
    except Exception:
        return []

def add_user_stsite(user_id: int, site: str):
    try:
        from db import add_db_user_stsite
        add_db_user_stsite(user_id, site)
    except Exception as e:
        print(f"add_user_stsite error: {e}")

def remove_user_stsite(user_id: int, site: str):
    try:
        from db import remove_db_user_stsite
        return remove_db_user_stsite(user_id, site)
    except Exception:
        return False


# ==================== LICENSE KEYS & PREMIUM ACCESS ====================
KEYS_FILE = os.path.join(os.path.dirname(__file__), "keys.json")
PREMIUM_FILE = os.path.join(os.path.dirname(__file__), "premium.json")

def generate_key(days: int = 1, max_uses: int = 1, created_by: int = 0) -> str:
    charset = string.ascii_uppercase + string.digits
    rand_part = "".join(random.choices(charset, k=16))
    key = f"FREAKY-{rand_part}"
    
    try:
        from db import create_license_key
        return create_license_key(days=days, max_uses=max_uses, created_by=created_by, key_code=key)
    except Exception as e:
        print(f"Generate key error: {e}")
        return key

def redeem_key(user_id: int, key: str) -> tuple[bool, str]:
    try:
        from db import redeem_license_key
        return redeem_license_key(user_id, key)
    except Exception as e:
        return False, f"Key system error: {e}"


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
    try:
        from db import get_all_registered_users
        return get_all_registered_users()
    except Exception:
        return []

def get_system_telemetry() -> dict:
    all_users = get_all_user_ids()
    total_users = len(all_users)
    
    premium_count = 0
    try:
        from db import get_premium_users_count
        premium_count = get_premium_users_count()
    except Exception:
        pass

    proxy_count = 0
    env_list = os.getenv("PROXY_LIST", "").strip()
    if env_list:
        proxy_count = len([p for p in env_list.split(",") if p.strip()])
    elif os.path.exists(PROXY_FILE):
        try:
            with open(PROXY_FILE, "r", encoding="utf-8") as f:
                proxy_count = len([line for line in f if line.strip()])
        except Exception:
            pass

    return {
        "total_users": total_users,
        "premium_users": premium_count,
        "proxy_count": proxy_count,
    }



