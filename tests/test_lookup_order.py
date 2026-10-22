import csv
import sys
from pathlib import Path

import pytest

import lookup_order as app
from transform_apparel_orders import family_ranges


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        csv.writer(file, lineterminator="\n").writerows(rows)


CONTACT_HEADERS = ["Submission ID", "Respondent ID", "Submitted at", "Full Name", "Email", "Phone Number"]
WISP_FAMILY_HEADERS = [
    "Order Wisp Black",
    "Wisp Black Quantity",
    "Wisp Black Size",
    "Wisp Back Print Text",
    "Wisp Initials",
    "Wisp Shirt Number",
    "Wisp Front Shirt Number",
    "Wisp Shirt Number Quantity",
]
POPLAR_FAMILY_HEADERS = [
    "Order Poplar",
    "Poplar Black Quantity",
    "Poplar White Quantity",
    "Poplar Size",
]


def make_person_csv(path: Path, rows: list[list[str]], extra_headers: list[str]) -> None:
    write_csv(path, [CONTACT_HEADERS + extra_headers, *rows])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Søreide", "soreide"),
        ("BLÅBÆRSYLTETØY", "blabaersyltetoy"),
        ("  Multiple   Spaces ", "multiple spaces"),
        ("café", "cafe"),
        ("Berg", "berg"),
    ],
)
def test_fold(value: str, expected: str) -> None:
    assert app.fold(value) == expected


def test_order_lines_extracts_single_family_line() -> None:
    headers = CONTACT_HEADERS + WISP_FAMILY_HEADERS
    row = (
        "S1", "R1", "2026-09-17 10:00:00", "Ola Fjell Berg", "ola@example.com", "4700000000",
        "yes", "2", "M", "BACK", "IN", "8", "9", "1",
    )
    from transform_apparel_orders import family_ranges

    lines = app.order_lines(row, headers, family_ranges(headers))

    assert lines == [
        {
            "product": "Wisp",
            "category": "Treningsdrakt",
            "color": "Black",
            "size": "M",
            "quantity": 2,
            "initials": "IN",
            "back_text": "BACK",
            "back_number": "8",
            "front_number": "9",
            "name_prints": 2,
            "initials_prints": 2,
            "back_number_prints": 1,
            "front_number_prints": 1,
        }
    ]


def test_order_lines_handles_poplar_dual_color_columns() -> None:
    headers = CONTACT_HEADERS + POPLAR_FAMILY_HEADERS
    row = ("S1", "R1", "2026-09-17 10:00:00", "Someone", "s@example.com", "1", "yes", "1", "2", "M")
    from transform_apparel_orders import family_ranges

    lines = app.order_lines(row, headers, family_ranges(headers))

    assert {(line["color"], line["quantity"]) for line in lines} == {("Black", 1), ("White", 2)}
    assert all(line["name_prints"] == line["initials_prints"] == 0 for line in lines)
    assert all(line["product"] == "Poplar" and line["category"] == "Annet" for line in lines)


def test_order_lines_skips_zero_quantity_families() -> None:
    headers = CONTACT_HEADERS + WISP_FAMILY_HEADERS
    row = ("S1", "R1", "2026-09-17 10:00:00", "Nobody", "n@example.com", "1", "no", "", "", "", "", "", "", "")
    from transform_apparel_orders import family_ranges

    assert app.order_lines(row, headers, family_ranges(headers)) == []


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("soreide", True),
        ("SØREIDE", True),
        ("kare.soreide@example.com", True),
        ("4700000002", True),
        ("nobody", False),
    ],
)
def test_matches_query_checks_name_email_and_phone(query: str, expected: bool) -> None:
    headers = CONTACT_HEADERS + WISP_FAMILY_HEADERS
    row = (
        "S1", "R1", "2026-09-25 20:52:25", "Kåre Søreide", "kare.soreide@example.com",
        "4700000002", "no", "", "", "", "", "", "", "",
    )
    assert app.matches_query(row, headers, query) is expected


def test_print_order_reports_no_items_when_no_lines(capsys: pytest.CaptureFixture[str]) -> None:
    headers = CONTACT_HEADERS + WISP_FAMILY_HEADERS
    row = ("S1", "R1", "2026-09-17 10:00:00", "Nobody", "n@example.com", "1", "no", "", "", "", "", "", "", "")

    app.print_order(row, headers, [])

    out = capsys.readouterr().out
    assert "Nobody" in out
    assert "(no items ordered)" in out


def test_print_order_lists_items_and_total(capsys: pytest.CaptureFixture[str]) -> None:
    headers = CONTACT_HEADERS + WISP_FAMILY_HEADERS
    row = (
        "S1", "R1", "2026-09-17 21:36:29", "Ola Fjell Berg", "ola@example.com",
        "4700000001", "yes", "2", "M", "BACK", "IN", "8", "9", "1",
    )
    lines = [
        {
            "product": "Wisp",
            "category": "Treningsdrakt",
            "color": "Black",
            "size": "M",
            "quantity": 2,
            "initials": "IN",
            "back_text": "BACK",
            "back_number": "8",
            "front_number": "9",
        }
    ]

    app.print_order(row, headers, lines)

    out = capsys.readouterr().out
    assert "Ola Fjell Berg" in out
    assert "4700000001" in out
    assert "Wisp" in out and "Black" in out and "M" in out
    assert "Total garments: 2" in out


