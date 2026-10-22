"""Price reference for apparel orders, in NOK.

Garment prices are the list prices; the team gets CLOTHING_DISCOUNT off them,
so use ``garment_unit_price`` for the price actually paid. Print (transfer)
prices are already the final per-print price and are not discounted.

Usage:
    apparel prices           # discounted garment prices and print prices
    apparel prices --list    # undiscounted list prices only
"""

from __future__ import annotations

import argparse
from decimal import Decimal

from .transform import PRODUCT_CATEGORIES

CLOTHING_DISCOUNT = Decimal("0.50")

# Keys are product names as normalized by tsi_apparel.transform.normalized().
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
    "name": Decimal("99.20"),
    "initials": Decimal("49.60"),
    "front_number": Decimal("30.00"),
    "back_number": Decimal("50.40"),
}
# Article names as they appear on the supplier's price list.
PRINT_ARTICLES = {
    "name": "Montering Navn K Transfermerke",
    "initials": "Montering Initialer K Transfermerke",
    "front_number": "Montering tall foran K Transfermerke",
    "back_number": "Montering tall rygg K Transfermerke",
}


def garment_unit_price(product: str) -> Decimal | None:
    """Discounted price for one garment, or None when the product is unpriced."""
    list_price = LIST_PRICES.get(" ".join(product.split()).casefold())
    if list_price is None:
        return None
    return list_price * (1 - CLOTHING_DISCOUNT)


def format_nok(amount: Decimal) -> str:
    return f"{amount:,.2f} kr".replace(",", " ")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--list",
        action="store_true",
        help="Show undiscounted list prices only, without print prices",
    )


def price_row(cells: tuple[str, ...]) -> str:
    """Product and category left-aligned, price columns right-aligned."""
    product, category, *amounts = cells
    return (
        product.ljust(18) + category.ljust(18) + "".join(a.rjust(14) for a in amounts)
    )


def run(arguments: argparse.Namespace) -> None:
    header_row = ("Product", "Category", "List price")
    if not arguments.list:
        header_row += (f"Price (-{CLOTHING_DISCOUNT:.0%})",)
    print(price_row(header_row))
    for product, category in PRODUCT_CATEGORIES.items():
        list_price = LIST_PRICES.get(product)
        cells = (product.title(), category, format_nok(list_price) if list_price else "-")
        if not arguments.list:
            unit_price = garment_unit_price(product)
            cells += (format_nok(unit_price) if unit_price else "-",)
        print(price_row(cells))
    if arguments.list:
        return
    print()
    print("Print".ljust(40) + "Price".rjust(10))
    for kind, article in PRINT_ARTICLES.items():
        print(article.ljust(40) + format_nok(PRINT_PRICES[kind]).rjust(10))
    print("\nA shirt number is printed on both front and back.")
