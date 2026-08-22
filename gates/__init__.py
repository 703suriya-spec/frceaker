"""
Gates Master Package
Organized into:
- gates.auth (6 Auth Gates)
- gates.charge (16 Charge Gates)
- gates.mass (6 Mass Checkers)
"""
from gates import auth
from gates import charge
from gates import mass

__all__ = ["auth", "charge", "mass"]
