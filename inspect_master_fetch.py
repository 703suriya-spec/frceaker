import requests
import json

r = requests.get('https://api.github.com/repos/dondai44423/master-fetch/contents')
if r.status_code == 200:
    for item in r.json():
        print(f"{item['name']} ({item['type']})")
else:
    print('GitHub API error:', r.status_code, r.text)

# Also check README.md
r_readme = requests.get('https://raw.githubusercontent.com/dondai44423/master-fetch/main/README.md')
if r_readme.status_code == 200:
    print("\n--- README.md ---")
    print(r_readme.text[:2000])
elif r_readme.status_code == 404:
    r_readme2 = requests.get('https://raw.githubusercontent.com/dondai44423/master-fetch/master/README.md')
    if r_readme2.status_code == 200:
        print("\n--- README.md ---")
        print(r_readme2.text[:2000])
