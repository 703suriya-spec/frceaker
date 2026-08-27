import requests
import re
import json
import time

def run_step_inspection():
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
    checkout_url = r_co.url

    print("Checkout URL:", checkout_url)
    
    tokens = re.findall(r'name="authenticity_token" value="([^"]+)"', checkout_html)
    print("Found authenticity tokens:", len(tokens))

    # Look for serialized Shopify checkout state
    config_match = re.search(r'Shopify\.Checkout\s*=\s*({.*?});', checkout_html)
    if config_match:
        print("Found Shopify.Checkout config")
    else:
        print("One-Page Checkout / Modern GraphQL detected.")
        # Extract session token from page
        st = re.search(r'"sessionToken":"([^"]+)"', checkout_html)
        if st:
            print("Extracted live sessionToken:", st.group(1)[:40] + "...")

if __name__ == '__main__':
    run_step_inspection()
