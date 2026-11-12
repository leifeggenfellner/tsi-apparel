"""Write an order into the supplier's Excel order form (Macron's «Ordremal»)."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Callable
from copy import copy
from pathlib import Path
from typing import TYPE_CHECKING

import openpyxl
from openpyxl.formatting.formatting import ConditionalFormattingList
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.cell_range import CellRange, MultiCellRange

if TYPE_CHECKING:
    from openpyxl.worksheet.worksheet import Worksheet

    from .transform import AggregatedOrders

TEMPLATE = Path(__file__).parent / "data" / "order_form.xlsx"
SHEET = "Ordremal"

PRODUCT_ROW = 10
CATEGORY_ROW = 11
COLOR_ROW = 12
SIZE_ROWS = {
    size: row
    for row, size in enumerate(
        (
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
        ),
        start=13,
    )
}
PRODUCT_TOTAL_ROW = 25
GRAND_TOTAL_ROW = 26
PRINT_HEADER_ROW = 33
# The template ends with two blank print rows, one for each alternating style.
PRINT_STYLE_ROWS = (34, 35)
FIRST_PRODUCT_COLUMN = 2
TEMPLATE_PRODUCT_COLUMNS = 8
PRODUCT_PLACEHOLDER = "← Produktnavn"
# The form is Norwegian; products keep the supplier's "TSI <model>" naming.
COLOR_NAMES = {"Black": "Svart", "White": "Hvit"}


class OrderFormError(ValueError):
    """Raised when an order does not fit the order form template."""


def product_label(product: str) -> str:
    return "TSI " + re.sub(r"\s+Kit$", "", product)


def cell_number(value: str) -> int | str:
    """Numbers as numbers, like the form; keep leading zeros as text."""
    if value.isdigit() and not (len(value) > 1 and value.startswith("0")):
        return int(value)
    return value


def _check_template(ws: Worksheet) -> None:
    labels = {PRODUCT_ROW: "Produkt", PRINT_HEADER_ROW: "Produkt"}
    labels |= {row: size for size, row in SIZE_ROWS.items()}
    for row, label in labels.items():
        if str(ws.cell(row, 1).value or "").strip() != label:
            raise OrderFormError(
                f"Order form template: expected {label!r} in A{row}, "
                f"got {ws.cell(row, 1).value!r}"
            )


def _add_product_columns(ws: Worksheet, extra: int) -> None:
    """Widen the product grid by ``extra`` columns, styled like the last one."""
    last = FIRST_PRODUCT_COLUMN + TEMPLATE_PRODUCT_COLUMNS - 1
    merged = [CellRange(str(cells)) for cells in ws.merged_cells.ranges]
    for cells in merged:
        ws.unmerge_cells(cells.coord)
    ws.insert_cols(last + 1, extra)
    for cells in merged:
        if cells.max_col >= last:
            cells.expand(right=extra)
        ws.merge_cells(cells.coord)
    for row in range(1, ws.max_row + 1):
        source = ws.cell(row, last)
        for column in range(last + 1, last + extra + 1):
            ws.cell(row, column)._style = copy(source._style)
    new_last = get_column_letter(last + extra)
    for column in range(last + 1, last + extra + 1):
        letter = get_column_letter(column)
        ws.cell(PRODUCT_ROW, column).value = PRODUCT_PLACEHOLDER
        ws.cell(
            PRODUCT_TOTAL_ROW, column
        ).value = (
            f"=SUM({letter}{min(SIZE_ROWS.values())}:{letter}{max(SIZE_ROWS.values())})"
        )
    ws.cell(
        GRAND_TOTAL_ROW, FIRST_PRODUCT_COLUMN
    ).value = f"=SUM(B{PRODUCT_TOTAL_ROW}:{new_last}{PRODUCT_TOTAL_ROW})"

    def widened(ranges: str) -> str:
        result = []
        for cells in ranges.split():
            cell_range = CellRange(cells)
            if cell_range.max_col == last:
                cell_range.expand(right=extra)
            result.append(cell_range.coord)
        return " ".join(result)

    for validation in ws.data_validations.dataValidation:
        validation.sqref = MultiCellRange(widened(str(validation.sqref)))
    formatting = ws.conditional_formatting
    ws.conditional_formatting = ConditionalFormattingList()
    for entry in formatting:
        for rule in entry.rules:
            ws.conditional_formatting.add(widened(str(entry.sqref)), rule)


def _fill_products(ws: Worksheet, orders: AggregatedOrders) -> None:
    extra = len(orders.slots) - TEMPLATE_PRODUCT_COLUMNS
    if extra > 0:
        _add_product_columns(ws, extra)
    for column in range(
        FIRST_PRODUCT_COLUMN + len(orders.slots),
        FIRST_PRODUCT_COLUMN + TEMPLATE_PRODUCT_COLUMNS,
    ):
        # Unused columns stay blank, so the form doesn't flag them as missing a color.
        ws.cell(PRODUCT_ROW, column).value = None
    for column, ((product, category, color), size_quantities) in enumerate(
        orders.slots, start=FIRST_PRODUCT_COLUMN
    ):
        ws.cell(PRODUCT_ROW, column).value = product_label(product)
        ws.cell(CATEGORY_ROW, column).value = category
        ws.cell(COLOR_ROW, column).value = COLOR_NAMES.get(color, color)
        for size, quantity in size_quantities.items():
            if size not in SIZE_ROWS:
                raise OrderFormError(
                    f"{product}: size {size} has no row on the order form; "
                    "write a .csv instead"
                )
            ws.cell(SIZE_ROWS[size], column).value = quantity


def _fill_prints(ws: Worksheet, orders: AggregatedOrders) -> None:
    styles = [
        (ws.row_dimensions[row].height, [copy(cell._style) for cell in ws[row]])
        for row in PRINT_STYLE_ROWS
    ]
    first = PRINT_STYLE_ROWS[0]
    for offset, print_row in enumerate(orders.print_rows):
        row = first + offset
        height, row_styles = styles[offset % len(styles)]
        ws.row_dimensions[row].height = height
        for column, style in enumerate(row_styles, start=1):
            ws.cell(row, column)._style = copy(style)
        product, color, size, *prints = print_row[:8]
        values = [product_label(product), COLOR_NAMES.get(color, color), size]
        values += [cell_number(value) for value in prints]
        for column, value in enumerate(values, start=1):
            ws.cell(row, column).value = value if value != "" else None
    unused = first + len(orders.print_rows)
    if unused <= ws.max_row:
        ws.delete_rows(unused, ws.max_row - unused + 1)


def _check_written(path: Path, orders: AggregatedOrders) -> None:
    ws = openpyxl.load_workbook(path)[SHEET]
    columns = range(FIRST_PRODUCT_COLUMN, FIRST_PRODUCT_COLUMN + len(orders.slots))
    grid_total = sum(
        ws.cell(row, column).value or 0
        for row in SIZE_ROWS.values()
        for column in columns
    )
    if grid_total != orders.source_total:
        raise OrderFormError("Quantity conservation check failed")
    print_count = ws.max_row - PRINT_HEADER_ROW
    if print_count != orders.expected_print_count:
        raise OrderFormError("Print row count check failed")


def publish(
    orders: AggregatedOrders,
    template_path: Path,
    output_path: Path,
    unchanged: Callable[[], None],
) -> None:
    """Fill the template and write it atomically to ``output_path``.

    ``unchanged`` is called just before publishing and must raise if the
    inputs changed while the order was being written.
    """
    workbook = openpyxl.load_workbook(template_path)
    if SHEET not in workbook.sheetnames:
        raise OrderFormError(f"Order form template has no {SHEET!r} sheet")
    ws = workbook[SHEET]
    _check_template(ws)
    _fill_products(ws, orders)
    _fill_prints(ws, orders)
    workbook.active = workbook.sheetnames.index(SHEET)
    # openpyxl can't compute the totals; have Excel do it when the file opens.
    workbook.calculation.fullCalcOnLoad = True
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp.xlsx",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
        workbook.save(temporary_name)
        _check_written(Path(temporary_name), orders)
        unchanged()
        os.replace(temporary_name, output_path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)
