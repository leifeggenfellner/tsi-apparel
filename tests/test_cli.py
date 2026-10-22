import csv
from pathlib import Path

import pytest

from tsi_apparel import __version__, cli
from tsi_apparel.transform import DEFAULT_TEMPLATE

CONTACT_HEADERS = ["Submission ID", "Respondent ID", "Submitted at", "Full Name", "Email", "Phone Number"]
SOCK_HEADERS = ["Order Round Socks Evo White", "Round Socks Evo White Size", "Round Socks Evo White Quantity"]


def write_orders(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        csv.writer(file, lineterminator="\n").writerows(
            [
                CONTACT_HEADERS + SOCK_HEADERS,
                ["S1", "R1", "t", "Ola Nordmann", "ola@example.com", "4700000001", "Yes", "M", "2"],
            ]
        )


def test_no_command_prints_overview(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main([])
    out = capsys.readouterr().out
    assert "usage: apparel" in out
    assert "convert" in out and "lookup" in out and "help" in out


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["--version"])
    assert error.value.code == 0
    assert capsys.readouterr().out.strip() == f"apparel {__version__}"


@pytest.mark.parametrize("command", ["convert", "lookup"])
def test_help_command_matches_command_help(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["help", command])
    via_help = capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.main([command, "--help"])
    assert via_help == capsys.readouterr().out
    assert f"usage: apparel {command}" in via_help


def test_help_rejects_unknown_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["help", "nope"])
    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_lookup_command_searches_orders(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "orders.csv"
    write_orders(source)

    cli.main(["lookup", "--input", str(source), "nordmann"])

    out = capsys.readouterr().out
    assert "Ola Nordmann" in out
    assert "Total:    189.00 kr" in out


def test_convert_command_uses_bundled_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert DEFAULT_TEMPLATE.is_file()
    write_orders(tmp_path / "apparel_order.csv")
    monkeypatch.chdir(tmp_path)

    cli.main(["convert"])

    assert (tmp_path / "populated_order_schema.csv").exists()
    assert "2 garments, 0 print rows" in capsys.readouterr().out
