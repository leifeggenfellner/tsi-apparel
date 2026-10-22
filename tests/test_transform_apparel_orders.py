import csv
import hashlib
import sys
from pathlib import Path

import pytest

import transform_apparel_orders as app


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        csv.writer(file, lineterminator="\n").writerows(rows)


def read_csv(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.reader(file))


def template_rows() -> list[list[str]]:
    rows = [["" for _ in range(11)] for _ in range(33)]
    rows[0][0] = "SYNTHETIC TEMPLATE"
    rows[32][0:8] = [
        "Produkt",
        "Farge",
        "Størrelse",
        "Navn å trykke",
        "Initialer",
        "Trykk tall bak",
        "Trykk tall foran",
        "Instruksjoner",
    ]
    return rows


def basic_headers() -> list[str]:
    return [
        "Order Wisp Black",
        "Wisp Black Quantity",
        "Wisp Black Size",
        "Wisp Back Print Text",
        "Wisp Initials",
        "Wisp Shirt Number",
        "Wisp Front Shirt Number",
        "Wisp Shirt Number Quantity",
    ]


def make_transform_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source.csv"
    template = tmp_path / "template.csv"
    output = tmp_path / "output.csv"
    write_csv(template, template_rows())
    return source, template, output


@pytest.mark.parametrize(
    ("value", "expected"),
    [("  Mixed\t CASE ", "mixed case"), (12, "12"), ("", "")],
)
def test_normalized(value: object, expected: str) -> None:
    assert app.normalized(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [("", 0), ("0", 0), ("+12", 12), (" 3 ", 3)]
)
def test_parse_quantity_valid(value: str, expected: int) -> None:
    assert app.parse_quantity(value, "quantity") == expected


@pytest.mark.parametrize("value", ["-1", "1.5", "two"])
def test_parse_quantity_invalid(value: str) -> None:
    with pytest.raises(app.TransformError):
        app.parse_quantity(value, "quantity")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", None), (" YES ", True), ("black", True), ("No", False), ("nei", False)],
)
def test_selection_state(value: str, expected: bool | None) -> None:
    assert app.selection_state(value, "color") is expected


def test_selection_state_rejects_unknown_value() -> None:
    with pytest.raises(app.TransformError, match="unrecognized"):
        app.selection_state("maybe", "color")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  Tee   black ", ("Tee", "Black")),
        ("Poplar", ("Poplar", "")),
        ("White", ("White", "")),
    ],
)
def test_product_and_color(value: str, expected: tuple[str, str]) -> None:
    assert app.product_and_color(value) == expected


@pytest.mark.parametrize(
    ("product", "category"),
    [
        ("Wyvern Kit", "Drakt"),
        ("Dryad", "Treningsdrakt"),
        ("Round Socks Evo", "Sokker"),
        ("Academy Evo", "Bag / Ryggsekk"),
        ("Barrier", "Annet"),
    ],
)
def test_product_category_resolves_confirmed_categories(
    product: str, category: str
) -> None:
    assert app.product_category(product) == category
    assert category in app.VALID_CATEGORIES


def test_product_category_rejects_unmapped_and_invalid_configured_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(app.TransformError, match="Unmapped"):
        app.product_category("Unknown")
    monkeypatch.setitem(app.PRODUCT_CATEGORIES, "wisp", "Not allowed")
    with pytest.raises(app.TransformError, match="invalid"):
        app.product_category("Wisp")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" 5xs (youth) ", "5XS"),
        ("4XS", "4XS"),
        ("m (adult)", "M"),
        ("one-size", "Vare uten størrelse"),
        ("", "Vare uten størrelse"),
        ("unknown", "Vare uten størrelse"),
    ],
)
def test_standardize_size(value: str, expected: str) -> None:
    assert app.standardize_size(value) == expected


@pytest.mark.parametrize(
    ("header", "expected"),
    [("Tee Quantity", True), ("Tee Color Selection", True), ("Notes", False)],
)
def test_is_recognized_family_field(header: str, expected: bool) -> None:
    assert app.is_recognized_family_field(header) is expected


@pytest.mark.parametrize("value", ["No", "FALSE", "0", "off", "nei"])
def test_is_explicit_no(value: str) -> None:
    assert app.is_explicit_no(value)
    assert not app.is_explicit_no("yes")


