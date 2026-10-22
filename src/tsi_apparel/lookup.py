"""Look up a person's order from apparel_order.csv for pickup-desk use.

Usage:
    apparel lookup                                # interactive: keeps prompting
    apparel lookup "nordmann"                     # one-shot search, then exit
    apparel lookup --input other.csv "nordmann"
    apparel lookup --no-print-costs "nordmann"    # garments only
    apparel lookup --hide-prices "nordmann"       # no prices at all

Matches on name, email, or phone number (partial, case- and
diacritic-insensitive, so "ase" finds "Åse").
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

from .prices import PRINT_PRICES, format_nok, garment_unit_price
from .transform import (
    TransformError,
    _load_source,
    customization_fields,
    family_field_indices,
    first_field,
    is_customization_quantity_field,
    parse_quantity,
    product_and_color,
    product_category,
    resolved_customization_quantity,
)

CONTACT_FIELDS = ("Full Name", "Email", "Phone Number")
FOLD_MAP = str.maketrans({"æ": "ae", "ø": "o", "å": "a"})


def fold(text: str) -> str:
    text = str(text).casefold().translate(FOLD_MAP)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip()


def print_count(raw_value: str | None, quantity: int, in_use: bool) -> int:
    if not in_use:
        return 0
    try:
        return resolved_customization_quantity(raw_value, quantity, in_use, "")
    except TransformError:
        return quantity


def order_lines(
    row: tuple[str, ...], headers: list[str], families: list[tuple[int, int, str]]
) -> list[dict[str, str | int]]:
    lines: list[dict[str, str | int]] = []
    for start, end, family_name in families:
        product, anchor_color = product_and_color(family_name)
        category = product_category(product)
        quantity_columns = [
            index
            for index in family_field_indices(headers, start, end, "quantity")
            if not is_customization_quantity_field(headers[index])
        ]
        for index in quantity_columns:
            header = headers[index]
            quantity = parse_quantity(row[index], header)
            if not quantity:
                continue
            _, field_color = product_and_color(
                re.sub(r"\s+Quantity$", "", header, flags=re.IGNORECASE)
            )
            color = field_color or anchor_color or "Black"
            size = first_field(row, headers, start, end, "size")
            fields = customization_fields(row, headers, start, end)
            has_number = bool(fields.get("back_number") or fields.get("front_number"))
            number_prints = print_count(fields["number_quantity"], quantity, has_number)
            lines.append(
                {
                    "product": product,
                    "category": category,
                    "color": color,
                    "size": size,
                    "quantity": quantity,
                    "initials": fields.get("initials") or "",
                    "back_text": fields.get("back_text") or "",
                    "back_number": fields.get("back_number") or "",
                    "front_number": fields.get("front_number") or "",
                    "name_prints": print_count(
                        fields["back_text_quantity"], quantity, bool(fields["back_text"])
                    ),
                    "initials_prints": print_count(
                        fields["initials_quantity"], quantity, bool(fields["initials"])
                    ),
                    "back_number_prints": number_prints if fields["back_number"] else 0,
                    "front_number_prints": number_prints if fields["front_number"] else 0,
                }
            )
    return lines


def matches_query(row: tuple[str, ...], headers: list[str], query: str) -> bool:
    folded_query = fold(query)
    for field_name in CONTACT_FIELDS:
        value = row[headers.index(field_name)]
        if folded_query in fold(value):
            return True
    return False


def print_cost(line: dict) -> Decimal:
    return sum(
        (
            PRINT_PRICES[kind] * int(line.get(f"{kind}_prints", 0))
            for kind in ("name", "initials", "front_number", "back_number")
        ),
        Decimal(0),
    )


def print_order(
    row: tuple[str, ...],
    headers: list[str],
    lines: list[dict],
    show_prices: bool = True,
    include_print_costs: bool = True,
) -> None:
    name = row[headers.index("Full Name")].strip()
    email = row[headers.index("Email")].strip()
    phone = row[headers.index("Phone Number")].strip()
    submitted = row[headers.index("Submitted at")].strip()

    print(f"{name}")
    print(f"  Email: {email}   Phone: {phone}   Submitted: {submitted}")
    if not lines:
        print("  (no items ordered)")
        return

    header_row = ("Product", "Color", "Size", "Qty", "Initials", "Back print", "Number")
    widths = [20, 6, 12, 4, 9, 16, 7]
    if show_prices:
        header_row += ("Price",)
        widths.append(12)
    print(
        "  "
        + "".join(text.ljust(width) for text, width in zip(header_row, widths))
    )
    total = 0
    clothing_cost = Decimal(0)
    prints_cost = Decimal(0)
    unpriced: list[str] = []
    for line in lines:
        number = line["back_number"] or line["front_number"] or ""
        cells = (
            str(line["product"]),
            str(line["color"]),
            str(line["size"]) or "-",
            str(line["quantity"]),
            str(line["initials"]),
            str(line["back_text"]),
            str(number),
        )
        if show_prices:
            unit_price = garment_unit_price(str(line["product"]))
            line_prints = print_cost(line) if include_print_costs else Decimal(0)
            prints_cost += line_prints
            if unit_price is None:
                unpriced.append(str(line["product"]))
                cells += ("?",)
            else:
                line_clothing = unit_price * int(line["quantity"])
                clothing_cost += line_clothing
                cells += (format_nok(line_clothing + line_prints),)
        print("  " + "".join(cell.ljust(width) for cell, width in zip(cells, widths)))
        total += int(line["quantity"])
    print(f"  Total garments: {total}")
    if not show_prices:
        return
    print(f"  Clothing: {format_nok(clothing_cost)}")
    if include_print_costs:
        print(f"  Prints:   {format_nok(prints_cost)}")
    print(f"  Total:    {format_nok(clothing_cost + prints_cost)}")
    if unpriced:
        print(f"  (no price for {', '.join(sorted(set(unpriced)))}; not included in total)")


def search(
    query: str,
    source_rows: list[tuple[str, ...]],
    headers: list[str],
    families: list,
    show_prices: bool = True,
    include_print_costs: bool = True,
) -> int:
    matched_rows = [row for row in source_rows if matches_query(row, headers, query)]
    if not matched_rows:
        print(f'No orders found matching "{query}".')
        return 0
    print(f'{len(matched_rows)} match(es) for "{query}":\n')
    for row in matched_rows:
        print_order(
            row,
            headers,
            order_lines(row, headers, families),
            show_prices=show_prices,
            include_print_costs=include_print_costs,
        )
        print()
    return len(matched_rows)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("query", nargs="?", help="Name, email, or phone to search for")
    parser.add_argument(
        "--input", default="apparel_order.csv", help="Source order CSV (default: %(default)s)"
    )
    parser.add_argument(
        "--no-print-costs",
        action="store_true",
        help="Leave print (transfer) costs out of the price totals",
    )
    parser.add_argument(
        "--hide-prices", action="store_true", help="Do not show any prices"
    )


def run(arguments: argparse.Namespace) -> None:
    price_options = {
        "show_prices": not arguments.hide_prices,
        "include_print_costs": not arguments.no_print_costs,
    }

    source, headers, families = _load_source(Path(arguments.input))
    source_rows = list(source.iter_rows())

    if arguments.query:
        search(arguments.query, source_rows, headers, families, **price_options)
        return

    print("Order lookup — type a name, email, or phone (blank line to quit).")
    while True:
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not query:
            break
        search(query, source_rows, headers, families, **price_options)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_arguments(parser)
    run(parser.parse_args(argv))
