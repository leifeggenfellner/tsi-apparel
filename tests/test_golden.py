"""Golden test: lock in what convert, lookup and totals print for one order.

The answer sheet below follows today's form layout, column for column, with
placeholder people. It covers every product, both Wyvern colors, Poplar's color
selection, size variants, every print type and partial print quantities.

Any change in output fails the test. When a change is intentional, rewrite the
golden files and review their diff before committing:

    UPDATE_GOLDEN=1 pytest tests/test_golden.py
"""

import csv
import os
from pathlib import Path

import pytest

from tsi_apparel import cli

GOLDEN_DIR = Path(__file__).parent / "golden"
UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"

FORM_HEADERS = [
    "Submission ID",
    "Respondent ID",
    "Submitted at",
    "Full Name",
    "Email",
    "Phone Number",
    "Order Wyvern Kit Black",
    "Wyvern Kit Black Size",
    "Wyvern Kit Black Quantity",
    "Wyvern Kit Black Shirt Number",
    "Wyvern Kit Black Shirt Number Quantity",
    "Wyvern Kit Black Front Initials",
    "Wyvern Kit Black Front Initials Quantity",
    "Wyvern Kit Black Back Print Text",
    "Wyvern Kit Black Back Print Text Quantity",
    "Order Wyvern Kit White",
    "Wyvern Kit White Size",
    "Wyvern Kit White Quantity",
    "Wyvern Kit White Shirt Number",
    "Wyvern Kit White Shirt Number Quantity",
    "Wyvern Kit White Front Initials",
    "Wyvern Kit White Front Initials Quantity",
    "Wyvern Kit White Back Print Text",
    "Wyvern Kit White Back Print Text Quantity",
    "Order Wisp",
    "Wisp Size",
    "Wisp Black Quantity",
    "Wisp Black Front Initials",
    "Wisp Black Front Initials Quantity",
    "Wisp Back Print Text",
    "Wisp Black Back Print Text Quantity",
    "Order Dryad",
    "Dryad Size",
    "Dryad Black Quantity",
    "Dryad Front Initials",
    "Dryad Black Front Initials Quantity",
    "Dryad Back Print Text",
    "Dryad Black Back Print Text Quantity",
    "Order Galax",
    "Galax Size",
    "Galax Shorts Quantity",
    "Galax Initials",
    "Galax Black Initials Quantity",
    "Order Acrux",
    "Acrux Size",
    "Acrux Quantity",
    "Acrux Initials",
    "Acrux Initials Quantity",
    "Order Round Socks Evo White",
    "Round Socks Evo White Size",
    "Round Socks Evo White Quantity",
    "Order Fixed Socks White",
    "Fixed Socks White Size",
    "Fixed Socks White Quantity",
    "Order Poseidon",
    "Poseidon Size",
    "Poseidon Black Quantity",
    "Poseidon Front Initials",
    "Poseidon Front Initials Quantity",
    "Poseidon Back Print Text",
    "Poseidon Back Print Text Quantity",
    "Order Artemis",
    "Artemis Size",
    "Artemis Black Quantity",
    "Artemis Front Initials",
    "Artemis Front Initials Quantity",
    "Artemis Back Print Text",
    "Artemis Back Print Text Quantity",
    "Order Anduin",
    "Anduin Size",
    "Anduin Black Quantity",
    "Anduin Front Initials",
    "Anduin Front Initials Quantity",
    "Anduin Back Print Text",
    "Anduin Back Print Text Quantity",
    "Order Anora",
    "Anora Size",
    "Anora Black Quantity",
    "Anora Front Initials",
    "Anora Front Initials Quantity",
    "Anora Back Print Text",
    "Anora Back Print Text Quantity",
    "Order Fenders",
    "Fenders Size",
    "Fenders Black Quantity",
    "Fenders Front Initials",
    "Fenders Front Initials Quantity",
    "Fenders Back Print Text",
    "Fenders Back Print Text Quantity",
    "Order Archen",
    "Archen Size",
    "Archen Black Quantity",
    "Archen Initials",
    "Archen Initials Quantity",
    "Order Desna",
    "Size",
    "Desna Black Quantity",
    "Desna Initials",
    "Desna Initials Quantity",
    "Order Thames",
    "Thames Size",
    "Thames Black Quantity",
    "Thames Initials",
    "Thames Initials Quantity",
    "Order Poplar",
    "Poplar Size",
    "Poplar Color Selection",
    "Poplar Color Selection (Black)",
    "Poplar Color Selection (White)",
    "Poplar Black Quantity",
    "Poplar White Quantity",
    "Order Northland",
    "Northland Jacket Size",
    "Northland Black Quantity",
    "Northland Front Initials",
    "Northland Front Initials Quantity",
    "Northland Back Print Text",
    "Northland Back Print Text Quantity",
    "Order Narvik",
    "Narvik Padded Jacket Size",
    "Narvik Black Quantity",
    "Narvik Front Initials",
    "Narvik Front Initials Quantity",
    "Narvik Back Print Text",
    "Narvik Back Print Text Quantity",
    "Order Rivendell",
    "Rivendell Size",
    "Rivendell Black Quantity",
    "Rivendell Front Initials",
    "Rivendell Front Initials Quantity",
    "Rivendell Back Print Text",
    "Rivendell Back Print Text Quantity",
    "Order Elbrus",
    "Elbrus Black Size",
    "Elbrus Black Quantity",
    "Elbrus Front Initials",
    "Elbrus Front Initials Quantity",
    "Elbrus Back Print Text",
    "Elbrus Back Print Text Quantity",
    "Order Pepper",
    "Pepper Black Quantity",
    "Pepper Initials",
    "Pepper Initials Quantity",
    "Order Metel",
    "Metel Black Quantity",
    "Order Blizzard",
    "Blizzard Black Quantity",
    "Order Rivet",
    "Rivet Size",
    "Rivet Black Quantity",
    "Order Barrier",
    "Barrier Size",
    "Barrier Black Quantity",
    "Order Rookie",
    "Rookie Size",
    "Rookie Black Quantity",
    "Rookie Initials",
    "Rookie Initials Quantity",
    "Order Academy Evo",
    "Academy Evo Black Quantity",
    "Academy Evo Initials",
    "Academy Evo Initials Quantity",
    "Order Trip",
    "Trip Size",
    "Trip Black Quantity",
    "Trip Initials",
    "Trip Initials Quantity",
]

