import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import requests

r_fetch = requests.get('https://raw.githubusercontent.com/dondai44423/master-fetch/master/src/master_fetch/fetcher.py')
if r_fetch.status_code == 200:
    print("--- fetcher.py (first 100 lines) ---")
    print("\n".join(r_fetch.text.splitlines()[:100]))

r_browser = requests.get('https://raw.githubusercontent.com/dondai44423/master-fetch/master/src/master_fetch/browser.py')
if r_browser.status_code == 200:
    print("\n--- browser.py (first 100 lines) ---")
    print("\n".join(r_browser.text.splitlines()[:100]))