def test_file_hash_is_sha256_and_changes_with_content(tmp_path: Path) -> None:
    path = tmp_path / "value.csv"
    path.write_text("value\n1\n", encoding="utf-8")
    assert app.file_hash(path) == hashlib.sha256(b"value\n1\n").hexdigest()
    path.write_text("value\n2\n", encoding="utf-8")
    assert app.file_hash(path) != hashlib.sha256(b"value\n1\n").hexdigest()


def test_family_ranges_and_validate_source_schema() -> None:
    headers = [
        "metadata",
        "Order Tee Black",
        "Tee Black Quantity",
        "",
        "Order Cap",
        "Cap Quantity",
        "Cap Size",
    ]
    expected = [(1, 4, "Tee Black"), (4, 7, "Cap")]
    assert app.family_ranges(headers) == expected
    assert app.validate_source_schema(headers) == expected


@pytest.mark.parametrize(
    "headers",
    [
        ["No order", "Tee Quantity"],
        ["Order ", "Tee Quantity"],
        ["Order Tee", "Tee Size"],
        ["Order Tee", "Tee Quantity", "Unexpected Field"],
    ],
)
def test_validate_source_schema_rejects_invalid_families(headers: list[str]) -> None:
    with pytest.raises(app.TransformError):
        app.validate_source_schema(headers)


def test_first_field() -> None:
    headers = ["Order Tee", "Tee Quantity", "Tee Size", "Other Size", "Order Cap"]
    row = ("yes", "2", " M ", "", "yes")
    assert app.first_field(row, headers, 0, 4, "size") == "M"
    assert app.first_field(row, headers, 0, 4, "initials") == ""


def test_first_field_rejects_conflicting_values() -> None:
    headers = ["Order Tee", "Tee Size", "Alternate Size"]
    with pytest.raises(app.TransformError, match="conflicting size"):
        app.first_field(("yes", "M", "L"), headers, 0, 3, "size")


def test_customization_fields_maps_each_supported_field() -> None:
    headers = basic_headers()
    row = ("yes", "2", "M", " BACK ", " IN ", " 8 ", " 9 ", " 1 ")
    assert app.customization_fields(row, headers, 0, len(headers)) == {
        "back_text": "BACK",
        "initials": "IN",
        "back_number": "8",
        "front_number": "9",
        "number_quantity": "1",
        "initials_quantity": None,
        "back_text_quantity": None,
    }


def test_customization_fields_copies_single_shirt_number_to_front() -> None:
    headers = ["Order Kit", "Kit Quantity", "Kit Shirt Number"]
    fields = app.customization_fields(("yes", "1", "7"), headers, 0, len(headers))
    assert fields["back_number"] == "7"
    assert fields["front_number"] == "7"


def test_poplar_selections_accepts_boolean_and_generic_selection() -> None:
    headers = [
        "Order Poplar",
        "Poplar Black Quantity",
        "Poplar White Quantity",
        "Poplar Color Selection",
        "Poplar Black Color Selection",
    ]
    row = ("yes", "1", "0", "white", "no")
    assert app.poplar_selections(row, headers, 0, len(headers), 2) == {
        "Black": False,
        "White": True,
    }


@pytest.mark.parametrize(
    "row",
    [
        ("yes", "1", "0", "maybe", ""),
        ("yes", "1", "0", "white", "yes"),
    ],
)
def test_poplar_selections_rejects_unrecognized_or_conflicting_values(
    row: tuple[str, ...],
) -> None:
    headers = [
        "Order Poplar",
        "Poplar Black Quantity",
        "Poplar White Quantity",
        "Poplar Color Selection",
        "Poplar Black Color Selection",
    ]
    with pytest.raises(app.TransformError):
        app.poplar_selections(row, headers, 0, len(headers), 2)


