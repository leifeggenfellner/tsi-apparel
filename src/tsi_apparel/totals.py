"""List the different amounts people owe, and who owes each, for invoicing.

Usage:
    apparel totals                     # every amount owed, and how many owe it
    apparel totals --amount 700        # who owes exactly 700.00 kr
    apparel totals --unpriced          # who has an item with no price
    apparel totals --input other.csv
    apparel totals --no-print-costs    # garments only, no transfer prints

Each person's total is the same Total that `apparel lookup` shows for them.
People whose order has an unpriced item are counted separately, since what
they owe isn't known. Plain `apparel totals` shows no names or contact
details; --amount and --unpriced do.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .lookup import CONTACT_FIELDS, fold, order_lines, order_total
from .prices import format_nok
from .transform import _load_source


def plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def parse_amount(text: str) -> Decimal:
    """An amount as people write it: 1200, 1 200, 1200,50 or 1 200.50 kr."""
    cleaned = re.sub(r"\s+", "", text.casefold()).removesuffix("kr")
    try:
        amount = Decimal(cleaned.replace(",", "."))
    except InvalidOperation:
        amount = None
    if amount is None or not amount.is_finite() or amount < 0:
        raise argparse.ArgumentTypeError(f"not an amount in kr: {text!r}")
    return amount


def person_totals(
    source_rows: list[tuple[str, ...]],
    headers: list[str],
    families: list,
    include_print_costs: bool = True,
) -> list[tuple[tuple[str, ...], Decimal, list[str]]]:
    """(row, total, unpriced items) for everyone who ordered something."""
    totals = []
    for row in source_rows:
        lines = order_lines(row, headers, families)
        if lines:
            totals.append((row, *order_total(lines, include_print_costs)))
    return totals


def print_amounts(totals: list[tuple[tuple[str, ...], Decimal, list[str]]]) -> None:
    priced = Counter(total for _, total, unpriced in totals if not unpriced)
    unpriced_count = sum(1 for _, _, unpriced in totals if unpriced)
    if not totals:
        print("Nobody has ordered anything.")
        return

    people = sum(priced.values())
    print(
        f"{plural(people, 'person', 'people')}, "
        f"{plural(len(priced), 'amount', 'different amounts')}:\n"
    )
    amounts = [format_nok(amount) for amount in sorted(priced)]
    width = max([len("Amount"), *map(len, amounts)])
    print(f"  {'Amount'.rjust(width)}   People")
    for amount, text in zip(sorted(priced), amounts):
        print(f"  {text.rjust(width)}   {priced[amount]}")
    print(f"\nTotal: {format_nok(sum(priced.elements(), Decimal(0)))}")
    if unpriced_count:
        print(
            f"\n{plural(unpriced_count, 'more person has', 'more people have')} "
            "an item with no price, so they're not counted above. "
            "Use `apparel totals --unpriced` to list them."
        )


def contact(row: tuple[str, ...], headers: list[str]) -> list[str]:
    return [row[headers.index(field)] for field in CONTACT_FIELDS]


def print_people(table: list[list[str]]) -> None:
    """One person per line, starting with their name, sorted by name."""
    table = sorted(table, key=lambda cells: fold(cells[0]))
    widths = [max(len(cells[i]) for cells in table) for i in range(len(table[0]))]
    for cells in table:
        line = "   ".join(cell.ljust(width) for cell, width in zip(cells, widths))
        print("  " + line.rstrip())


def print_owing(
    totals: list[tuple[tuple[str, ...], Decimal, list[str]]],
    headers: list[str],
    amount: Decimal,
) -> bool:
    """List who owes exactly ``amount``; False when nobody does."""
    priced = sorted({total for _, total, unpriced in totals if not unpriced})
    rows = [row for row, total, unpriced in totals if not unpriced and total == amount]
    if not rows:
        print(f"Nobody owes {format_nok(amount)}.")
        closest = sorted(sorted(priced, key=lambda owed: abs(owed - amount))[:3])
        if closest:
            print(f"Closest amounts owed: {', '.join(map(format_nok, closest))}")
        return False
    print(f"{plural(len(rows), 'person owes', 'people owe')} {format_nok(amount)}:\n")
    print_people([contact(row, headers) for row in rows])
    return True


def print_unpriced(
    totals: list[tuple[tuple[str, ...], Decimal, list[str]]], headers: list[str]
) -> None:
    unpriced = [(row, items) for row, _, items in totals if items]
    if not unpriced:
        print("Everyone's order has a price.")
        return
    print(
        f"{plural(len(unpriced), 'person has', 'people have')} an item with no price:\n"
    )
    print_people(
        [
            [*contact(row, headers), f"no price for {', '.join(items)}"]
            for row, items in unpriced
        ]
    )


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--input",
        default="apparel_order.csv",
        help="Source order CSV (default: %(default)s)",
    )
    parser.add_argument(
        "--no-print-costs",
        action="store_true",
        help="Leave print (transfer) costs out of the totals",
    )
    listing = parser.add_mutually_exclusive_group()
    listing.add_argument(
        "--amount",
        type=parse_amount,
        help="List the people who owe exactly this amount, e.g. 700 or '1 200,50'",
    )
    listing.add_argument(
        "--unpriced",
        action="store_true",
        help="List the people with an item that has no price",
    )


def run(arguments: argparse.Namespace) -> None:
    source, headers, families = _load_source(Path(arguments.input))
    totals = person_totals(
        list(source.iter_rows()),
        headers,
        families,
        include_print_costs=not arguments.no_print_costs,
    )
    if arguments.amount is not None:
        if not print_owing(totals, headers, arguments.amount):
            raise SystemExit(1)
    elif arguments.unpriced:
        print_unpriced(totals, headers)
    else:
        print_amounts(totals)
