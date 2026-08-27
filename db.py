"""
db.py — Supabase Postgres Persistence Layer for Freaky Checker Bot
"""

import os
import json
import time
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

DEFAULT_DB_URLS = [
    # 1. Supabase IPv4 Session Pooler (Port 5432 - fast & universal IPv4 compatibility)
    "postgresql://postgres.fgdgauxhlnwpvkpcpsmc:Suriya303%40303@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres",
    # 2. Supabase IPv4 Transaction Pooler (Port 6543)
    "postgresql://postgres.fgdgauxhlnwpvkpcpsmc:Suriya303%40303@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres",
    # 3. Supabase Direct Host (Port 5432)
    "postgresql://postgres:Suriya303%40303@db.fgdgauxhlnwpvkpcpsmc.supabase.co:5432/postgres",
]

def get_db_connection():
    candidate_urls = []
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        candidate_urls.append(env_url)
    
    for u in DEFAULT_DB_URLS:
        if u not in candidate_urls:
            candidate_urls.append(u)

    for db_url in candidate_urls:
        for ssl_mode in ["require", "prefer"]:
            try:
                conn = psycopg2.connect(db_url, connect_timeout=8, sslmode=ssl_mode)
                return conn
            except Exception as e:
                pass
    return None



# ==================== REGISTERED USERS ====================
def add_registered_user(user_id: int):
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO registered_users (user_id, registered_at)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING;
            """, (str(user_id), int(time.time())))
            conn.commit()
    except Exception as e:
        print(f"[Supabase DB Error] add_registered_user: {e}")
    finally:
        conn.close()

def get_all_registered_users() -> list[int]:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM registered_users;")
            rows = cur.fetchall()
            return sorted([int(r[0]) for r in rows if r[0].isdigit()])
    except Exception as e:
        print(f"[Supabase DB Error] get_all_registered_users: {e}")
        return []
    finally:
        conn.close()

# ==================== PREMIUM USERS ====================
def is_user_premium(user_id: int) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT expires FROM premium_users
                WHERE user_id = %s;
            """, (str(user_id),))
            row = cur.fetchone()
            if not row:
                return False
            expires = row[0]
            if expires == 0 or expires > int(time.time()):
                return True
            return False
    except Exception as e:
        print(f"[Supabase DB Error] is_user_premium: {e}")
        return False
    finally:
        conn.close()

def grant_premium_access(user_id: int, days: int) -> int:
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        now = int(time.time())
        current_exp = now
        with conn.cursor() as cur:
            cur.execute("SELECT expires FROM premium_users WHERE user_id = %s;", (str(user_id),))
            row = cur.fetchone()
            if row and row[0] > now:
                current_exp = row[0]
            new_exp = current_exp + (days * 86400)
            cur.execute("""
                INSERT INTO premium_users (user_id, expires, authorized_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET expires = EXCLUDED.expires, authorized_at = EXCLUDED.authorized_at;
            """, (str(user_id), new_exp, now))
            conn.commit()
            return new_exp
    except Exception as e:
        print(f"[Supabase DB Error] grant_premium_access: {e}")
        return 0
    finally:
        conn.close()

def get_premium_users_count() -> int:
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        now = int(time.time())
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM premium_users WHERE expires = 0 OR expires > %s;", (now,))
            row = cur.fetchone()
            return row[0] if row else 0
    except Exception as e:
        print(f"[Supabase DB Error] get_premium_users_count: {e}")
        return 0
    finally:
        conn.close()

