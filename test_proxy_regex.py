import re

sample_text = """
purevpn0s13628768:vecnnovx@px051703.pointtoserver.com:10780
purevpn0s7397024:6CU9ZvexLGTqpB@px051703.pointtoserver.com:10780
192.168.1.1:8080
1.1.1.1:8080:user:pass
user:pass@1.1.1.1:8080
http://user:pass@px051703.pointtoserver.com:10780
socks5://px051703.pointtoserver.com:10780:user:pass
"""

def extract_proxies_universal(text_content):
    if not text_content:
        return []
    cleaned_text = re.sub(r'[\r\t\u200b\u200c\u200d\ufeff\xa0]', '', text_content)
    cleaned_text = re.sub(r'^[•\-\*\s]+', '', cleaned_text, flags=re.MULTILINE)
    
    # Split by lines and tokens
    lines = [l.strip() for l in cleaned_text.splitlines() if l.strip()]
    proxies = []
    
    # Comprehensive pattern matching
    # 1. Scheme + optional auth + host + port
    # 2. user:pass@host:port or host:port:user:pass or host:port
    pattern = r'(?:(?:socks4|socks5|http|https)://)?(?:[a-zA-Z0-9_\-\.]+:[a-zA-Z0-9_\-\.]+@)?[a-zA-Z0-9_\-\.]+:\d{2,5}(?::[a-zA-Z0-9_\-\.]+:[a-zA-Z0-9_\-\.]+)?'
    
    for token in re.findall(pattern, cleaned_text):
        token = token.strip()
        if token and token not in proxies and not token.startswith(('/addproxy', '/proxy')):
            # Basic validation
            parts = token.split(':')
            if len(parts) >= 2:
                proxies.append(token)
    return proxies

extracted = extract_proxies_universal(sample_text)
print("Extracted proxies:", len(extracted))
for p in extracted:
    print("  •", p)
