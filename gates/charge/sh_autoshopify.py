"""
Auto Shopify Charge Engine (/sh)
Powered by Storefront GraphQL negotiation across 1,136 auto-rotating myshopify.com domains.
"""
from gates.mass.msh_shopify import check_card_msh as check_card_autoshopify

__all__ = ["check_card_autoshopify"]
