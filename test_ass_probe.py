import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
import httpx
import time

def capture(text, start, end):
    try:
        s = text.split(start, 1)[1]
        return s.split(end, 1)[0]
    except Exception:
        return None

async def test_ass_probe():
    headers_base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }
    async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=20.0) as session:
        print("[*] Probing isubscribe.co.uk magazine product page...")
        r = await session.get("https://www.isubscribe.co.uk/She-Kicks-Magazine-Subscription.cfm", headers=headers_base)
        print(f"    Product Page Status: {r.status_code}")
        
        pi = capture(r.text, "prodId=", "&amp")
        ps = capture(r.text, "prodSubId=", "&amp")
        token = capture(r.text, "_token = '", "'")
        print(f"    Extracted: prodId={pi} | prodSubId={ps} | _token={token}")

        print("[*] Probing payment bridge (paynow.pmnts.io)...")
        r_bridge = await session.get("https://paynow.pmnts.io/sdk/bridge", headers=headers_base)
        print(f"    Bridge Status: {r_bridge.status_code}")

if __name__ == '__main__':
    asyncio.run(test_ass_probe())
