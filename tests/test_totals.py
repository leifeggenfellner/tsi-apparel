import argparse
import csv
from decimal import Decimal
from pathlib import Path

import pytest

from tsi_apparel import cli, totals

CONTACT_HEADERS = [
    "Submission ID",
    "Respondent ID",
    "Submitted at",
    "Full Name",
    "Email",
    "Phone Number",
]
ORDER_HEADERS = [
    "Order Round Socks Evo White",
    "Round Socks Evo White Size",
    "Round Socks Evo White Quantity",
    "Order Rookie",
    "Rookie Size",
    "Rookie Black Quantity",
]


def person(name: str, socks: int, rookie_size: str = "", rookies: int = 0) -> list:
    email = name.split()[0].lower() + "@example.com"
    return [
        "S",
        "R",
        "t",
        name,
        email,
        "4700000001",
        "Yes" if socks else "No",
        "M",
        str(socks or ""),
        "Yes" if rookies else "No",
        rookie_size,
        str(rookies or ""),
    ]


def write_orders(path: Path, people: list[list]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as file:
        csv.writer(file, lineterminator="\n").writerows(
            [CONTACT_HEADERS + ORDER_HEADERS, *people]
        )
    return path


@pytest.fixture
def orders(tmp_path: Path) -> Path:
    # Socks are 94.50 kr each, a size L Rookie 549.50 kr.
    return write_orders(
        tmp_path / "orders.csv",
        [
            person("Ola Nordmann", 2),
            person("Kari Nordmann", 1),
            person("Bob Smith", 2),
            person("Alice Smith", 1, "L", 1),
            person("Per Nordmann", 0),
        ],
    )


def test_totals_groups_people_by_amount(
    orders: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["totals", "--input", str(orders)])

    out = capsys.readouterr().out
    assert out.startswith("4 people, 3 different amounts:\n")
    rows = [line.split() for line in out.splitlines() if line.startswith("  ")]
    assert rows == [
        ["Amount", "People"],
        ["94.50", "kr", "1"],
        ["189.00", "kr", "2"],
        ["644.00", "kr", "1"],
    ]
    assert "Total: 1 116.50 kr" in out
    assert "Nordmann" not in out and "@" not in out


def test_totals_counts_unpriced_orders_separately(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    orders = write_orders(
        tmp_path / "orders.csv",
        [person("Ola Nordmann", 2), person("Bob Smith", 1, "", 1)],
    )

    cli.main(["totals", "--input", str(orders)])

    out = capsys.readouterr().out
    assert out.startswith("1 person, 1 amount:\n")
    assert "Total: 189.00 kr" in out
    assert "1 more person has an item with no price" in out
    assert "apparel totals --unpriced" in out


def test_totals_with_nobody_ordering(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    orders = write_orders(tmp_path / "orders.csv", [person("Ola Nordmann", 0)])

    cli.main(["totals", "--input", str(orders)])

    assert capsys.readouterr().out == "Nobody has ordered anything.\n"


def test_totals_match_lookup(orders: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["lookup", "--input", str(orders), "alice"])
    assert "Total:    644.00 kr" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("700", "700"),
        ("700.00", "700.00"),
        ("700,50", "700.50"),
        ("1200", "1200"),
        ("1 200", "1200"),
        ("1 200,00 kr", "1200.00"),
        (" 1 200.00 KR ", "1200.00"),
    ],
)
def test_parse_amount(text: str, expected: str) -> None:
    assert totals.parse_amount(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["", "kr", "abc", "1,200.00", "-5", "nan"])
def test_parse_amount_rejects_non_amounts(text: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        totals.parse_amount(text)


def test_amount_lists_people_who_owe_it(
    orders: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["totals", "--input", str(orders), "--amount", "189,00 kr"])

    out = capsys.readouterr().out
    assert out.startswith("2 people owe 189.00 kr:\n")
    people = [line.split() for line in out.splitlines() if line.startswith("  ")]
    assert people == [
        ["Bob", "Smith", "bob@example.com", "4700000001"],
        ["Ola", "Nordmann", "ola@example.com", "4700000001"],
    ]


def test_amount_nobody_owes_shows_closest_and_fails(
    orders: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["totals", "--input", str(orders), "--amount", "190"])

    assert error.value.code == 1
    assert capsys.readouterr().out == (
        "Nobody owes 190.00 kr.\nClosest amounts owed: 94.50 kr, 189.00 kr, 644.00 kr\n"
    )


def test_amount_rejects_bad_input(
    orders: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["totals", "--input", str(orders), "--amount", "lots"])
    assert error.value.code == 2
    assert "not an amount in kr" in capsys.readouterr().err


def test_unpriced_lists_people_and_items(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    orders = write_orders(
        tmp_path / "orders.csv",
        [
            person("Ola Nordmann", 2),
            person("Bob Smith", 1, "", 1),
            person("Bob Smith", 0, "", 2),
        ],
    )

    cli.main(["totals", "--input", str(orders), "--unpriced"])

    out = capsys.readouterr().out
    assert out.startswith("2 people have an item with no price:\n")
    assert out.count("no price for Rookie (no size)") == 2
    assert "Ola" not in out


def test_unpriced_when_everything_has_a_price(
    orders: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["totals", "--input", str(orders), "--unpriced"])
    assert capsys.readouterr().out == "Everyone's order has a price.\n"


def test_amount_and_unpriced_are_exclusive(orders: Path) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["totals", "--input", str(orders), "--amount", "1", "--unpriced"])
    assert error.value.code == 2