def test_add_print_rows_maps_number_quantity_to_each_garment() -> None:
    rows: list[list[str]] = []
    fields = {
        "back_text": "BACK",
        "initials": "IN",
        "back_number": "8",
        "front_number": "9",
        "number_quantity": "1",
    }
    app.add_print_rows(rows, "Wisp", "Treningsdrakt", "Black", "M", 2, fields, 4)
    assert rows == [
        [
            "Wisp",
            "Black",
            "M",
            "BACK",
            "IN",
            "8",
            "9",
            "Navn trykkes øverst på ryggen; Initialer trykkes under Kraft-logoen foran",
        ],
        [
            "Wisp",
            "Black",
            "M",
            "BACK",
            "IN",
            "",
            "",
            "Navn trykkes øverst på ryggen; Initialer trykkes under Kraft-logoen foran",
        ],
    ]
    assert fields["number_quantity"] == "1"


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        (
            {
                "back_text": "Name",
                "initials": "",
                "back_number": "",
                "front_number": "",
                "number_quantity": "",
            },
            "Navn trykkes øverst på ryggen",
        ),
        (
            {
                "back_text": "",
                "initials": "IN",
                "back_number": "",
                "front_number": "",
                "number_quantity": "",
            },
            "Initialer trykkes under Kraft-logoen foran",
        ),
        (
            {
                "back_text": "Name",
                "initials": "IN",
                "back_number": "",
                "front_number": "",
                "number_quantity": "",
            },
            "Navn trykkes øverst på ryggen; Initialer trykkes under Kraft-logoen foran",
        ),
        (
            {
                "back_text": "",
                "initials": "",
                "back_number": "8",
                "front_number": "9",
                "number_quantity": "1",
            },
            "",
        ),
    ],
)
def test_add_print_rows_composes_customization_instructions(
    fields: dict[str, str], expected: str
) -> None:
    rows: list[list[str]] = []

    app.add_print_rows(rows, "Wisp", "Treningsdrakt", "Black", "M", 1, fields, 3)

    assert rows[0][7] == expected


def test_add_print_rows_only_wyvern_kit_mentions_the_number_position() -> None:
    fields = {
        "back_text": "Name",
        "initials": "",
        "back_number": "",
        "front_number": "",
        "number_quantity": "",
    }

    kit_rows: list[list[str]] = []
    app.add_print_rows(kit_rows, "Wyvern Kit", "Drakt", "Black", "M", 1, fields, 3)
    assert kit_rows[0][7] == "Navn trykkes øverst på ryggen, over tallet"

    jacket_rows: list[list[str]] = []
    app.add_print_rows(
        jacket_rows, "Poseidon", "Jakke / Yttertøy", "Black", "M", 1, fields, 3
    )
    assert jacket_rows[0][7] == "Navn trykkes øverst på ryggen"


def test_add_print_rows_skips_blank_fields_and_rejects_number_overflow() -> None:
    rows: list[list[str]] = []
    app.add_print_rows(
        rows,
        "Wisp",
        "Treningsdrakt",
        "",
        "M",
        1,
        {
            "back_text": "",
            "initials": "",
            "back_number": "",
            "front_number": "",
            "number_quantity": "",
        },
        2,
    )
    assert rows == []
    with pytest.raises(app.TransformError, match="exceeds"):
        app.add_print_rows(
            rows,
            "Tee",
            "Drakt",
            "",
            "M",
            1,
            {
                "back_text": "BACK",
                "initials": "",
                "back_number": "",
                "front_number": "",
                "number_quantity": "2",
            },
            2,
        )


def test_add_print_rows_gates_initials_and_back_text_by_their_own_quantity() -> None:
    rows: list[list[str]] = []
    fields = {
        "back_text": "BACK",
        "initials": "IN",
        "back_number": "",
        "front_number": "",
        "number_quantity": None,
        "initials_quantity": "1",
        "back_text_quantity": "2",
    }
    app.add_print_rows(rows, "Wisp", "Treningsdrakt", "Black", "M", 2, fields, 4)
    assert [row[3] for row in rows] == ["BACK", "BACK"]
    assert [row[4] for row in rows] == ["IN", ""]


def test_add_print_rows_requires_garment_quantity_one_when_quantity_field_blank() -> (
    None
):
    fields = {
        "back_text": "",
        "initials": "IN",
        "back_number": "",
        "front_number": "",
        "number_quantity": None,
        "initials_quantity": "",
        "back_text_quantity": None,
    }
    rows: list[list[str]] = []
    app.add_print_rows(rows, "Wisp", "Treningsdrakt", "Black", "M", 1, fields, 4)
    assert rows[0][4] == "IN"

    with pytest.raises(app.TransformError, match="left blank"):
        app.add_print_rows(rows, "Wisp", "Treningsdrakt", "Black", "M", 2, fields, 4)


