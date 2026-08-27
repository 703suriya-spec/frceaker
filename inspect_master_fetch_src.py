import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import requests

r_src = requests.get('https://api.github.com/repos/dondai44423/master-fetch/contents/src/master_fetch')
if r_src.status_code == 200:
    for item in r_src.json():
        print(f"{item['name']} ({item['type']})")

r_browser = requests.get('https://api.github.com/repos/dondai44423/master-fetch/contents/src/master_fetch/browser')
if r_browser.status_code == 200:
    print("\n--- browser dir ---")
    for item in r_browser.json():
        print(f"{item['name']} ({item['type']})")
