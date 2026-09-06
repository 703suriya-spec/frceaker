"""
Faker Identity & Address Generator for Alone Checker Bot
Generates realistic names, billing/shipping addresses, emails, and phone numbers.
Supports country/currency-specific locale mapping.
"""
import random
from typing import Dict, Any, Tuple

try:
    from faker import Faker
    _FAKER_AVAILABLE = True
except ImportError:
    _FAKER_AVAILABLE = False

LOCALE_MAP = {
    'US': 'en_US', 'USD': 'en_US',
    'GB': 'en_GB', 'UK': 'en_GB', 'GBP': 'en_GB',
    'CA': 'en_CA', 'CAD': 'en_CA',
    'AU': 'en_AU', 'AUD': 'en_AU',
    'DE': 'de_DE', 'EUR': 'de_DE',
    'FR': 'fr_FR',
    'ES': 'es_ES',
    'IT': 'it_IT',
    'NL': 'nl_NL',
    'BR': 'pt_BR', 'BRL': 'pt_BR',
    'MX': 'es_MX', 'MXN': 'es_MX',
    'IN': 'en_IN', 'INR': 'en_IN',
}

_FAKER_INSTANCES = {}

def get_faker_instance(locale_code: str = 'en_US'):
    if not _FAKER_AVAILABLE:
        return None
    if locale_code not in _FAKER_INSTANCES:
        try:
            _FAKER_INSTANCES[locale_code] = Faker(locale_code)
        except Exception:
            _FAKER_INSTANCES[locale_code] = Faker('en_US')
    return _FAKER_INSTANCES[locale_code]

EMAIL_DOMAINS = [
    'gmail.com', 'yahoo.com', 'outlook.com', 'icloud.com',
    'hotmail.com', 'aol.com', 'protonmail.com', 'mail.com'
]

FALLBACK_FIRST_NAMES = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"]
FALLBACK_LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]

FALLBACK_ADDRESSES = {
    "US": [
        {"address1": "742 Evergreen Terrace", "city": "Springfield", "zoneCode": "OR", "postalCode": "97477", "countryCode": "US", "phone": "5415550199"},
        {"address1": "100 Wilshire Blvd", "city": "Santa Monica", "zoneCode": "CA", "postalCode": "90401", "countryCode": "US", "phone": "3105550143"},
        {"address1": "350 Fifth Ave", "city": "New York", "zoneCode": "NY", "postalCode": "10118", "countryCode": "US", "phone": "2125550178"},
        {"address1": "233 S Wacker Dr", "city": "Chicago", "zoneCode": "IL", "postalCode": "60606", "countryCode": "US", "phone": "3125550182"},
        {"address1": "500 Howard St", "city": "San Francisco", "zoneCode": "CA", "postalCode": "94105", "countryCode": "US", "phone": "4155550129"},
    ],
    "GB": [
        {"address1": "10 Downing Street", "city": "London", "zoneCode": "ENG", "postalCode": "SW1A 2AA", "countryCode": "GB", "phone": "02079460912"},
        {"address1": "221B Baker Street", "city": "London", "zoneCode": "ENG", "postalCode": "NW1 6XE", "countryCode": "GB", "phone": "02079460144"},
    ],
    "CA": [
        {"address1": "111 Wellington St", "city": "Ottawa", "zoneCode": "ON", "postalCode": "K1A 0A9", "countryCode": "CA", "phone": "6135550165"},
        {"address1": "100 Front St W", "city": "Toronto", "zoneCode": "ON", "postalCode": "M5J 1E6", "countryCode": "CA", "phone": "4165550190"},
    ],
    "AU": [
        {"address1": "100 Market St", "city": "Sydney", "zoneCode": "NSW", "postalCode": "2000", "countryCode": "AU", "phone": "0292670000"},
        {"address1": "120 Collins St", "city": "Melbourne", "zoneCode": "VIC", "postalCode": "3000", "countryCode": "AU", "phone": "0396540000"},
    ]
}

def generate_fake_identity(country_or_currency: str = "US") -> Dict[str, Any]:
    """
    Generates a full fake identity (name, email, phone, address).
    Returns dict with keys:
      firstName, lastName, name, email, phone,
      address1, address2, city, zoneCode, postalCode, countryCode
    """
    cc_upper = (country_or_currency or "US").upper()
    locale = LOCALE_MAP.get(cc_upper, 'en_US')
    fk = get_faker_instance(locale)

    if fk:
        try:
            first = fk.first_name()
            last = fk.last_name()
            email_domain = random.choice(EMAIL_DOMAINS)
            email = f"{first.lower()}.{last.lower()}{random.randint(10, 999)}@{email_domain}"
            
            raw_phone = fk.phone_number()
            phone = ''.join(c for c in raw_phone if c.isdigit() or c == '+')[:15]
            if len(phone) < 10:
                phone = f"1{random.randint(201, 999)}{random.randint(200, 999)}{random.randint(1000, 9999)}"

            street = fk.street_address()
            city = fk.city()

            state = None
            if hasattr(fk, 'state_abbr'):
                try:
                    state = fk.state_abbr()
                except Exception:
                    pass
            if not state:
                state = fk.city_suffix().upper()[:2] if hasattr(fk, 'city_suffix') else "NY"

            postcode = fk.postcode()
            country = cc_upper if len(cc_upper) == 2 else "US"

            return {
                "firstName": first,
                "lastName": last,
                "name": f"{first} {last}",
                "email": email,
                "phone": phone,
                "address1": street,
                "address2": "",
                "city": city,
                "zoneCode": state,
                "postalCode": postcode,
                "countryCode": country
            }
        except Exception:
            pass

    first = random.choice(FALLBACK_FIRST_NAMES)
    last = random.choice(FALLBACK_LAST_NAMES)
    email = f"{first.lower()}.{last.lower()}{random.randint(10, 999)}@{random.choice(EMAIL_DOMAINS)}"
    
    country = cc_upper if len(cc_upper) == 2 and cc_upper in FALLBACK_ADDRESSES else "US"
    addr_list = FALLBACK_ADDRESSES.get(country, FALLBACK_ADDRESSES["US"])
    base_addr = random.choice(addr_list).copy()

    base_addr.update({
        "firstName": first,
        "lastName": last,
        "name": f"{first} {last}",
        "email": email,
    })
    return base_addr

def get_random_identity_tuple(country: str = "US") -> Tuple[str, str, str]:
    """Returns (firstName, lastName, email)"""
    ident = generate_fake_identity(country)
    return ident["firstName"], ident["lastName"], ident["email"]
