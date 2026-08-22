"""
Stripe Mass Charge 1 Runner ($1.00) - /mst1
"""
from gates.charge.st1_stripe import check_card_stripe_1

async def run_mst1(card: str, proxy: str | None = None) -> tuple[str, str, str]:
    st, msg, code = await check_card_stripe_1(card, proxy_url=proxy)
    return st, msg, "Stripe"