def test_search_reports_no_match(capsys: pytest.CaptureFixture[str]) -> None:
    headers = CONTACT_HEADERS + WISP_FAMILY_HEADERS
    rows = [("S1", "R1", "t", "Someone Else", "e@example.com", "1", "no", "", "", "", "", "", "", "")]
    from transform_apparel_orders import family_ranges

    matched = app.search("Kristoffer Nordmann", rows, headers, family_ranges(headers))

    out = capsys.readouterr().out
    assert matched == 0
    assert 'No orders found matching "Kristoffer Nordmann"' in out


def test_search_reports_multiple_matches(capsys: pytest.CaptureFixture[str]) -> None:
    headers = CONTACT_HEADERS + WISP_FAMILY_HEADERS
    rows = [
        ("S1", "R1", "t1", "Kari Bergheim Lien", "a@example.com", "1", "no", "", "", "", "", "", "", ""),
        ("S2", "R2", "t2", "Ola Fjell Berg", "b@example.com", "2", "yes", "1", "M", "", "", "", "", ""),
    ]
    from transform_apparel_orders import family_ranges

    matched = app.search("berg", rows, headers, family_ranges(headers))

    out = capsys.readouterr().out
    assert matched == 2
    assert "2 match(es)" in out
    assert "Kari Bergheim Lien" in out
    assert "Ola Fjell Berg" in out


def test_main_one_shot_query_finds_person(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "orders.csv"
    make_person_csv(
        source,
        [
            ("S1", "R1", "2026-09-25 20:52:25", "Kåre Søreide", "kare@example.com", "111", "yes", "1", "L", "Søreide", "KS", "9", "", ""),
        ],
        WISP_FAMILY_HEADERS,
    )
    monkeypatch.setattr(sys, "argv", ["lookup_order.py", "--input", str(source), "soreide"])

    app.main()

    out = capsys.readouterr().out
    assert "Kåre Søreide" in out
    assert "Total garments: 1" in out


def test_main_one_shot_query_reports_no_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "orders.csv"
    make_person_csv(
        source,
        [("S1", "R1", "t", "Someone Else", "e@example.com", "1", "no", "", "", "", "", "", "", "")],
        WISP_FAMILY_HEADERS,
    )
    monkeypatch.setattr(sys, "argv", ["lookup_order.py", "--input", str(source), "Kristoffer Nordmann"])

    app.main()

    out = capsys.readouterr().out
    assert 'No orders found matching "Kristoffer Nordmann"' in out


def test_main_interactive_loop_reads_until_blank_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "orders.csv"
    make_person_csv(
        source,
        [
            ("S1", "R1", "t", "Ola Fjell Berg", "n@example.com", "1", "yes", "1", "M", "", "", "", "", ""),
        ],
        WISP_FAMILY_HEADERS,
    )
    monkeypatch.setattr(sys, "argv", ["lookup_order.py", "--input", str(source)])
    responses = iter(["berg", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))

    app.main()

    out = capsys.readouterr().out
    assert "Order lookup" in out
    assert "Ola Fjell Berg" in out


def test_main_interactive_loop_exits_on_keyboard_interrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "orders.csv"
    make_person_csv(source, [], WISP_FAMILY_HEADERS)
    monkeypatch.setattr(sys, "argv", ["lookup_order.py", "--input", str(source)])

    def raise_interrupt(prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", raise_interrupt)

    app.main()

    assert "Order lookup" in capsys.readouterr().out


def test_print_order_shows_discounted_clothing_and_print_costs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    headers = CONTACT_HEADERS + WISP_FAMILY_HEADERS
    row = (
        "S1", "R1", "2026-09-17 21:36:29", "Ola Fjell Berg", "ola@example.com",
        "4700000001", "yes", "2", "M", "BACK", "IN", "8", "", "1",
    )
    lines = app.order_lines(row, headers, family_ranges(headers))

    app.print_order(row, headers, lines)

    out = capsys.readouterr().out
    # 2 x Wisp at 669 / 2 = 669.00; 2 names, 2 initials, 1 front + 1 back number.
    assert "Clothing: 669.00 kr" in out
    assert "Prints:   378.00 kr" in out
    assert "Total:    1 047.00 kr" in out


def test_print_order_can_exclude_print_costs_or_hide_prices(
    capsys: pytest.CaptureFixture[str],
) -> None:
    headers = CONTACT_HEADERS + WISP_FAMILY_HEADERS
    row = (
        "S1", "R1", "t", "Someone", "s@example.com", "1", "yes", "1", "M", "BACK", "", "", "", "",
    )
    lines = app.order_lines(row, headers, family_ranges(headers))

    app.print_order(row, headers, lines, include_print_costs=False)
    out = capsys.readouterr().out
    assert "Prints:" not in out
    assert "Total:    334.50 kr" in out

    app.print_order(row, headers, lines, show_prices=False)
    out = capsys.readouterr().out
    assert "kr" not in out and "Total garments: 1" in out
