import csv
from pathlib import Path

import openpyxl
import pytest

from tsi_apparel import order_form, transform

ROSTER = [
    [
        "Name",
        "TSI Poseidon",
        "TSI Wyvern BLK",
        "Size",
        "Initials",
        "Back Print",
        "Number",
        "Notes",
    ],
    ["Ola Nordmann", "1", "0", "L", "ON", "Trener", "", "To linjer"],
    ["Kari Nordmann", "0", "1", "M", "", "Nordmann", "07", ""],
    ["Bob Smith", "0", "1", "XL", "", "Smith", "9", ""],
    ["Alice Smith", "1", "0", "S", "", "", "", ""],
]


def convert(tmp_path: Path, rows: list[list[str]], name: str = "order.xlsx") -> Path:
    source = tmp_path / "roster.csv"
    with source.open("w", encoding="utf-8", newline="") as file:
        csv.writer(file, lineterminator="\n").writerows(rows)
    output = tmp_path / name
    transform.transform(source, order_form.TEMPLATE, output, "Apparel")
    return output


def sheet(path: Path):
    return openpyxl.load_workbook(path)[order_form.SHEET]


def test_bundled_template_is_blank() -> None:
    ws = sheet(order_form.TEMPLATE)
    order_form._check_template(ws)
    for coord in ("B3", "E3", "B4", "B5", "B6", "B7", "B30"):
        assert ws[coord].value is None
    assert ws.max_row == order_form.PRINT_STYLE_ROWS[-1]
    assert all(
        cell.value is None for row in order_form.PRINT_STYLE_ROWS for cell in ws[row]
    )


def test_writes_products_and_prints_in_the_form_layout(tmp_path: Path) -> None:
    ws = sheet(convert(tmp_path, ROSTER))
    assert [ws.cell(10, column).value for column in range(1, 5)] == [
        "Produkt",
        "TSI Poseidon",
        "TSI Wyvern",
        None,
    ]
    assert ws["B11"].value == "Jakke / Yttertøy"
    assert ws["C12"].value == "Svart"
    assert ws["B18"].value == 1 and ws["B16"].value == 1
    assert ws["B25"].value == "=SUM(B13:B24)"
    assert ws["B26"].value == "=SUM(B25:I25)"
    # The order details in rows 3-7 are left for the person placing the order.
    assert all(ws.cell(row, 2).value is None for row in range(3, 8))
    assert [[cell.value for cell in row[:8]] for row in ws.iter_rows(min_row=34)] == [
        ["TSI Poseidon", "Svart", "L", "Trener", "ON", None, None, "To linjer"],
        ["TSI Wyvern", "Svart", "M", "Nordmann", None, "07", "07", None],
        ["TSI Wyvern", "Svart", "XL", "Smith", None, 9, 9, None],
    ]
    fills = [ws.cell(row, 1).fill.fgColor.rgb for row in (34, 35, 36)]
    assert fills[0] == fills[2] != fills[1]


def test_widens_the_grid_for_more_than_eight_products(tmp_path: Path) -> None:
    products = ["Poseidon", "Fenders", "Artemis", "Anora", "Anduin"]
    products += ["Rivendell", "Northland", "Narvik", "Elbrus", "Wisp"]
    rows = [["Name", *(f"TSI {p}" for p in products), "Size"]]
    rows += [
        [f"Ola Nordmann {n}", *("1" if i == n else "0" for i in range(10)), "M"]
        for n in range(10)
    ]
    ws = sheet(convert(tmp_path, rows))
    assert ws.cell(10, 11).value == "TSI Wisp"
    assert ws.cell(10, 13).value == "Kommentar"
    assert ws["K25"].value == "=SUM(K13:K24)"
    assert ws["B26"].value == "=SUM(B25:K25)"
    assert "A1:M1" in {str(cells) for cells in ws.merged_cells.ranges}
    assert ws["K10"].fill.fgColor.rgb == ws["B10"].fill.fgColor.rgb
    assert ws.max_row == 33


def test_rejects_sizes_missing_from_the_form(tmp_path: Path) -> None:
    rows = [ROSTER[0], ["Ola Nordmann", "1", "0", "5XS", "", "", "", ""]]
    with pytest.raises(order_form.OrderFormError, match="5XS"):
        convert(tmp_path, rows)
    assert not (tmp_path / "order.xlsx").exists()


def test_convert_picks_the_xlsx_template_for_xlsx_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tsi_apparel import cli

    source = tmp_path / "roster.csv"
    with source.open("w", encoding="utf-8", newline="") as file:
        csv.writer(file, lineterminator="\n").writerows(ROSTER)
    monkeypatch.chdir(tmp_path)
    cli.main(["convert", "--input", str(source), "--output", "order.xlsx"])
    assert sheet(tmp_path / "order.xlsx")["B10"].value == "TSI Poseidon"
