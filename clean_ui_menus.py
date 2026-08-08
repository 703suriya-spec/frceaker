import re
import sys

def main():
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # We need to find block replacements for the command responses.
    # It's easier to write a targeted script.
    
    # 1. For /st1
    content = re.sub(
        r'status_emoji = "✅" if st in \("charged", "approved"\) else "❌"\n    res = f"""<b>Stripe \$1 Charge</b>\n━━━━━━━━━━━━━━━━━━━━\n💳 <b>CC:</b> <code>\{cc\}\|\{mm\}\|\{yy\}\|\{cvc\}</code>\n💡 <b>Status:</b> \{status_emoji\} \{st\.upper\(\)\}\n💬 <b>Message:</b> \{msg\}\n⏱️ <b>Time:</b> \{time_taken\}s\n━━━━━━━━━━━━━━━━━━━━\n<i>Gateway: Stripe \$1</i>"""',
        r'status_line = f"Status: {st.upper()} - {msg}\\n" if st not in ("charged", "approved") else ""\n    res = f"""<b>Stripe $1 Charge</b>\n━━━━━━━━━━━━━━━━━━━━\nCC: <code>{cc}|{mm}|{yy}|{cvc}</code>\n{status_line}Time: {time_taken}s\n━━━━━━━━━━━━━━━━━━━━\nGateway: Stripe $1"""',
        content, flags=re.MULTILINE
    )

    # 2. For /br1
    content = re.sub(
        r'status_emoji = "✅" if st in \("charged", "approved"\) else "❌"\n    res = f"""<b>Braintree \$1 Charge</b>\n━━━━━━━━━━━━━━━━━━━━\n💳 <b>CC:</b> <code>\{cc\}\|\{mm\}\|\{yy\}\|\{cvc\}</code>\n💡 <b>Status:</b> \{status_emoji\} \{st\.upper\(\)\}\n💬 <b>Message:</b> \{msg\}\n⏱️ <b>Time:</b> \{time_taken\}s\n━━━━━━━━━━━━━━━━━━━━\n<i>Gateway: Braintree \$1</i>"""',
        r'status_line = f"Status: {st.upper()} - {msg}\\n" if st not in ("charged", "approved") else ""\n    res = f"""<b>Braintree $1 Charge</b>\n━━━━━━━━━━━━━━━━━━━━\nCC: <code>{cc}|{mm}|{yy}|{cvc}</code>\n{status_line}Time: {time_taken}s\n━━━━━━━━━━━━━━━━━━━━\nGateway: Braintree $1"""',
        content, flags=re.MULTILINE
    )

    # 3. For /b3auth
    content = re.sub(
        r'status_emoji = "✅" if st in \("approved", "ccn"\) else "❌"\n    res = f"""<b>Braintree Auth</b>\n━━━━━━━━━━━━━━━━━━━━\n💳 <b>CC:</b> <code>\{cc\}\|\{mm\}\|\{yy\}\|\{cvc\}</code>\n💡 <b>Status:</b> \{status_emoji\} \{st\.upper\(\)\}\n💬 <b>Message:</b> \{msg\}\n⏱️ <b>Time:</b> \{time_taken\}s\n━━━━━━━━━━━━━━━━━━━━\n<i>Gateway: Braintree Auth \(silvercell\)</i>"""',
        r'status_line = f"Status: {st.upper()} - {msg}\\n" if st not in ("approved", "ccn") else ""\n    res = f"""<b>Braintree Auth</b>\n━━━━━━━━━━━━━━━━━━━━\nCC: <code>{cc}|{mm}|{yy}|{cvc}</code>\n{status_line}Time: {time_taken}s\n━━━━━━━━━━━━━━━━━━━━\nGateway: Braintree Auth (silvercell)"""',
        content, flags=re.MULTILINE
    )

    # 4. For /b3rap
    content = re.sub(
        r'status_emoji = "✅" if st in \("approved", "ccn"\) else "❌"\n    res = f"""<b>Braintree Rapunzel Auth</b>\n━━━━━━━━━━━━━━━━━━━━\n💳 <b>CC:</b> <code>\{cc\}\|\{mm\}\|\{yy\}\|\{cvc\}</code>\n💡 <b>Status:</b> \{status_emoji\} \{st\.upper\(\)\}\n💬 <b>Message:</b> \{msg\}\n⏱️ <b>Time:</b> \{time_taken\}s\n━━━━━━━━━━━━━━━━━━━━\n<i>Gateway: Braintree Auth \(bellamoda\)</i>"""',
        r'status_line = f"Status: {st.upper()} - {msg}\\n" if st not in ("approved", "ccn") else ""\n    res = f"""<b>Braintree Rapunzel Auth</b>\n━━━━━━━━━━━━━━━━━━━━\nCC: <code>{cc}|{mm}|{yy}|{cvc}</code>\n{status_line}Time: {time_taken}s\n━━━━━━━━━━━━━━━━━━━━\nGateway: Braintree Auth (bellamoda)"""',
        content, flags=re.MULTILINE
    )

    # 5. For /rz1
    content = re.sub(
        r'status_emoji = "✅" if st in \("live"\) else "❌"\n    res = f"""<b>Razorpay \$1 Charge</b>\n━━━━━━━━━━━━━━━━━━━━\n💳 <b>CC:</b> <code>\{cc\}\|\{mm\}\|\{yy\}\|\{cvc\}</code>\n💡 <b>Status:</b> \{status_emoji\} \{st\.upper\(\)\}\n💬 <b>Message:</b> \{msg\}\n⏱️ <b>Time:</b> \{time_taken\}s\n━━━━━━━━━━━━━━━━━━━━\n<i>Gateway: Razorpay New</i>"""',
        r'status_line = f"Status: {st.upper()} - {msg}\\n" if st != "live" else ""\n    res = f"""<b>Razorpay $1 Charge</b>\n━━━━━━━━━━━━━━━━━━━━\nCC: <code>{cc}|{mm}|{yy}|{cvc}</code>\n{status_line}Time: {time_taken}s\n━━━━━━━━━━━━━━━━━━━━\nGateway: Razorpay New"""',
        content, flags=re.MULTILINE
    )

    # 6. For /vbv2
    content = re.sub(
        r'status_emoji = "✅" if code == "passed" else \("⚠️" if code == "challenge_3d" else "❌"\)\n    res = f"""<b>Braintree 3DS Lookup</b>\n━━━━━━━━━━━━━━━━━━━━\n💳 <b>CC:</b> <code>\{card_input\}</code>\n💡 <b>Status:</b> \{status_emoji\} \{code\.upper\(\)\}\n💬 <b>Message:</b> \{msg\}\n⏱️ <b>Time:</b> \{time_taken\}s\n━━━━━━━━━━━━━━━━━━━━\n<i>Gateway: VBV Hosted API</i>"""',
        r'status_line = f"Status: {code.upper()} - {msg}\\n" if code != "passed" else ""\n    res = f"""<b>Braintree 3DS Lookup</b>\n━━━━━━━━━━━━━━━━━━━━\nCC: <code>{card_input}</code>\n{status_line}Time: {time_taken}s\n━━━━━━━━━━━━━━━━━━━━\nGateway: VBV Hosted API"""',
        content, flags=re.MULTILINE
    )

    # 7. For /st2
    content = re.sub(
        r'status_emoji = "✅" if msg == "Card Added" else "❌"\n    res = f"""<b>Stripe WCPay New</b>\n━━━━━━━━━━━━━━━━━━━━\n💳 <b>CC:</b> <code>\{card_input\}</code>\n💡 <b>Status:</b> \{status_emoji\}\n💬 <b>Message:</b> \{msg\}\n⏱️ <b>Time:</b> \{time_taken\}s\n━━━━━━━━━━━━━━━━━━━━\n<i>Gateway: Stripe New \(motherluck\)</i>"""',
        r'status_line = f"Status: {msg}\\n" if msg != "Card Added" else ""\n    res = f"""<b>Stripe WCPay New</b>\n━━━━━━━━━━━━━━━━━━━━\nCC: <code>{card_input}</code>\n{status_line}Time: {time_taken}s\n━━━━━━━━━━━━━━━━━━━━\nGateway: Stripe New (motherluck)"""',
        content, flags=re.MULTILINE
    )

    # 8. For /st (original)
    content = re.sub(
        r'if is_live:\n        status = "✅ <b>Approved \(Charged\)</b>"\n    else:\n        status = f"❌ <b>Declined</b> - \{msg\}"\n        \n    res = f"""<b>Stripe WCPay Charge</b>\n━━━━━━━━━━━━━━━━━━━━\n💳 <b>CC:</b> <code>\{cc\}\|\{mm\}\|\{yy\}\|\{cvc\}</code>\n💡 <b>Status:</b> \{status\}\n💰 <b>Amount:</b> \{amt\}\n⏱️ <b>Time:</b> \{time_taken\}s\n━━━━━━━━━━━━━━━━━━━━\n<i>Gateway: Stripe \(WooCommerce Payments\)</i>"""',
        r'status_line = f"Status: {msg}\\n" if not is_live else ""\n    res = f"""<b>Stripe WCPay Charge</b>\n━━━━━━━━━━━━━━━━━━━━\nCC: <code>{cc}|{mm}|{yy}|{cvc}</code>\n{status_line}Time: {time_taken}s\n━━━━━━━━━━━━━━━━━━━━\nGateway: Stripe (WooCommerce Payments)"""',
        content, flags=re.MULTILINE
    )

    # 9. For /vbv (original)
    content = re.sub(
        r'if is_live:\n        status_str = "VBV ✅"\n        resp_str = msg\.replace\("3DS Passed: ", ""\)\.replace\("Non-VBV \(Bypassed\): ", ""\)\n    else:\n        status_str = "VBV ❌"\n        resp_str = msg\.replace\("VBV \(Challenge Required\): ", ""\)\.replace\("Lookup Error: ", ""\)\.replace\("Failed: ", ""\)\n\n    user_name = event\.sender\.first_name if event\.sender and event\.sender\.first_name else "User"\n\n    res = f"""<b>Vbv Check</b> \n\n💳 <b>𝗖𝗖</b> : <code>\{cc\}\|\{mm\}\|\{yy\}\|\{cvc\}</code>\n💡 <b>𝗦𝘁𝗮𝘁𝘂𝘀</b> : \{status_str\}\n💬 <b>𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲</b> : <code>\{resp_str\}</code>\n\n🔍 <b>𝗕𝗶𝗻</b> : <code>\{bin_num\}</code>\n🌐 <b>𝗖𝗼𝘂𝗻𝘁𝗿𝘆</b> : <code>\{country\}</code>\n🏦 <b>𝗜𝘀𝘀𝘂𝗲𝗿</b> : <code>\{bank\}</code>\n💳 <b>𝗧𝘆𝗽𝗲</b> : <code>\{card_type\}</code>\n⏱️ <b>𝗧/𝘁</b> : <code>\{time_taken\}s</code> \| <b>Proxy</b> : <code>\{proxy_status\}</code>\n👤 <b>𝗨𝘀𝗲𝗿</b> : <code>\{user_name\}</code>"""',
        r'status_line = f"Status: {msg}\\n" if not is_live else ""\n    res = f"""<b>Vbv Check</b>\n━━━━━━━━━━━━━━━━━━━━\nCC: <code>{cc}|{mm}|{yy}|{cvc}</code>\n{status_line}BIN: <code>{bin_num}</code>\nCountry: <code>{country}</code>\nBank: <code>{bank}</code>\nType: <code>{card_type}</code>\nTime: {time_taken}s | Proxy: {proxy_status}\n━━━━━━━━━━━━━━━━━━━━\nGateway: VBV (Braintree)"""',
        content, flags=re.MULTILINE
    )

    # 10. For /rz (original)
    content = re.sub(
        r'if result\[\'status\'\] == \'Charged\':\n            status_emoji = "CHARGED ✅"\n        else:\n            status_emoji = "DECLINED ❌"\n\n        res_msg = f"""<b>AUTO RAZORPAY CHECKOUT</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n💳 <b>Card:</b> <code>\{card\}</code>\n⚡ <b>Status:</b> \{status_emoji\}\n💬 <b>Response:</b> <code>\{response_msg\}</code>\n💰 <b>Amount:</b> <code>₹\{price\}</code>\n\nℹ️ <b>Brand:</b> \{brand\} - \{bin_type\} \(\{level\}\)\n🏦 <b>Bank:</b> \{bank\}\n🌐 <b>Country:</b> \{country\} \{flag\}"""',
        r'status_line = f"Status: {response_msg}\\n" if result["status"] != "Charged" else ""\n        res_msg = f"""<b>AUTO RAZORPAY CHECKOUT</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nCC: <code>{card}</code>\n{status_line}Brand: {brand} - {bin_type} ({level})\nBank: {bank}\nCountry: {country}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nGateway: Razorpay ₹1"""',
        content, flags=re.MULTILINE
    )

    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    main()