def test_add_print_rows_ignores_missing_quantity_companion_column() -> None:
    rows: list[list[str]] = []
    fields = {
        "back_text": "",
        "initials": "AB",
        "back_number": "",
        "front_number": "",
        "number_quantity": None,
        "initials_quantity": None,
        "back_text_quantity": None,
    }
    app.add_print_rows(rows, "Galax", "Shorts", "Black", "5XS", 2, fields, 4)
    assert [row[4] for row in rows] == ["AB", "AB"]


@pytest.mark.parametrize(
    ("category", "expected_instruction"),
    [
        ("Bag / Ryggsekk", ""),
        ("Shorts", ""),
        ("Sokker", ""),
        ("Bukser", ""),
        ("Caps / Lue", ""),
        ("Annet", ""),
        (
            "Jakke / Yttertøy",
            "Navn trykkes øverst på ryggen; Initialer trykkes under Kraft-logoen foran",
        ),
    ],
)
def test_add_print_rows_suppresses_only_instructions_for_configured_categories(
    category: str, expected_instruction: str
) -> None:
    rows: list[list[str]] = []
    fields = {
        "back_text": "BACK",
        "initials": "IN",
        "back_number": "8",
        "front_number": "9",
        "number_quantity": "1",
    }

    app.add_print_rows(rows, "Product", category, "Black", "M", 1, fields, 3)

    assert rows[0][:7] == ["Product", "Black", "M", "BACK", "IN", "8", "9"]
    assert rows[0][7] == expected_instruction


def test_transform_aggregates_in_order_preserves_inputs_and_maps_print_rows(
    tmp_path: Path,
) -> None:
    source, template, output = make_transform_paths(tmp_path)
    headers = basic_headers() + [
        "Order Poplar",
        "Poplar Black Quantity",
        "Poplar White Quantity",
        "Poplar Size",
        "Poplar Black Color Selection",
        "Poplar White Color Selection",
    ]
    write_csv(
        source,
        [
            headers,
            [
                "yes",
                "2",
                "M (Adult)",
                "BACK",
                "IN",
                "8",
                "9",
                "1",
                "yes",
                "1",
                "2",
                "S",
                "yes",
                "yes",
            ],
        ],
    )
    source_hash, template_hash = app.file_hash(source), app.file_hash(template)

    assert app.transform(source, template, output, "Team Apparel") == (5, 2)
    written = read_csv(output)

    assert app.file_hash(source) == source_hash
    assert app.file_hash(template) == template_hash
    assert len(written) == 37
    assert {len(row) for row in written} == {11}
    assert [written[app.PRODUCT_ROW][column] for column in range(1, 4)] == [
        "Wisp",
        "Poplar",
        "Poplar",
    ]
    assert [written[app.COLOR_ROW][column] for column in range(1, 4)] == [
        "Black",
        "Black",
        "White",
    ]
    assert [written[app.CATEGORY_ROW][column] for column in range(1, 4)] == [
        "Treningsdrakt",
        "Annet",
        "Annet",
    ]
    assert {
        written[app.CATEGORY_ROW][column] for column in range(1, 4)
    } <= app.VALID_CATEGORIES
    assert written[app.SIZE_ROWS["M"]][1] == "2"
    assert written[app.SIZE_ROWS["S"]][2:4] == ["1", "2"]
    assert written[app.PRODUCT_TOTAL_ROW][1:4] == ["2", "1", "2"]
    assert written[app.GRAND_TOTAL_ROW][1] == "5"
    assert written[app.PRINT_HEADER_ROW] == template_rows()[32]
    assert written[35][0:8] == [
        "Wisp",
        "Black",
        "M",
        "BACK",
        "IN",
        "8",
        "9",
        "Navn trykkes øverst på ryggen; Initialer trykkes under Kraft-logoen foran",
    ]
    assert written[36][0:8] == [
        "Wisp",
        "Black",
        "M",
        "BACK",
        "IN",
        "",
        "",
        "Navn trykkes øverst på ryggen; Initialer trykkes under Kraft-logoen foran",
    ]