ANSWERS = [
    {
        "Submitted at": "2026-09-17 10:00:00",
        "Full Name": "Ola Nordmann",
        "Email": "ola@example.com",
        "Phone Number": "4700000001",
        # Three kits: name on all, number on two, initials on one.
        "Order Wyvern Kit Black": "Yes",
        "Wyvern Kit Black Size": "M",
        "Wyvern Kit Black Quantity": "3",
        "Wyvern Kit Black Shirt Number": "7",
        "Wyvern Kit Black Shirt Number Quantity": "2",
        "Wyvern Kit Black Front Initials": "ON",
        "Wyvern Kit Black Front Initials Quantity": "1",
        "Wyvern Kit Black Back Print Text": "NORDMANN",
        "Wyvern Kit Black Back Print Text Quantity": "3",
        # One kit, print quantities left blank: all prints on it.
        "Order Wyvern Kit White": "Yes",
        "Wyvern Kit White Size": "L",
        "Wyvern Kit White Quantity": "1",
        "Wyvern Kit White Shirt Number": "7",
        "Wyvern Kit White Back Print Text": "NORDMANN",
        "Order Round Socks Evo White": "Yes",
        "Round Socks Evo White Size": "L (43-46)",
        "Round Socks Evo White Quantity": "2",
        "Order Poplar": "Yes",
        "Poplar Size": "M",
        "Poplar Color Selection": "Black, White",
        "Poplar Color Selection (Black)": "Black",
        "Poplar Color Selection (White)": "White",
        "Poplar Black Quantity": "1",
        "Poplar White Quantity": "1",
    },
    {
        "Submitted at": "2026-09-17 11:30:00",
        "Full Name": "Kari Nordmann",
        "Email": "kari@example.com",
        "Phone Number": "4700000002",
        "Order Wisp": "Yes",
        "Wisp Size": " S ",
        "Wisp Black Quantity": "2",
        "Wisp Black Front Initials": "KN",
        "Wisp Black Front Initials Quantity": "2",
        "Wisp Back Print Text": "KARI",
        "Wisp Black Back Print Text Quantity": "1",
        "Order Dryad": "Yes",
        "Dryad Size": "XS",
        "Dryad Black Quantity": "1",
        "Dryad Front Initials": "KN",
        "Order Galax": "Yes",
        "Galax Size": "M",
        "Galax Shorts Quantity": "1",
        "Galax Initials": "KN",
        "Order Acrux": "Yes",
        "Acrux Size": "S",
        "Acrux Quantity": "2",
        "Acrux Initials": "KN",
        "Acrux Initials Quantity": "1",
        "Order Desna": "Yes",
        "Size": "XL",
        "Desna Black Quantity": "1",
        "Desna Initials": "KN",
        "Order Pepper": "Yes",
        "Pepper Black Quantity": "1",
        "Pepper Initials": "KN",
        "Order Metel": "Yes",
        "Metel Black Quantity": "1",
        "Order Blizzard": "Yes",
        "Blizzard Black Quantity": "1",
        "Order Rookie": "Yes",
        "Rookie Size": "L",
        "Rookie Black Quantity": "1",
        "Rookie Initials": "KN",
    },
    {
        "Submitted at": "2026-09-18 09:15:00",
        "Full Name": "Bob Smith",
        "Email": "bob@example.com",
        "Phone Number": "4700000003",
        "Order Poseidon": "Yes",
        "Poseidon Size": "XXL",
        "Poseidon Black Quantity": "1",
        "Poseidon Front Initials": "BS",
        "Poseidon Back Print Text": "SMITH",
        "Order Artemis": "Yes",
        "Artemis Size": "XL",
        "Artemis Black Quantity": "1",
        "Order Anduin": "Yes",
        "Anduin Size": "L",
        "Anduin Black Quantity": "1",
        "Anduin Back Print Text": "SMITH",
        "Order Anora": "Yes",
        "Anora Size": "M",
        "Anora Black Quantity": "1",
        "Order Fenders": "Yes",
        "Fenders Size": "3XL",
        "Fenders Black Quantity": "1",
        "Fenders Front Initials": "BS",
        "Order Northland": "Yes",
        "Northland Jacket Size": "XL",
        "Northland Black Quantity": "1",
        "Order Narvik": "Yes",
        "Narvik Padded Jacket Size": "XS",
        "Narvik Black Quantity": "1",
        "Order Rivendell": "Yes",
        "Rivendell Size": "S",
        "Rivendell Black Quantity": "1",
        "Order Elbrus": "Yes",
        "Elbrus Black Size": "M",
        "Elbrus Black Quantity": "1",
        "Order Trip": "Yes",
        "Trip Size": "M",
        "Trip Black Quantity": "1",
        "Trip Initials": "BS",
        "Order Academy Evo": "Yes",
        "Academy Evo Black Quantity": "1",
        "Academy Evo Initials": "BS",
    },
    {
        "Submitted at": "2026-09-18 20:45:00",
        "Full Name": "Alice Smith",
        "Email": "alice@example.com",
        "Phone Number": "4700000004",
        "Order Archen": "Yes",
        "Archen Size": "S",
        "Archen Black Quantity": "1",
        "Archen Initials": "AS",
        "Order Thames": "Yes",
        "Thames Size": "M",
        "Thames Black Quantity": "2",
        "Order Fixed Socks White": "Yes",
        "Fixed Socks White Size": "M (39-42)",
        "Fixed Socks White Quantity": "3",
        "Order Poplar": "Yes",
        "Poplar Size": "L",
        "Poplar Color Selection": "White",
        "Poplar Color Selection (White)": "White",
        "Poplar White Quantity": "2",
        "Order Rivet": "Yes",
        "Rivet Size": "One size",
        "Rivet Black Quantity": "1",
        "Order Barrier": "Yes",
        "Barrier Size": "S",
        "Barrier Black Quantity": "1",
        # A bag ordered without a size has no price.
        "Order Rookie": "Yes",
        "Rookie Black Quantity": "1",
    },
    {
        "Submitted at": "2026-09-19 08:00:00",
        "Full Name": "Per Nordmann",
        "Email": "per@example.com",
        "Phone Number": "4700000005",
    },
]

