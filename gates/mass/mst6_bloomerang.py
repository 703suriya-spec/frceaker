"""
Stripe Mass Charge 2 Runner (Bloomerang $1.00) - /mst6
"""
from gates.charge.st6_bloomerang import check_card_bloomerang

async def run_mst6(card: str, proxy: str | None = None) -> tuple[str, str, str]:
    parts = card.split("|")
    if len(parts) >= 4:
        st, msg, brand = await check_card_bloomerang(parts[0], parts[1], parts[2], parts[3], proxy_url=proxy)
        return st, msg, brand
    return "declined", "Invalid Card Format", "Unknown"