def test_transform_does_not_double_count_customization_quantity_columns(
    tmp_path: Path,
) -> None:
    source, template, output = make_transform_paths(tmp_path)
    headers = basic_headers() + [
        "Wisp Initials Quantity",
        "Wisp Back Print Text Quantity",
    ]
    write_csv(
        source,
        [
            headers,
            ["yes", "2", "M", "BACK", "IN", "", "", "", "2", "2"],
        ],
    )

    assert app.transform(source, template, output, "Apparel") == (2, 2)


def test_transform_expands_template_to_rectangular_product_width(
    tmp_path: Path,
) -> None:
    source, template, output = make_transform_paths(tmp_path)
    headers: list[str] = []
    row: list[str] = []
    products = list(app.PRODUCT_CATEGORIES)
    for number, product in enumerate(products[:11]):
        display_product = product.title()
        headers.extend([f"Order {display_product}", f"{display_product} Quantity"])
        row.extend(["yes", "1"])
    write_csv(source, [headers, row])

    assert app.transform(source, template, output, "Apparel") == (11, 0)
    written = read_csv(output)
    assert {len(output_row) for output_row in written} == {12}
    assert [written[app.PRODUCT_ROW][column] for column in range(1, 12)] == [
        product.title() for product in products[:11]
    ]


def test_transform_groups_same_product_columns_together(tmp_path: Path) -> None:
    source, template, output = make_transform_paths(tmp_path)
    headers = [
        "Order Wyvern Kit Black",
        "Wyvern Kit Black Quantity",
        "Order Dryad",
        "Dryad Black Quantity",
        "Order Wyvern Kit White",
        "Wyvern Kit White Quantity",
    ]
    write_csv(
        source,
        [
            headers,
            ["yes", "1", "yes", "1", "no", ""],
            ["no", "", "no", "", "yes", "1"],
        ],
    )

    assert app.transform(source, template, output, "Apparel") == (3, 0)
    written = read_csv(output)

    assert [written[app.PRODUCT_ROW][column] for column in range(1, 4)] == [
        "Wyvern Kit",
        "Wyvern Kit",
        "Dryad",
    ]
    assert [written[app.COLOR_ROW][column] for column in range(1, 4)] == [
        "Black",
        "White",
        "Black",
    ]


def test_transform_groups_print_rows_by_product(tmp_path: Path) -> None:
    source, template, output = make_transform_paths(tmp_path)
    headers = [
        "Order Wyvern Kit Black",
        "Wyvern Kit Black Quantity",
        "Wyvern Kit Black Initials",
        "Order Dryad",
        "Dryad Black Quantity",
        "Dryad Initials",
    ]
    write_csv(
        source,
        [
            headers,
            ["yes", "1", "AA", "yes", "1", "BB"],
            ["yes", "1", "CC", "no", "", ""],
        ],
    )

    assert app.transform(source, template, output, "Apparel") == (3, 3)
    written = read_csv(output)

    assert [row[0] for row in written[35:38]] == [
        "Wyvern Kit",
        "Wyvern Kit",
        "Dryad",
    ]
    assert [row[4] for row in written[35:38]] == ["AA", "CC", "BB"]


def test_transform_uses_one_column_for_multiple_sizes_and_maps_galax_to_black(
    tmp_path: Path,
) -> None:
    source, template, output = make_transform_paths(tmp_path)
    headers = [
        "Order Galax",
        "Galax Shorts Quantity",
        "Galax Shorts Size",
        "Galax Shorts Initials",
    ]
    write_csv(source, [headers, ["yes", "2", "5xs", "AB"], ["yes", "3", "4XS", ""]])

    assert app.transform(source, template, output, "Apparel") == (5, 2)
    written = read_csv(output)

    assert len(written) == 37
    assert [written[app.SIZE_ROWS[size]][0] for size in ("5XS", "4XS", "3XS")] == [
        "5XS",
        "4XS",
        "",
    ]
    assert written[app.SIZE_ROWS["5XS"]][1] == "2"
    assert written[app.SIZE_ROWS["4XS"]][1] == "3"
    assert written[app.SIZE_ROWS["3XS"]] == [""] * 11
    assert written[app.PRODUCT_TOTAL_ROW][1] == "5"
    assert written[app.CATEGORY_ROW][1] == "Shorts"
    assert written[app.GRAND_TOTAL_ROW][1] == "5"
    assert written[app.PRINT_HEADER_ROW] == template_rows()[32]
    assert [row[0:3] for row in written[35:]] == [
        ["Galax", "Black", "5XS"],
        ["Galax", "Black", "5XS"],
    ]