COMMANDS = {
    "lookup.golden": [["lookup", "--field", "email", "example.com"]],
    "totals.golden": [
        ["totals"],
        ["totals", "--no-print-costs"],
        ["totals", "--unpriced"],
        ["totals", "--amount", "3 447"],
        ["totals", "--amount", "100"],
    ],
}


@pytest.fixture
def answer_sheet(tmp_path: Path) -> Path:
    unknown = {column for answer in ANSWERS for column in answer} - set(FORM_HEADERS)
    assert not unknown, f"not a form column: {unknown}"
    path = tmp_path / "apparel_order.csv"
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(FORM_HEADERS)
        for number, answer in enumerate(ANSWERS, start=1):
            ids = {"Submission ID": f"S{number}", "Respondent ID": f"R{number}"}
            writer.writerow(
                [{**ids, **answer}.get(column, "") for column in FORM_HEADERS]
            )
    return path


def check_golden(name: str, actual: str) -> None:
    path = GOLDEN_DIR / name
    if UPDATE:
        GOLDEN_DIR.mkdir(exist_ok=True)
        path.write_bytes(actual.encode())
        return
    assert path.exists(), f"{path} is missing; run with UPDATE_GOLDEN=1 to create it"
    assert actual.encode() == path.read_bytes(), (
        f"output differs from {path}; if intended, run with UPDATE_GOLDEN=1 "
        "and review the diff"
    )


def test_convert_matches_golden(answer_sheet: Path, tmp_path: Path) -> None:
    output = tmp_path / "order.csv"
    cli.main(["convert", "--input", str(answer_sheet), "--output", str(output)])
    check_golden("convert.golden", output.read_bytes().decode())


@pytest.mark.parametrize("name", list(COMMANDS))
def test_command_output_matches_golden(
    name: str, answer_sheet: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sections = []
    for arguments in COMMANDS[name]:
        try:
            cli.main([*arguments, "--input", str(answer_sheet)])
            status = ""
        except SystemExit as exit:
            status = f"(exit {exit.code})\n"
        command = " ".join(arguments)
        sections.append(f"$ apparel {command}\n{capsys.readouterr().out}{status}")
    check_golden(name, "\n".join(sections))
