"""
Braintree Mass Charge Runner ($1.00) - /mbt1
"""
from gates.charge.br1_braintree import check_card as check_card_braintree_1

async def run_mbt1(card: str, proxy: str | None = None) -> tuple[str, str, str]:
    parts = card.split("|")
    if len(parts) >= 4:
        st, msg, code = await check_card_braintree_1(parts[0], parts[1], parts[2], parts[3], proxy=proxy)
        return st, msg, "Braintree"
    return "declined", "Invalid Card Format", "Unknown"
