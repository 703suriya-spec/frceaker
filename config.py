import os

# Telegram API & Bot Configuration
API_ID = int(os.getenv("API_ID", "4055879"))
API_HASH = os.getenv("API_HASH", "e53c44adf9ffc52f1eeca7d739e1b212")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8698873627:AAGxIxgMdIiQb19MT5L-dXAFp4_HMGXuT8g")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "Fchker")

# Admin Configuration
ADMIN_ID = int(os.getenv("ADMIN_ID", "1296435544"))
KEY_ADMINS = {ADMIN_ID, 7203159458, 7716186369, 8409853085}

# APIs & Resources (Valyrian AutoShopify Endpoints)
SHOPIFY_APIS = [
    "https://gates.valyrian.cc/autoshopify/curl/check",
    "https://gates.valyrian.cc/autoshopify/tsl/check"
]
PHOTO_URL = os.getenv("PHOTO_URL", "https://i.postimg.cc/pdYQxY74/Alone.png")
