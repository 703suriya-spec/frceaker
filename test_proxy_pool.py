import asyncio
import aiohttp
import random

with open("alone_checker_bot/test_proxies.txt") as f:
    proxies = [line.strip() for line in f if line.strip()]

async def check_single_proxy(p):
    parts = p.split("@")
    user_pass = parts[0]
    host_port = parts[1]
    formatted = f"http://{user_pass}@{host_port}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.ipify.org?format=json", proxy=formatted, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    data = await r.json()
                    return p, True, data.get("ip")
    except Exception as e:
        return p, False, str(e)

async def main():
    print(f"[*] Testing {len(proxies)} proxies...")
    tasks = [check_single_proxy(p) for p in proxies]
    results = await asyncio.gather(*tasks)
    alive = [r for r in results if r[1]]
    print(f"[+] Alive proxies: {len(alive)} / {len(proxies)}")
    for a in alive[:5]:
        print(f"    [LIVE] {a[0]} -> External IP: {a[2]}")

if __name__ == '__main__':
    asyncio.run(main())
