import requests
import re
import json

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

matches = re.findall(r'<script\b[^>]*>(.*?)</script>', checkout_html, re.DOTALL)
for i, m in enumerate(matches):
    print(f"=== Script {i} (len {len(m)}) ===")
    print(m[:250], "\n")