def test_transform_defaults_blank_color_to_black_for_any_product(
    tmp_path: Path,
) -> None:
    source, template, output = make_transform_paths(tmp_path)
    write_csv(
        source,
        [
            ["Order Acrux", "Acrux Quantity", "Acrux Size"],
            ["yes", "1", "M"],
        ],
    )

    assert app.transform(source, template, output, "Apparel") == (1, 0)
    written = read_csv(output)

    assert written[app.COLOR_ROW][1] == "Black"


def test_transform_poplar_requires_explicit_color(tmp_path: Path) -> None:
    source, template, output = make_transform_paths(tmp_path)
    write_csv(
        source,
        [
            ["Order Poplar", "Poplar Quantity"],
            ["yes", "1"],
        ],
    )

    with pytest.raises(app.TransformError, match="no Black or White color"):
        app.transform(source, template, output, "Apparel")


def test_transform_maps_exact_round_socks_evo_to_sokker(tmp_path: Path) -> None:
    source, template, output = make_transform_paths(tmp_path)
    write_csv(
        source,
        [
            ["Order Round Socks Evo", "Round Socks Evo Quantity"],
            ["yes", "2"],
        ],
    )

    assert app.transform(source, template, output, "Apparel") == (2, 0)
    written = read_csv(output)

    assert written[app.PRODUCT_ROW][1] == "Round Socks Evo"
    assert written[app.CATEGORY_ROW][1] == "Sokker"


def test_transform_coalesces_repeated_product_category_color_and_size(
    tmp_path: Path,
) -> None:
    source, template, output = make_transform_paths(tmp_path)
    write_csv(
        source,
        [
            [
                "Order Round Socks Evo",
                "Round Socks Evo Quantity",
                "Round Socks Evo Size",
            ],
            ["yes", "2", "M"],
            ["yes", "3", "M"],
        ],
    )

    assert app.transform(source, template, output, "Apparel") == (5, 0)
    written = read_csv(output)

    assert written[app.PRODUCT_ROW][1] == "Round Socks Evo"
    assert written[app.CATEGORY_ROW][1] == "Sokker"
    assert written[app.SIZE_ROWS["M"]][1] == "5"
    assert written[app.PRODUCT_TOTAL_ROW][1] == "5"


def test_main_ignores_alternate_category_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, template, default_output = make_transform_paths(tmp_path)
    alternate_output = tmp_path / "alternate-output.csv"
    write_csv(source, [basic_headers(), ["yes", "1", "M", "", "", "", "", ""]])

    for output, category in (
        (default_output, "Apparel"),
        (alternate_output, "A different category"),
    ):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "transform_apparel_orders.py",
                "--input",
                str(source),
                "--template",
                str(template),
                "--output",
                str(output),
                "--category",
                category,
            ],
        )
        app.main()

    assert default_output.read_bytes() == alternate_output.read_bytes()


def test_transform_rejects_unknown_product_without_publishing(tmp_path: Path) -> None:
    source, template, output = make_transform_paths(tmp_path)
    write_csv(
        source,
        [["Order Unknown", "Unknown Quantity"], ["yes", "1"]],
    )

    with pytest.raises(app.TransformError, match="Unmapped product"):
        app.transform(source, template, output, "Apparel")

    assert not output.exists()


@pytest.mark.parametrize("number_quantity", ["-1", "1.5", "not a number"])
def test_transform_rejects_invalid_shirt_number_quantity_without_publishing(
    tmp_path: Path, number_quantity: str
) -> None:
    source, template, output = make_transform_paths(tmp_path)
    row = ["yes", "1", "M", "BACK", "", "8", "", number_quantity]
    write_csv(source, [basic_headers(), row])

    with pytest.raises(app.TransformError, match="Shirt Number Quantity"):
        app.transform(source, template, output, "Apparel")

    assert not output.exists()


def test_transform_rejects_output_path_aliasing_template(tmp_path: Path) -> None:
    source, template, _ = make_transform_paths(tmp_path)
    write_csv(source, [basic_headers(), ["yes", "1", "M", "", "", "", "", ""]])

    with pytest.raises(ValueError, match="Output path must not alias"):
        app.transform(source, template, template, "Apparel")


