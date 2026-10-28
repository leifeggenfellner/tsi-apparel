"""List the different amounts people owe, to know which invoices to make.

Usage:
    apparel totals                     # every amount owed, and how many owe it
    apparel totals --input other.csv
    apparel totals --no-print-costs    # garments only, no transfer prints

Each person's total is the same Total that `apparel lookup` shows for them.
People whose order has an unpriced item are counted separately, since what
they owe isn't known. The output has no names or contact details.
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
from pathlib import Path

from .lookup import order_lines, order_total
from .prices import format_nok
from .transform import _load_source


def plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


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
            "Use `apparel lookup` to see what they ordered."
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


def run(arguments: argparse.Namespace) -> None:
    source, headers, families = _load_source(Path(arguments.input))
    totals = person_totals(
        list(source.iter_rows()),
        headers,
        families,
        include_print_costs=not arguments.no_print_costs,
    )
    print_amounts(totals)
