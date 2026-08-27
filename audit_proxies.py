import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import sqlite3

sys.path.append('alone_checker_bot')

print("=== 1. LOCAL PROXY FILES ===")
for fn in ['proxy.txt', 'proxies.txt', 'test_proxies.txt']:
    fp = os.path.join('alone_checker_bot', fn)
    if os.path.exists(fp):
        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [l.strip() for l in f if l.strip()]
        print(f"  • {fn}: {len(lines)} proxies")
    else:
        print(f"  • {fn}: Not found")

print("\n=== 2. SQLITE BOT DATABASE ===")
db_path = os.path.join('alone_checker_bot', 'bot_database.db')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cur.fetchall()]
    print(f"  Tables found: {tables}")
    for t in tables:
        if 'proxy' in t or 'user' in t:
            try:
                cur.execute(f"SELECT count(*) FROM {t};")
                count = cur.fetchone()[0]
                print(f"  • Table '{t}': {count} total rows")
                cur.execute(f"SELECT * FROM {t} LIMIT 5;")
                print(f"    Sample rows: {cur.fetchall()}")
            except Exception as e:
                print(f"    Error reading {t}: {e}")
    conn.close()
else:
    print("  bot_database.db not found locally.")

print("\n=== 3. SUPABASE / CLOUD DATABASE ===")
try:
    from db import supabase, get_db_user_proxies
    if supabase:
        res = supabase.table("user_proxies").select("count", count="exact").execute()
        print(f"  • Supabase 'user_proxies' table: {res.count} proxies")
        
        # User break down
        res_users = supabase.table("user_proxies").select("user_id, proxy").execute()
        user_map = {}
        for r in res_users.data:
            uid = r.get("user_id")
            user_map[uid] = user_map.get(uid, 0) + 1
        for uid, count in user_map.items():
            print(f"    - User ID {uid}: {count} proxies")
    else:
        print("  Supabase client not configured.")
except Exception as e:
    print(f"  Supabase query error / note: {e}")
