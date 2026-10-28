import csv
from pathlib import Path

import pytest

from tsi_apparel import cli

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


def test_totals_with_nobody_ordering(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    orders = write_orders(tmp_path / "orders.csv", [person("Ola Nordmann", 0)])

    cli.main(["totals", "--input", str(orders)])

    assert capsys.readouterr().out == "Nobody has ordered anything.\n"


def test_totals_match_lookup(orders: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["lookup", "--input", str(orders), "alice"])
    assert "Total:    644.00 kr" in capsys.readouterr().out