# ==================== LICENSE KEYS ====================
def create_license_key(days: int = 1, max_uses: int = 1, created_by: int = 0, key_code: str = "") -> str:
    conn = get_db_connection()
    if not conn:
        return key_code
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO license_keys (key, days, created_by, created_at, max_uses, redeemed_by)
                VALUES (%s, %s, %s, %s, %s, '[]'::jsonb)
                ON CONFLICT (key) DO NOTHING;
            """, (key_code, days, created_by, int(time.time()), max_uses))
            conn.commit()
            return key_code
    except Exception as e:
        print(f"[Supabase DB Error] create_license_key: {e}")
        return key_code
    finally:
        conn.close()

def redeem_license_key(user_id: int, key_code: str) -> tuple[bool, str]:
    conn = get_db_connection()
    if not conn:
        return False, "Database unavailable!"
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM license_keys WHERE key = %s;", (key_code,))
            kinfo = cur.fetchone()
            if not kinfo:
                return False, "Invalid or expired key!"

            redeemed_by = kinfo.get("redeemed_by") or []
            if isinstance(redeemed_by, str):
                redeemed_by = json.loads(redeemed_by)

            if user_id in redeemed_by or str(user_id) in [str(x) for x in redeemed_by]:
                return False, "You already redeemed this key!"

            if len(redeemed_by) >= kinfo.get("max_uses", 1):
                return False, "Key maximum usages reached!"

            days = kinfo.get("days", 1)
            redeemed_by.append(user_id)

            cur.execute("""
                UPDATE license_keys
                SET redeemed_by = %s::jsonb
                WHERE key = %s;
            """, (json.dumps(redeemed_by), key_code))
            conn.commit()

        # Grant premium access in DB
        new_exp = grant_premium_access(user_id, days)
        exp_date_str = datetime.fromtimestamp(new_exp).strftime("%Y-%m-%d %H:%M:%S")
        return True, f"Key redeemed successfully! Granted {days} day(s) Premium access until {exp_date_str}."
    except Exception as e:
        print(f"[Supabase DB Error] redeem_license_key: {e}")
        return False, f"Key redeem error: {e}"
    finally:
        conn.close()

# ==================== USER ST SITES ====================
def get_db_user_stsites(user_id: int) -> list[str]:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sites FROM user_stsites WHERE user_id = %s;", (str(user_id),))
            row = cur.fetchone()
            if not row or not row[0]:
                return []
            sites = row[0]
            if isinstance(sites, str):
                sites = json.loads(sites)
            return sites
    except Exception as e:
        print(f"[Supabase DB Error] get_db_user_stsites: {e}")
        return []
    finally:
        conn.close()

def add_db_user_stsite(user_id: int, site: str):
    conn = get_db_connection()
    if not conn:
        return
    try:
        sites = get_db_user_stsites(user_id)
        if site not in sites:
            sites.append(site)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_stsites (user_id, sites)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (user_id) DO UPDATE
                SET sites = EXCLUDED.sites;
            """, (str(user_id), json.dumps(sites)))
            conn.commit()
    except Exception as e:
        print(f"[Supabase DB Error] add_db_user_stsite: {e}")
    finally:
        conn.close()

def remove_db_user_stsite(user_id: int, site: str) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        sites = get_db_user_stsites(user_id)
        if site in sites:
            sites.remove(site)
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE user_stsites
                    SET sites = %s::jsonb
                    WHERE user_id = %s;
                """, (json.dumps(sites), str(user_id)))
                conn.commit()
                return True
        return False
    except Exception as e:
        print(f"[Supabase DB Error] remove_db_user_stsite: {e}")
        return False
    finally:
        conn.close()

# ==================== DAILY USAGE ====================
def get_db_daily_usage(user_id: int) -> dict:
    conn = get_db_connection()
    today = datetime.now().date().isoformat()
    if not conn:
        return {"cc_count": 0, "date": today}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT cc_count, usage_date FROM daily_usage WHERE user_id = %s;", (str(user_id),))
            row = cur.fetchone()
            if not row or row[1] != today:
                return {"cc_count": 0, "date": today}
            return {"cc_count": row[0], "date": row[1]}
    except Exception as e:
        print(f"[Supabase DB Error] get_db_daily_usage: {e}")
        return {"cc_count": 0, "date": today}
    finally:
        conn.close()

def update_db_daily_usage(user_id: int, cc_count=1):
    conn = get_db_connection()
    today = datetime.now().date().isoformat()
    if not conn:
        return
    try:
        current = get_db_daily_usage(user_id)
        new_count = current["cc_count"] + cc_count
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO daily_usage (user_id, cc_count, usage_date)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET cc_count = %s, usage_date = %s;
            """, (str(user_id), new_count, today, new_count, today))
            conn.commit()
    except Exception as e:
        print(f"[Supabase DB Error] update_db_daily_usage: {e}")
    finally:
        conn.close()


# ==================== PER-USER PROXIES (FREAKYHITTER ARCHITECTURE + CACHE) ====================
USER_PROXIES_CACHE: dict[str, list[str]] = {}

