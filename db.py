"""
db.py — Supabase Postgres Persistence Layer for Freaky Checker Bot
"""

import os
import json
import time
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:Suriya303%40303@db.fgdgauxhlnwpvkpcpsmc.supabase.co:5432/postgres"
)

def get_db_connection():
    for attempt in range(3):
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10, sslmode="prefer")
            return conn
        except Exception as e:
            print(f"[Supabase DB Error] Connection attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(0.5)
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

# ==================== RAZORPAY SITES ====================
def add_db_rz_site(site_url: str):
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO rz_sites (site_url, added_at)
                VALUES (%s, %s)
                ON CONFLICT (site_url) DO NOTHING;
            """, (site_url, int(time.time())))
            conn.commit()
    except Exception as e:
        print(f"[Supabase DB Error] add_db_rz_site: {e}")
    finally:
        conn.close()

def get_db_rz_sites() -> list[str]:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT site_url FROM rz_sites ORDER BY added_at DESC;")
            rows = cur.fetchall()
            return [r[0] for r in rows]
    except Exception as e:
        print(f"[Supabase DB Error] get_db_rz_sites: {e}")
        return []
    finally:
        conn.close()

def remove_db_rz_site(site_url: str) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rz_sites WHERE site_url = %s;", (site_url,))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        print(f"[Supabase DB Error] remove_db_rz_site: {e}")
        return False
    finally:
        conn.close()

# ==================== PER-USER PROXIES ====================
def add_db_user_proxies(user_id: int, proxy_urls: list[str]) -> tuple[int, int]:
    conn = get_db_connection()
    if not conn:
        return (0, 0)
    inserted = 0
    duplicates = 0
    try:
        now = int(time.time())
        uid = str(user_id)
        with conn.cursor() as cur:
            for p in proxy_urls:
                cur.execute("""
                    INSERT INTO user_proxies (user_id, proxy_url, added_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, proxy_url) DO NOTHING;
                """, (uid, p, now))
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    duplicates += 1
            conn.commit()
            return (inserted, duplicates)
    except Exception as e:
        print(f"[Supabase DB Error] add_db_user_proxies: {e}")
        return (inserted, duplicates)
    finally:
        conn.close()



def get_db_user_proxies(user_id: int) -> list[str]:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT proxy_url FROM user_proxies
                WHERE user_id = %s
                ORDER BY added_at DESC;
            """, (str(user_id),))
            rows = cur.fetchall()
            return [r[0] for r in rows]
    except Exception as e:
        print(f"[Supabase DB Error] get_db_user_proxies: {e}")
        return []
    finally:
        conn.close()

def remove_db_user_proxy(user_id: int, proxy_url: str) -> bool:
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM user_proxies
                WHERE user_id = %s AND (proxy_url = %s OR proxy_url LIKE %s);
            """, (str(user_id), proxy_url, f"%{proxy_url}%"))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        print(f"[Supabase DB Error] remove_db_user_proxy: {e}")
        return False
    finally:
        conn.close()

def clear_db_user_proxies(user_id: int):
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_proxies WHERE user_id = %s;", (str(user_id),))
            conn.commit()
    except Exception as e:
        print(f"[Supabase DB Error] clear_db_user_proxies: {e}")
    finally:
        conn.close()

def sync_db_user_proxies(user_id: int, alive_proxies: list[str]):
    """Atomic replacement of user's active proxies in Supabase database after audit."""
    conn = get_db_connection()
    if not conn:
        return
    try:
        uid = str(user_id)
        now = int(time.time())
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_proxies WHERE user_id = %s;", (uid,))
            for p in alive_proxies:
                cur.execute("""
                    INSERT INTO user_proxies (user_id, proxy_url, added_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, proxy_url) DO NOTHING;
                """, (uid, p, now))
            conn.commit()
    except Exception as e:
        print(f"[Supabase DB Error] sync_db_user_proxies: {e}")
    finally:
        conn.close()




