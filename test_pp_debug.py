import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('alone_checker_bot')
import asyncio
from paypal_lounsbury_engine import check_card_paypal_lounsbury_sync

test_card = "5187255864020882"
mm = "05"
yy = "2030"
cvc = "540"

print(f"=== TESTING PAYPAL LOUNSBURY ENGINE ON {test_card}|{mm}|{yy}|{cvc} ===")
st, msg, brand = check_card_paypal_lounsbury_sync(test_card, mm, yy, cvc)
print(f"Status: {st}")
print(f"Msg: {msg}")
print(f"Brand: {brand}")
