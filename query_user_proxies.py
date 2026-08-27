import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import json

sys.path.append('alone_checker_bot')
from db import get_db_connection

conn = get_db_connection()
if not conn:
    print("Failed to connect to database.")
    sys.exit(1)

try:
    with conn.cursor() as cur:
        # Check all records in user_proxies table
        cur.execute("SELECT user_id, proxies, updated_at FROM user_proxies;")
        rows = cur.fetchall()
        print(f"Total Users with custom proxies in Database: {len(rows)}\n")
        
        total_proxies_all_users = 0
        for uid, p_json, updated in rows:
            try:
                p_list = json.loads(p_json) if isinstance(p_json, str) else p_json
                count = len(p_list)
                total_proxies_all_users += count
                print(f"👤 User ID: {uid}")
                print(f"   • Loaded Proxies Count: {count}")
                if count > 0:
                    print(f"   • Sample: {p_list[0]} ... {p_list[-1] if count > 1 else ''}")
            except Exception as ex:
                print(f"   • Error parsing proxies for user {uid}: {ex}")
                
        print(f"\n==========================================")
        print(f"Total Combined User Proxies: {total_proxies_all_users}")
        print(f"==========================================")
except Exception as e:
    print("Database Query Error:", e)
finally:
    conn.close()
