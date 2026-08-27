import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import httpx
import time
import random

try:
    with open('alone_checker_bot/test_proxies.txt') as f:
        PROXIES = [l.strip() for l in f if l.strip()]
except Exception:
    PROXIES = []

def get_proxy():
    if not PROXIES:
        return None
    p = random.choice(PROXIES)
    if "@" in p:
        user_pass, host_port = p.split("@")
        return f"http://{user_pass}@{host_port}"
    return f"http://{p}"

async def test_boruto_with_proxy(card_str):
    cc, month, year, cvv = [p.strip() for p in card_str.split('|')[:4]]
    if len(year) == 2:
        year = "20" + year
    month = month.zfill(2)

    proxy = get_proxy()
    print(f"[*] Using Proxy: {proxy}")

    headers_base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    async with httpx.AsyncClient(proxy=proxy, follow_redirects=True, verify=False, timeout=25.0) as session:
        print("[*] Step 1: Visiting Product Page...")
        r1 = await session.get(
            "https://prepsportswear.com/school/us/new-york/accord/kerhonkson-elementary-school-ganders/product/fruit-of-the-loom-mens-5oz-cotton-t-shirt?productid=5078&schoolid=167239",
            headers=headers_base
        )
        print(f"    Product Page Status: {r1.status_code}")
        if r1.status_code == 403:
            print("    [!] Cloudflare blocked on this proxy IP too.")
            return

if __name__ == '__main__':
    asyncio.run(test_boruto_with_proxy('4033060047342909|08|28|667'))
