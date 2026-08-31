# SK-Based Gate Engine
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
                        'available': f"{avail_amt:.2f} {currency}",
                        'pending': f"{pend_amt:.2f} {currency}"
                    }
                    return True, 'LIVE & ACTIVE 🟢', info
                else:
                    err_msg = (bal_json.get('error') or {}).get('message', 'Expired or Invalid SK Key')
                    return False, 'DEAD 🔴 (' + err_msg + ')', None
    except Exception as e:
        return False, 'Error checking key: ' + str(e), None

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
        return False, 'NO KEYS', 'Please add an active SK key using /sk command', ''

    derived_pk, acct_id = derive_pk_or_acct(sk_key, pk_key)

    try:
        sys.path.insert(0, r'C:\Users\acer\Downloads\Ch-main\Ch-main')
        from Gates.skbasedoff import skintoff
        
        async with httpx.AsyncClient(proxy=proxy_url if proxy_url else None, timeout=20.0) as session:
            res_str = await skintoff(session, cc, mm, yy, cvc, sk_key=sk_key, pk_key=derived_pk)
            
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
        return False, 'ERROR', str(e), ''
