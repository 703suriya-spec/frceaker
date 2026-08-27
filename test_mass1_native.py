"""
Mass 1 (/mass1) Native Engine - PayPal Commerce Charged
Direct PayPal Commerce GraphQL pipeline.
Zero external API key dependencies.
"""
import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
from paypal_lounsbury_engine import check_card_paypal_lounsbury_sync

if __name__ == '__main__':
    card_arg = sys.argv[1] if len(sys.argv) > 1 else "4033060047342909|08|28|667"
    p = card_arg.split('|')
    print(f"[*] Running Native Test of Mass 1 (/mass1) Gate on: {card_arg}")
    start = time.time()
    
    st, msg, brand = check_card_paypal_lounsbury_sync(p[0], p[1], p[2], p[3])
    elapsed = round(time.time() - start, 2)
    
    status_label = "Approved! 🟩" if st in ("live", "charged") else "DECLINED 🔴"
    
    print(f"""
=== TELEGRAM BOT OUTPUT (MASS 1 GATE) ===
Gate Auth: >_ PayPal Commerce Charged ($10.00)
----------------------------------------
Card: {card_arg}
Status: {status_label}
Response: {msg}
----------------------------------------
Time: {elapsed}s | Gateway: Mass 1 (PayPal Commerce)
""")
