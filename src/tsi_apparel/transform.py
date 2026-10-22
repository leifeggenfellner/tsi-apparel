"""Expand apparel order CSV families into the supplied order-form template."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import tempfile
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import polars as pl

DEFAULT_TEMPLATE = Path(__file__).parent / "data" / "order_schema.csv"

PRODUCT_ROW = 9
CATEGORY_ROW = 10
COLOR_ROW = 11
SIZE_ORDER = (
    "5XS",
    "4XS",
    "3XS",
    "XXS",
    "XS",
    "S",
    "M",
    "L",
    "XL",
    "XXL",
    "3XL",
    "4XL",
    "5XL",
    "Vare uten størrelse",
)
INSERTED_SIZE_ROWS = ("5XS", "4XS")
SIZE_ROWS = {size: index + 12 for index, size in enumerate(SIZE_ORDER)}
PRODUCT_TOTAL_ROW = 26
GRAND_TOTAL_ROW = 27
PRINT_BANNER_ROW = 33
PRINT_HEADER_ROW = 34

COLOR_WORDS = ("Black", "White")
PRODUCT_CATEGORIES = {
    "wyvern kit": "Drakt",
    "wisp": "Treningsdrakt",
    "dryad": "Treningsdrakt",
    "galax": "Shorts",
    "acrux": "Shorts",
    "thames": "Bukser",
    "desna": "Bukser",
    "archen": "Bukser",
    "poseidon": "Jakke / Yttertøy",
    "fenders": "Jakke / Yttertøy",
    "artemis": "Jakke / Yttertøy",
    "anora": "Jakke / Yttertøy",
    "anduin": "Jakke / Yttertøy",
    "rivendell": "Jakke / Yttertøy",
    "northland": "Jakke / Yttertøy",
    "narvik": "Jakke / Yttertøy",
    "elbrus": "Jakke / Yttertøy",
    "fixed socks": "Sokker",
    "round socks evo": "Sokker",
    "trip": "Bag / Ryggsekk",
    "rookie": "Bag / Ryggsekk",
    "academy evo": "Bag / Ryggsekk",
    "pepper": "Caps / Lue",
    "metel": "Caps / Lue",
    "blizzard": "Caps / Lue",
    "rivet": "Annet",
    "barrier": "Annet",
    "poplar": "Annet",
}
VALID_CATEGORIES = frozenset(
    {
        "Drakt",
        "Treningsdrakt",
        "Shorts",
        "Bukser",
        "Jakke / Yttertøy",
        "Caps / Lue",
        "Sokker",
        "Bag / Ryggsekk",
        "Annet",
    }
)
# Prints on these are still made (and charged), but get no placement
# instruction: the club has no standard spot and uses the factory default.
PRINT_INSTRUCTION_SUPPRESSION_CATEGORIES = frozenset(
    {
        "Bag / Ryggsekk",
        "Shorts",
        "Sokker",
        "Bukser",
        "Caps / Lue",
        "Annet",
    }
)
TRUE_VALUES = {"yes", "true", "1", "on", "ja", "x", "selected", "black", "white"}
FALSE_VALUES = {"no", "false", "0", "off", "nei", ""}


class TransformError(ValueError):
    """Raised when source data cannot be transformed without guessing."""


FamilyRange = tuple[int, int, str]
ProductSlot = tuple[tuple[str, str, str], OrderedDict[str, int]]


@dataclass
class AggregatedOrders:
    slots: list[ProductSlot]
    print_rows: list[list[str]]
    source_total: int
    expected_print_count: int


def normalized(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip()).casefold()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_quantity(value: str, context: str) -> int:
    text = value.strip()
    if not text or text == "0":
        return 0
    if not re.fullmatch(r"[+-]?\d+", text):
        raise TransformError(
            f"{context}: quantity must be a whole integer, got {text!r}"
        )
    quantity = int(text)
    if quantity < 0:
        raise TransformError(f"{context}: quantity cannot be negative")
    return quantity


def selection_state(value: str, context: str) -> bool | None:
    text = normalized(value)
    if not text:
        return None
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    raise TransformError(f"{context}: unrecognized color selection value {value!r}")


def product_and_color(text: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    match = re.match(r"^(.*?)(?:\s+(Black|White))$", cleaned, flags=re.IGNORECASE)
    if not match:
        return cleaned, ""
    return match.group(1).strip(), match.group(2).title()


def product_category(product: str) -> str:
    category = PRODUCT_CATEGORIES.get(normalized(product))
    if category is None:
        raise TransformError(f"Unmapped product {product!r}")
    if category not in VALID_CATEGORIES:
        raise TransformError(
            f"Configured category {category!r} for product {product!r} is invalid"
        )
    return category


def standardize_size(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip().upper()
    if not text or "ONE SIZE" in text or "ONE-SIZE" in text:
        return "Vare uten størrelse"
    base = re.match(
        r"^(5XS|4XS|3XS|XXS|XS|S|M|L|XL|XXL|3XL|4XL|5XL)(?:\s*\([^)]*\))?$", text
    )
    return base.group(1) if base else "Vare uten størrelse"


def family_ranges(headers: list[str]) -> list[FamilyRange]:
    anchors = [
        (index, header[6:].strip())
        for index, header in enumerate(headers)
        if header.strip().casefold().startswith("order ")
    ]
    if not anchors:
        raise TransformError("No 'Order ' headers found in input CSV")
    return [
        (
            start,
            anchors[position + 1][0] if position + 1 < len(anchors) else len(headers),
            name,
        )
        for position, (start, name) in enumerate(anchors)
    ]


def is_customization_quantity_field(header: str) -> bool:
    field = normalized(header)
    if "quantity" not in field:
        return False
    return any(
        marker in field
        for marker in ("shirt number quantity", "initials", "back print text")
    )


def is_recognized_family_field(header: str) -> bool:
    field = normalized(header)
    return any(
        marker in field
        for marker in (
            "quantity",
            "size",
            "include number",
            "shirt number",
            "initials",
            "back print text",
            "color selection",
        )
    )


def validate_source_schema(headers: list[str]) -> list[FamilyRange]:
    families = family_ranges(headers)
    for start, end, family_name in families:
        if not family_name:
            raise TransformError("Order header must name its order family")
        family_headers = [
            header for header in headers[start + 1 : end] if header.strip()
        ]
        unknown_headers = [
            header
            for header in family_headers
            if not is_recognized_family_field(header)
        ]
        if unknown_headers:
            raise TransformError(
                f"Order {family_name}: unrecognized family field {unknown_headers[0]!r}"
            )
        if not any("quantity" in normalized(header) for header in family_headers):
            raise TransformError(
                f"Order {family_name}: missing recognizable quantity field"
            )
    return families


def family_field_indices(
    headers: list[str], start: int, end: int, keyword: str
) -> list[int]:
    return [
        index for index in range(start + 1, end) if keyword in headers[index].casefold()
    ]


def first_field(
    row: tuple[str, ...], headers: list[str], start: int, end: int, keyword: str
) -> str:
    matches = family_field_indices(headers, start, end, keyword)
    populated = [row[index].strip() for index in matches if row[index].strip()]
    if len(set(populated)) > 1:
        raise TransformError(f"conflicting {keyword} values within one order family")
    return populated[0] if populated else ""


def is_explicit_no(value: str) -> bool:
    return normalized(value) in {"no", "false", "0", "off", "nei"}


def print_instructions(fields: dict[str, str], category: str, product: str) -> str:
    if category in PRINT_INSTRUCTION_SUPPRESSION_CATEGORIES:
        return ""
    instructions = []
    if fields.get("back_text", ""):
        if normalized(product) == "wyvern kit":
            instructions.append("Navn trykkes øverst på ryggen, over tallet")
        else:
            instructions.append("Navn trykkes øverst på ryggen")
    if fields.get("initials", ""):
        instructions.append("Initialer trykkes under Kraft-logoen foran")
    return "; ".join(instructions)


def resolved_customization_quantity(
    raw_value: str | None, quantity: int, in_use: bool, context: str
) -> int:
    if raw_value is None:
        return quantity
    text = raw_value.strip()
    if not text:
        if not in_use:
            return 0
        if quantity != 1:
            raise TransformError(
                f"{context}: left blank, which is only valid when garment quantity is 1, "
                f"got {quantity}"
            )
        return quantity
    resolved = parse_quantity(text, context)
    if resolved > quantity:
        raise TransformError(f"{context}: exceeds garment quantity")
    return resolved


def add_print_rows(
    print_rows: list[list[str]],
    product: str,
    category: str,
    color: str,
    size: str,
    quantity: int,
    fields: dict[str, str],
    source_row: int,
) -> None:
    has_customization = any(fields.values())
    if not has_customization:
        return
    number_quantity = resolved_customization_quantity(
        fields.get("number_quantity"),
        quantity,
        bool(fields.get("back_number") or fields.get("front_number")),
        f"source row {source_row}, {product} Shirt Number Quantity",
    )
    initials_quantity = resolved_customization_quantity(
        fields.get("initials_quantity"),
        quantity,
        bool(fields.get("initials")),
        f"source row {source_row}, {product} Front Initials Quantity",
    )
    back_text_quantity = resolved_customization_quantity(
        fields.get("back_text_quantity"),
        quantity,
        bool(fields.get("back_text")),
        f"source row {source_row}, {product} Back Print Text Quantity",
    )
    instructions = print_instructions(fields, category, product)
    for unit in range(quantity):
        print_rows.append(
            [
                product,
                color,
                size,
                fields.get("back_text", "") if unit < back_text_quantity else "",
                fields.get("initials", "") if unit < initials_quantity else "",
                fields.get("back_number", "") if unit < number_quantity else "",
                fields.get("front_number", "") if unit < number_quantity else "",
                instructions,
            ]
        )


def customization_fields(
    row: tuple[str, ...], headers: list[str], start: int, end: int
) -> dict[str, str | None]:
    result: dict[str, str | None] = {
        "back_text": "",
        "initials": "",
        "back_number": "",
        "front_number": "",
        "number_quantity": None,
        "initials_quantity": None,
        "back_text_quantity": None,
    }
    for index in range(start + 1, end):
        header = headers[index].casefold()
        value = row[index].strip()
        if "back print text" in header and "quantity" in header:
            result["back_text_quantity"] = value
            continue
        if "initials" in header and "quantity" in header:
            result["initials_quantity"] = value
            continue
        if "shirt number quantity" in header:
            result["number_quantity"] = value
            continue
        if not value:
            continue
        if "back print text" in header:
            result["back_text"] = value
        elif "initials" in header:
            result["initials"] = value
        elif "front shirt number" in header:
            result["front_number"] = value
        elif "shirt number" in header:
            result["back_number"] = value
    # The order form asks for a single shirt number, printed on both front and back.
    if result["back_number"] and not result["front_number"]:
        result["front_number"] = result["back_number"]
    return result


def poplar_selections(
    row: tuple[str, ...], headers: list[str], start: int, end: int, source_row: int
) -> dict[str, bool | None]:
    selections: dict[str, bool | None] = {"Black": None, "White": None}
    for color in COLOR_WORDS:
        values = []
        for index in range(start + 1, end):
            header = headers[index].casefold()
            if "color selection" in header and color.casefold() in header:
                state = selection_state(
                    row[index], f"source row {source_row}, Poplar {color} selection"
                )
                if state is not None:
                    values.append(state)
        if len(set(values)) > 1:
            raise TransformError(
                f"source row {source_row}, Poplar {color}: conflicting selections"
            )
        selections[color] = values[0] if values else None
    generic = [
        row[index].strip()
        for index in range(start + 1, end)
        if "color selection" in headers[index].casefold()
        and all(
            color.casefold() not in headers[index].casefold() for color in COLOR_WORDS
        )
        and row[index].strip()
    ]
    if generic:
        listed = {
            word.title()
            for value in generic
            for word in COLOR_WORDS
            if word.casefold() in normalized(value)
        }
        if not listed:
            raise TransformError(
                f"source row {source_row}, Poplar: unrecognized color selection"
            )
        for color in COLOR_WORDS:
            if selections[color] is None:
                selections[color] = color in listed
            elif selections[color] != (color in listed):
                raise TransformError(
                    f"source row {source_row}, Poplar {color}: list and boolean selections disagree"
                )
    return selections


def _load_source(input_path: Path) -> tuple[pl.DataFrame, list[str], list[FamilyRange]]:
    source = (
        pl.scan_csv(
            input_path,
            has_header=True,
            separator=",",
            encoding="utf8",
            null_values=[],
            infer_schema=False,
            truncate_ragged_lines=False,
        )
        # Form answers often carry stray leading/trailing spaces; trim them once here.
        .with_columns(pl.all().str.strip_chars())
        .collect()
        .fill_null("")
    )
    headers = list(source.columns)
    return source, headers, validate_source_schema(headers)


def _load_template(template_path: Path) -> list[list[str]]:
    with template_path.open("r", encoding="utf-8", newline="") as template_file:
        template = list(csv.reader(template_file, delimiter=","))
    if len(template) != 33 or any(len(row) != 11 for row in template):
        raise TransformError("Template must be the expected rectangular 33 by 11 CSV")
    return template


def _aggregate_orders(
    source: pl.DataFrame, headers: list[str], families: list[FamilyRange]
) -> AggregatedOrders:
    aggregate: OrderedDict[tuple[str, str, str], OrderedDict[str, int]] = OrderedDict()
    print_rows: list[list[str]] = []
    source_total = 0
    expected_print_count = 0
    for data_index, row in enumerate(source.iter_rows()):
        source_row = data_index + 2
        for start, end, family_name in families:
            product, anchor_color = product_and_color(family_name)
            category = product_category(product)
            order_value = row[start].strip()
            quantity_columns = [
                index
                for index in family_field_indices(headers, start, end, "quantity")
                if not is_customization_quantity_field(headers[index])
            ]
            for index in quantity_columns:
                header = headers[index]
                quantity = parse_quantity(
                    row[index], f"source row {source_row}, {header}"
                )
                if not quantity:
                    continue
                if is_explicit_no(order_value):
                    raise TransformError(
                        f"source row {source_row}, {product}: positive quantity conflicts with Order value No"
                    )
                _, field_color = product_and_color(
                    re.sub(r"\s+Quantity$", "", header, flags=re.IGNORECASE)
                )
                if normalized(product) == "poplar" and not field_color:
                    raise TransformError(
                        f"source row {source_row}, Poplar: quantity field has no Black or White color"
                    )
                color = field_color or anchor_color or "Black"
                if normalized(product) == "poplar":
                    selections = poplar_selections(row, headers, start, end, source_row)
                    if selections[color] is False:
                        raise TransformError(
                            f"source row {source_row}, Poplar {color}: selected No with positive quantity"
                        )
                size = standardize_size(first_field(row, headers, start, end, "size"))
                key = (product, category, color)
                size_quantities = aggregate.setdefault(key, OrderedDict())
                size_quantities[size] = size_quantities.get(size, 0) + quantity
                source_total += quantity
                custom_fields = customization_fields(row, headers, start, end)
                if any(custom_fields.values()):
                    expected_print_count += quantity
                add_print_rows(
                    print_rows,
                    product,
                    category,
                    color,
                    size,
                    quantity,
                    custom_fields,
                    source_row,
                )
    return AggregatedOrders(
        slots=grouped_by_product(list(aggregate.items())),
        print_rows=grouped_print_rows_by_product(print_rows),
        source_total=source_total,
        expected_print_count=expected_print_count,
    )


def grouped_by_product(slots: list[ProductSlot]) -> list[ProductSlot]:
    groups: OrderedDict[str, list[ProductSlot]] = OrderedDict()
    for slot in slots:
        (product, _, _), _ = slot
        groups.setdefault(product, []).append(slot)
    return [slot for group in groups.values() for slot in group]


def grouped_print_rows_by_product(print_rows: list[list[str]]) -> list[list[str]]:
    groups: OrderedDict[str, list[list[str]]] = OrderedDict()
    for row in print_rows:
        groups.setdefault(row[0], []).append(row)
    return [row for group in groups.values() for row in group]


def _render_template(
    template: list[list[str]], orders: AggregatedOrders
) -> list[list[str]]:
    product_columns = len(orders.slots)
    output_width = max(len(template[0]), product_columns + 1)
    output = [row + [""] * (output_width - len(row)) for row in template]
    output[12:12] = [[size] + [""] * (output_width - 1) for size in INSERTED_SIZE_ROWS]
    for column_offset, ((product, category, color), size_quantities) in enumerate(
        orders.slots, start=1
    ):
        output[PRODUCT_ROW][column_offset] = product
        output[CATEGORY_ROW][column_offset] = category
        output[COLOR_ROW][column_offset] = color
        for size, quantity in size_quantities.items():
            output[SIZE_ROWS[size]][column_offset] = str(quantity)
        output[PRODUCT_TOTAL_ROW][column_offset] = str(sum(size_quantities.values()))
    output[GRAND_TOTAL_ROW][1] = str(orders.source_total)
    return (
        output[: PRINT_BANNER_ROW + 1]
        + [output[PRINT_HEADER_ROW]]
        + [row + [""] * (len(output[0]) - len(row)) for row in orders.print_rows]
    )


def _validate_output(output: list[list[str]], orders: AggregatedOrders) -> None:
    width = len(output[0])
    if any(len(row) != width for row in output):
        raise TransformError("Output is not rectangular")
    grid_total = sum(
        int(output[row_index][column])
        for row_index in SIZE_ROWS.values()
        for column in range(1, len(orders.slots) + 1)
        if output[row_index][column]
    )
    if (
        grid_total != orders.source_total
        or sum(sum(size_quantities.values()) for _, size_quantities in orders.slots)
        != orders.source_total
    ):
        raise TransformError("Quantity conservation check failed")
    if len(orders.print_rows) != orders.expected_print_count:
        raise TransformError("Print row count check failed")


def _publish_output(
    output: list[list[str]], output_path: Path, before_hashes: dict[Path, str]
) -> None:
    width = len(output[0])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            csv.writer(temporary, delimiter=",", lineterminator="\n").writerows(output)
        with open(temporary_name, "r", encoding="utf-8", newline="") as check_file:
            written = list(csv.reader(check_file, delimiter=","))
        if not written or any(len(row) != width for row in written):
            raise TransformError("Temporary output validation failed")
        if any(file_hash(path) != digest for path, digest in before_hashes.items()):
            raise TransformError("Input or template changed during transformation")
        os.replace(temporary_name, output_path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def transform(
    input_path: Path, template_path: Path, output_path: Path, category: str
) -> tuple[int, int]:
    input_path = input_path.resolve()
    template_path = template_path.resolve()
    output_path = output_path.resolve()
    if output_path in (input_path, template_path):
        raise ValueError(
            "Output path must not alias the apparel input or template path"
        )
    del category
    before_hashes = {path: file_hash(path) for path in (input_path, template_path)}
    source, headers, families = _load_source(input_path)
    template = _load_template(template_path)
    orders = _aggregate_orders(source, headers, families)
    output = _render_template(template, orders)
    _validate_output(output, orders)
    _publish_output(output, output_path, before_hashes)
    return orders.source_total, len(orders.print_rows)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "input_path", nargs="?", help="Form answers CSV (positional form of --input)"
    )
    parser.add_argument(
        "template_path",
        nargs="?",
        help="Order sheet template (positional form of --template)",
    )
    parser.add_argument(
        "output_path",
        nargs="?",
        help="Where to write the result (positional form of --output)",
    )
    parser.add_argument("--input", help="Form answers CSV (default: apparel_order.csv)")
    parser.add_argument(
        "--template",
        help="Order sheet template (default: the bundled order_schema.csv)",
    )
    parser.add_argument(
        "--output",
        help="Where to write the result (default: populated_order_schema.csv)",
    )
    parser.add_argument(
        "--category",
        default="Apparel",
        help="Deprecated and ignored; product categories are resolved from the source product",
    )


def run(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    positional_paths = (
        arguments.input_path,
        arguments.template_path,
        arguments.output_path,
    )
    if any(positional_paths) and not all(positional_paths):
        parser.error(
            "positional paths require input_name, template_file, and output_name"
        )
    option_paths = (arguments.input, arguments.template, arguments.output)
    if any(
        positional_path is not None and option_path is not None
        for positional_path, option_path in zip(positional_paths, option_paths)
    ):
        parser.error(
            "a positional path cannot be combined with its matching long option"
        )
    input_name, template_file, output_name = (
        positional_path or option_path or default
        for positional_path, option_path, default in zip(
            positional_paths,
            option_paths,
            ("apparel_order.csv", DEFAULT_TEMPLATE, "populated_order_schema.csv"),
        )
    )
    try:
        quantity, print_count = transform(
            Path(input_name),
            Path(template_file),
            Path(output_name),
            arguments.category,
        )
    except (OSError, ValueError, pl.exceptions.PolarsError, TransformError) as error:
        raise SystemExit(f"Error: {error}")
    print(f"Wrote {output_name}: {quantity} garments, {print_count} print rows")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    run(parser.parse_args(argv), parser)