def save_db_user_proxies(user_id: int, proxies: list[str]) -> bool:
    uid = str(user_id)
    USER_PROXIES_CACHE[uid] = list(proxies)

    conn = get_db_connection()
    if not conn:
        return False
    try:
        now = int(time.time())
        data = json.dumps(proxies)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_proxies (user_id, proxies, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET proxies = EXCLUDED.proxies, updated_at = EXCLUDED.updated_at;
            """, (uid, data, now))
            conn.commit()
            return True
    except Exception as e:
        print(f"[Supabase DB Error] save_db_user_proxies: {e}")
        return False
    finally:
        conn.close()


def get_db_user_proxies(user_id: int) -> list[str]:
    uid = str(user_id)
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT proxies FROM user_proxies WHERE user_id = %s;", (uid,))
                row = cur.fetchone()
                if row and row[0]:
                    res = json.loads(row[0])
                    USER_PROXIES_CACHE[uid] = res
                    return res
        except Exception as e:
            print(f"[Supabase DB Error] get_db_user_proxies: {e}")
        finally:
            conn.close()

    return USER_PROXIES_CACHE.get(uid, [])


def add_db_user_proxies(user_id: int, new_proxies: list[str]) -> tuple[int, int]:
    existing = get_db_user_proxies(user_id)
    existing_set = set(existing)
    truly_new = []
    duplicates = 0

    for p in new_proxies:
        p_clean = p.strip()
        if not p_clean:
            continue
        if p_clean in existing_set:
            duplicates += 1
        else:
            truly_new.append(p_clean)
            existing_set.add(p_clean)

    if truly_new:
        updated_list = existing + truly_new
        save_db_user_proxies(user_id, updated_list)

    return (len(truly_new), duplicates)


def remove_db_user_proxy(user_id: int, proxy_url: str) -> bool:
    existing = get_db_user_proxies(user_id)
    target = proxy_url.strip()
    new_list = [p for p in existing if p != target and target not in p]
    if len(new_list) != len(existing):
        save_db_user_proxies(user_id, new_list)
        return True
    return False


def sync_db_user_proxies(user_id: int, alive_proxies: list[str]):
    save_db_user_proxies(user_id, alive_proxies)


# ==================== PER-USER SHOPIFY SITES (SUPABASE DB + CACHE) ====================
USER_SITES_CACHE: dict[str, list[str]] = {}

def save_db_user_sites(user_id: int, sites: list[str]) -> bool:
    uid = str(user_id)
    USER_SITES_CACHE[uid] = list(sites)

    conn = get_db_connection()
    if not conn:
        return False
    try:
        now = int(time.time())
        data = json.dumps(sites)
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_sites (
                    user_id TEXT PRIMARY KEY,
                    sites JSONB,
                    updated_at BIGINT
                );
            """)
            cur.execute("""
                INSERT INTO user_sites (user_id, sites, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET sites = EXCLUDED.sites, updated_at = EXCLUDED.updated_at;
            """, (uid, data, now))
            conn.commit()
            return True
    except Exception as e:
        print(f"[Supabase DB Error] save_db_user_sites: {e}")
        return False
    finally:
        conn.close()


def get_db_user_sites(user_id: int) -> list[str]:
    uid = str(user_id)
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_sites (
                        user_id TEXT PRIMARY KEY,
                        sites JSONB,
                        updated_at BIGINT
                    );
                """)
                conn.commit()
                cur.execute("SELECT sites FROM user_sites WHERE user_id = %s;", (uid,))
                row = cur.fetchone()
                if row and row[0] is not None:
                    res = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    if isinstance(res, list):
                        USER_SITES_CACHE[uid] = list(res)
                        return list(res)
        except Exception as e:
            print(f"[Supabase DB Error] get_db_user_sites: {e}")
        finally:
            conn.close()

    return USER_SITES_CACHE.get(uid, [])


def add_db_user_sites(user_id: int, new_sites: list[str]) -> int:
    uid = str(user_id)
    existing = get_db_user_sites(user_id)
    existing_set = set(existing)
    truly_new = []

    for s in new_sites:
        s_clean = s.strip()
        if not s_clean:
            continue
        if s_clean not in existing_set:
            truly_new.append(s_clean)
            existing_set.add(s_clean)

    if truly_new:
        updated_list = existing + truly_new
        USER_SITES_CACHE[uid] = updated_list
        save_db_user_sites(user_id, updated_list)

    return len(truly_new)


def remove_db_user_site(user_id: int, site: str) -> bool:
    existing = get_db_user_sites(user_id)
    target = site.strip()
    new_list = [s for s in existing if s != target and target not in s]
    if len(new_list) != len(existing):
        save_db_user_sites(user_id, new_list)
        return True
    return False


def clear_db_user_sites(user_id: int):
    save_db_user_sites(user_id, [])







