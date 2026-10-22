import argparse
from decimal import Decimal

import pytest

from tsi_apparel import prices
from tsi_apparel.transform import PRODUCT_CATEGORIES


def run_prices(capsys: pytest.CaptureFixture[str], *, list_only: bool) -> list[str]:
    prices.run(argparse.Namespace(list=list_only))
    return capsys.readouterr().out.splitlines()


def test_garment_unit_price_applies_discount() -> None:
    assert prices.garment_unit_price("Wyvern Kit") == Decimal("499.50")
    assert prices.garment_unit_price("  round   SOCKS evo ") == Decimal("94.50")
    assert prices.garment_unit_price("Academy Evo") == Decimal("375.50")
    assert prices.garment_unit_price("Not A Product") is None


def test_every_product_has_a_price_and_no_price_is_orphaned() -> None:
    assert set(prices.LIST_PRICES) == set(PRODUCT_CATEGORIES)
    assert set(prices.PRINT_ARTICLES) == set(prices.PRINT_PRICES)


def test_prices_lists_every_product_with_discounted_price(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = run_prices(capsys, list_only=False)

    assert "Price (-50%)" in lines[0]
    rows = {line[:18].strip(): line for line in lines[1 : len(PRODUCT_CATEGORIES) + 1]}
    assert set(rows) == {product.title() for product in PRODUCT_CATEGORIES}
    assert rows["Northland"].endswith("3 999.00 kr   1 999.50 kr")
    assert rows["Rivet"].endswith("249.00 kr     124.50 kr")
    assert rows["Barrier"].endswith("499.00 kr     249.50 kr")
    assert any("Montering tall rygg K Transfermerke" in line and "50.40 kr" in line for line in lines)
    assert all(line == line.rstrip() for line in lines)


def test_prices_list_flag_shows_list_prices_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = run_prices(capsys, list_only=True)

    assert "Price (-50%)" not in lines[0]
    assert len(lines) == len(PRODUCT_CATEGORIES) + 1
    assert any(line.startswith("Fenders") and line.endswith("1 399.00 kr") for line in lines)
    assert not any("Transfermerke" in line for line in lines)