def test_transform_is_byte_deterministic_across_distinct_outputs(
    tmp_path: Path,
) -> None:
    source, template, first_output = make_transform_paths(tmp_path)
    second_output = tmp_path / "second-output.csv"
    write_csv(source, [basic_headers(), ["yes", "2", "M", "BACK", "IN", "8", "9", "1"]])

    assert app.transform(source, template, first_output, "Apparel") == (2, 2)
    assert app.transform(source, template, second_output, "Apparel") == (2, 2)

    assert first_output.read_bytes() == second_output.read_bytes()
    assert app.file_hash(first_output) == app.file_hash(second_output)


def test_transform_preserves_existing_output_and_cleans_temp_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, template, output = make_transform_paths(tmp_path)
    write_csv(source, [basic_headers(), ["yes", "1", "M", "", "", "", "", ""]])
    prior_output = b"prior output must survive\n"
    output.write_bytes(prior_output)

    def fail_replace(source_path: str, destination_path: Path) -> None:
        raise OSError("simulated publication failure")

    monkeypatch.setattr(app.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated publication failure"):
        app.transform(source, template, output, "Apparel")

    assert output.read_bytes() == prior_output
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


@pytest.mark.parametrize(
    "case",
    [
        "output_alias",
        "invalid_quantity",
        "explicit_no",
        "malformed_template",
        "number_bounds",
        "poplar_conflict",
    ],
)
def test_transform_rejects_invalid_inputs(tmp_path: Path, case: str) -> None:
    source, template, output = make_transform_paths(tmp_path)
    headers = basic_headers()
    row = ["yes", "1", "M", "", "", "", "", ""]
    category = "Apparel"
    if case == "output_alias":
        output = source
    elif case == "invalid_quantity":
        row[1] = "1.5"
    elif case == "explicit_no":
        row[0] = "No"
    elif case == "malformed_template":
        write_csv(template, [["too", "small"]])
    elif case == "number_bounds":
        row[3], row[7] = "BACK", "2"
    elif case == "poplar_conflict":
        headers = [
            "Order Poplar",
            "Poplar Black Quantity",
            "Poplar Black Color Selection",
        ]
        row = ["yes", "1", "no"]
    write_csv(source, [headers, row])

    with pytest.raises((ValueError, app.TransformError)):
        app.transform(source, template, output, category)


def test_main_reports_success_and_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source, template, output = make_transform_paths(tmp_path)
    write_csv(source, [basic_headers(), ["yes", "1", "M", "", "", "", "", ""]])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "transform_apparel_orders.py",
            "--input",
            str(source),
            "--template",
            str(template),
            "--output",
            str(output),
            "--category",
            "Apparel",
        ],
    )
    app.main()
    assert "Wrote" in capsys.readouterr().out

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "transform_apparel_orders.py",
            "--input",
            str(source),
            "--template",
            str(template),
            "--output",
            str(source),
        ],
    )
    with pytest.raises(SystemExit, match="Output path must not alias"):
        app.main()


def test_main_accepts_all_positional_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source, template, output = make_transform_paths(tmp_path)
    write_csv(source, [basic_headers(), ["yes", "1", "M", "", "", "", "", ""]])
    monkeypatch.setattr(
        sys,
        "argv",
        ["transform_apparel_orders.py", str(source), str(template), str(output)],
    )

    app.main()

    assert output.exists()
    assert f"Wrote {output}: 1 garments, 0 print rows" in capsys.readouterr().out


def test_main_rejects_partial_positional_paths(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["transform_apparel_orders.py", "source.csv"])

    with pytest.raises(SystemExit) as error:
        app.main()

    assert error.value.code == 2
    assert "positional paths require input_name, template_file, and output_name" in (
        capsys.readouterr().err
    )


def test_main_rejects_matching_positional_and_option_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "transform_apparel_orders.py",
            "source.csv",
            "template.csv",
            "output.csv",
            "--input",
            "other-source.csv",
        ],
    )

    with pytest.raises(SystemExit) as error:
        app.main()

    assert error.value.code == 2
    assert "a positional path cannot be combined with its matching long option" in (
        capsys.readouterr().err
    )
