"""Price reference for apparel orders, in NOK.

Garment prices are the list prices; the team gets CLOTHING_DISCOUNT off them,
so use ``garment_unit_price`` for the price actually paid. Print (transfer)
prices are already the final per-print price and are not discounted.
"""

from __future__ import annotations

from decimal import Decimal

CLOTHING_DISCOUNT = Decimal("0.50")

# Keys are product names as normalized by transform_apparel_orders.normalized().
LIST_PRICES = {
    "wyvern kit": Decimal("999"),
    "wisp": Decimal("669"),
    "dryad": Decimal("669"),
    "poseidon": Decimal("999"),
    "fenders": Decimal("1399"),
    "artemis": Decimal("999"),
    "anora": Decimal("799"),
    "anduin": Decimal("799"),
    "rivendell": Decimal("1249"),
    "northland": Decimal("3999"),
    "narvik": Decimal("2299"),
    "elbrus": Decimal("999"),
    "thames": Decimal("999"),
    "galax": Decimal("299"),
    "desna": Decimal("699"),
    "archen": Decimal("699"),
    "acrux": Decimal("429"),
    "round socks evo": Decimal("189"),
    "fixed socks": Decimal("169"),
    "trip": Decimal("999"),
    "rookie": Decimal("1099"),
    # Two prices were supplied for Academy Evo (1099 and 751); the order form
    # has a single Academy Evo option, so the higher one is used here.
    "academy evo": Decimal("1099"),
    "pepper": Decimal("292"),
    "metel": Decimal("199"),
    "blizzard": Decimal("449"),
    "poplar": Decimal("989"),
    # Rivet and Barrier have no price yet.
}

PRINT_PRICES = {
    "name": Decimal("99.20"),  # Montering Navn K Transfermerke
    "initials": Decimal("49.60"),  # Montering Initialer K Transfermerke
    "front_number": Decimal("30.00"),  # Montering tall foran K Transfermerke
    "back_number": Decimal("50.40"),  # Montering tall rygg K Transfermerke
}


def garment_unit_price(product: str) -> Decimal | None:
    """Discounted price for one garment, or None when the product is unpriced."""
    list_price = LIST_PRICES.get(" ".join(product.split()).casefold())
    if list_price is None:
        return None
    return list_price * (1 - CLOTHING_DISCOUNT)


def format_nok(amount: Decimal) -> str:
    return f"{amount:,.2f} kr".replace(",", " ")
