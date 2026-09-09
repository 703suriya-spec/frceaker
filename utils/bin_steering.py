"""
BIN Steering & Dynamic Geo-Alignment Engine
Provides instant in-memory card classification, 3DS risk evaluation, and issuer-matched address generation.
"""
import random

# Mapping of Country Codes to Authentic Address Profiles
GEO_PROFILES = {
    "US": [
        ("New York", "NY", "10001", "Main Street"),
        ("Los Angeles", "CA", "90001", "Sunset Blvd"),
        ("Chicago", "IL", "60601", "Michigan Ave"),
        ("Houston", "TX", "77001", "Post Oak Blvd"),
        ("Miami", "FL", "33101", "Ocean Drive"),
    ],
    "GB": [
        ("London", "London", "SW1A 1AA", "High Street"),
        ("Manchester", "Greater Manchester", "M1 1AD", "Market Street"),
        ("Birmingham", "West Midlands", "B1 1AA", "Broad Street"),
    ],
    "CA": [
        ("Toronto", "ON", "M5H 2N2", "Queen Street"),
        ("Vancouver", "BC", "V6B 1A1", "Robson Street"),
        ("Montreal", "QC", "H3B 1A1", "Sainte-Catherine"),
    ],
    "AU": [
        ("Sydney", "NSW", "2000", "George Street"),
        ("Melbourne", "VIC", "3000", "Collins Street"),
        ("Brisbane", "QLD", "4000", "Queen Street"),
    ],
    "DE": [
        ("Berlin", "Berlin", "10115", "Friedrichstrasse"),
        ("Munich", "Bavaria", "80331", "Maximilianstrasse"),
    ],
    "FR": [
        ("Paris", "Ile-de-France", "75001", "Rue de Rivoli"),
        ("Lyon", "Rhone", "69001", "Place Bellecour"),
    ]
}

# Known Non-VBV / Frictionless US Subprime & Commercial BIN Prefixes
KNOWN_NON_VBV_BINS = {
    # Chime / Bancorp / Stride
    "440393", "498503", "428203", "463726", "414398",
    # Green Dot / Go2Bank
    "414321", "414322", "414323", "414398", "511342", "526214",
    # Netspend / MetaBank / Pathward
    "485460", "485461", "526219", "409758", "546616", "435880",
    # Sutton Bank (Cash App)
    "400344", "475435", "403163",
    # Commercial / Corporate Purchasing
    "471563", "471527", "448528", "424604", "556735", "556888", "540156",
    # Amex Subprime
    "379363", "372485", "375183", "371449", "378282", "340000"
}

def get_geo_aligned_identity(country_code: str = "US") -> dict:
    cc = (country_code or "US").upper()
    pool = GEO_PROFILES.get(cc, GEO_PROFILES["US"])
    city, state, postal, street_name = random.choice(pool)
    street_num = random.randint(100, 9999)
    
    first_names = ["Marcus", "James", "Alexander", "David", "Robert", "Michael", "William", "Daniel"]
    last_names = ["Vance", "Miller", "Smith", "Johnson", "Williams", "Brown", "Davis", "Wilson"]
    first = random.choice(first_names)
    last = random.choice(last_names)
    
    return {
        "first_name": first,
        "last_name": last,
        "name": f"{first} {last}",
        "line1": f"{street_num} {street_name}",
        "city": city,
        "state": state,
        "postal_code": postal,
        "country": cc,
        "email": f"{first.lower()}.{last.lower()}{random.randint(100,999)}@gmail.com",
        "phone": f"+1555{random.randint(100,999)}{random.randint(1000,9999)}"
    }

def evaluate_bin_3ds_profile(bin6: str, country_code: str = "US", card_type: str = "credit") -> dict:
    """
    Evaluates 3DS / VBV risk profile based on BIN heuristics.
    Returns: {"category": "DIRECT_CHECKOUT"|"FRICTIONLESS"|"CHALLENGE", "score": float, "reason": str}
    """
    cc = (country_code or "US").upper()
    if bin6 in KNOWN_NON_VBV_BINS or bin6[:4] in {"4854", "4143", "5262", "4403", "4031"}:
        return {
            "category": "DIRECT_CHECKOUT",
            "score": 0.92,
            "reason": "Known Non-VBV / US Subprime / Prepaid BIN"
        }
    
    if cc == "US" and card_type.lower() == "prepaid":
        return {
            "category": "DIRECT_CHECKOUT",
            "score": 0.85,
            "reason": "US Prepaid Debit (Low 3DS enforcement)"
        }
        
    if cc in {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "GB"}:
        return {
            "category": "CHALLENGE",
            "score": 0.15,
            "reason": "EEA / PSD2 Mandatory 3DS SCA"
        }
        
    if cc == "US":
        return {
            "category": "FRICTIONLESS",
            "score": 0.70,
            "reason": "US Domestic Issuer (Frictionless candidate)"
        }
        
    return {
        "category": "CHALLENGE",
        "score": 0.35,
        "reason": "International Card (3DS OTP likely)"
    }
