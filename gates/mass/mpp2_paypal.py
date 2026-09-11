"""
PayPal Mass Charge Runner ($10.00) - /mpp2
"""
from gates.charge.pp_paypal import check_card_paypal_aww

async def run_mpp2(card: str, proxy: str | None = None) -> tuple[str, str, str]:
    parts = card.split("|")
    if len(parts) >= 4:
        return await check_card_paypal_aww(parts[0], parts[1], parts[2], parts[3], proxy_url=proxy)
    return "declined", "Invalid Card Format", "PayPal"
