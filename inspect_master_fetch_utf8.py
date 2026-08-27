import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import requests

r_readme = requests.get('https://raw.githubusercontent.com/dondai44423/master-fetch/master/README.md')
if r_readme.status_code == 200:
    print(r_readme.text[:3000])

r_src = requests.get('https://api.github.com/repos/dondai44423/master-fetch/contents/src')
if r_src.status_code == 200:
    print("\n--- src contents ---")
    for item in r_src.json():
        print(f"{item['name']} ({item['type']})")
