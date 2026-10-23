# tsi-apparel

Order tools for TSI Volleyball apparel. One command, `apparel`, that:

- **converts** the form answers into the supplier's order sheet (quantities per product, color and size, plus one row per garment that gets a print), and
- **looks up** what one person ordered and what it costs, for the pickup desk.

> **Order CSVs contain personal data** (names, emails, phone numbers). They are
> gitignored and CI fails if one is committed. Only the blank template
> `src/tsi_apparel/data/order_schema.csv` belongs in the repo. Use placeholder
> names like Ola Nordmann or Bob Smith in tests and examples.

## Install

With [pipx](https://pipx.pypa.io) (recommended, puts `apparel` on your PATH):

```sh
pipx install git+ssh://git@github.com/leifeggenfellner/tsi-apparel.git
# or from a checkout
pipx install .
```

pipx puts the command in `~/.local/bin`; run `pipx ensurepath` if your shell
can't find `apparel` afterwards. To update, run `pipx install --force .` or `pipx reinstall tsi-apparel`.

With pip, install into a virtual environment:

```sh
python -m venv .venv
.venv/bin/pip install .
```

Requires Python 3.12 or newer. On NixOS, `nix develop` provides Python, pip,
pipx and ruff. Plain `pip install .` inside it fails, because the Nix Python is read-only.
Use pipx or a venv as above.

## Usage

```sh
apparel                  # overview of all commands
apparel help <command>   # same as: apparel <command> --help
apparel --version
```

`convert` and `lookup` read `apparel_order.csv` from the current directory
unless you pass `--input`.

### `apparel convert`: fill the supplier order sheet

```sh
apparel convert                                  # apparel_order.csv -> populated_order_schema.csv
apparel convert --input answers.csv --output order.csv
apparel convert --template my_template.csv       # only to override the bundled template
apparel convert answers.csv template.csv out.csv # positional form: all three paths
```

The result has:

- the product grid: product, category and color per column, with quantities per size and totals
- the print section: one row per garment that gets a print, with name, initials, back and front number, and placement instructions

The output is written atomically, and it is checked before it is published:

- the total number of garments must match the source
- the number of print rows must match the number of printed garments

`convert` refuses to write over its input or template.

### `apparel lookup`: one person's order and its cost

```sh
apparel lookup                                # interactive: type queries, blank line quits
apparel lookup "nordmann"                     # one search, then exit
apparel lookup --no-print-costs "nordmann"    # garment prices only, no transfer prints
apparel lookup --hide-prices "nordmann"       # no prices at all
apparel lookup --input other.csv "nordmann"
apparel lookup --exact "smith"                # whole words: Bob Smith, not Alice Smithson
apparel lookup --field phone --exact 91234567 # one field only; repeat --field for several
```

By default, searches match any part of the name, email or phone number,
ignoring case and accents, so `ase` finds *Åse*. Use `--exact` when that
returns too many people:

- **Names** match on whole words, in order. `smith` finds *Bob Smith* but not
  *Alice Smithson*, and `nordmann` finds *Kari Berg-Nordmann*.
- **Emails** match the whole address.
- **Phone numbers** match the whole number, ignoring spaces and `+`. An 8-digit
  number also matches without the country code, so `91234567` finds `4791234567`.

`--field name|email|phone` limits the search to that field. It works with or
without `--exact`, and can be repeated. Example output:

```
1 match(es) for "nordmann":

Ola Nordmann
  Email: ola@example.com   Phone: 4700000001   Submitted: 2026-09-17 10:00:00
  Product             Color Size        Qty Initials Back print      Number Price
  Wyvern Kit          Black M           1   ON       Nordmann        7      728.70 kr
  Rookie              Black M           1                                   449.50 kr
  Total garments: 2
  Clothing: 949.00 kr
  Prints:   229.20 kr
  Total:    1 178.20 kr
```

The kit's 728.70 kr is the 499.50 kr kit plus name (99.20), initials (49.60)
and the number on front (30.00) and back (50.40).

### `apparel prices`: the price list

```sh
apparel prices          # list price, discounted price, and transfer print prices
apparel prices --list   # list prices only
```

## Prices

All prices live in [`src/tsi_apparel/prices.py`](src/tsi_apparel/prices.py), in NOK:

- **`LIST_PRICES`**: garment list prices. The club gets `CLOTHING_DISCOUNT`
  (50%) off these, and that discounted price is what gets charged.
- **`SIZE_LIST_PRICES`**: products whose price depends on size (Rookie and
  Trip bags: M and L). A size-priced product ordered without a size, or in a
  size with no price, is shown as unpriced (`?`) and left out of the total.
- **`PRINT_PRICES`**: transfer prints, already final (no discount):

  | Print | Price |
  |---|---|
  | Name (back) | 99.20 kr |
  | Initials | 49.60 kr |
  | Number, front | 30.00 kr |
  | Number, back | 50.40 kr |

  A shirt number is always printed on both front and back.

Every product on the form must have exactly one price entry; a test enforces this.

## Form CSV format

The input is the form tool's CSV export: comma-separated UTF-8 with a header
row. Every value is trimmed of leading and trailing whitespace on load.

- **Contact columns**: `Submission ID`, `Respondent ID`, `Submitted at`,
  `Full Name`, `Email`, `Phone Number`.
- **Product families**: each product starts with an `Order <Product>` column
  (optionally with a color, e.g. `Order Wyvern Kit Black`). That column is
  followed by its fields, recognised by these words in the header:

  | Header contains | Meaning |
  |---|---|
  | `Quantity` | number ordered (whole number; blank = 0) |
  | `Size` | size, e.g. `M` or `L (43-46)`; blank or *one size* means no size |
  | `Shirt Number` | number, printed front and back |
  | `Front Initials` / `Initials` | initials |
  | `Back Print Text` | name printed on the back |
  | `... Quantity` after one of the above | how many of the garments get that print (missing column = all; blank is only allowed when ordering one) |
  | `Color Selection` | Poplar's black/white choice |

The product name in `Order <Product>` must be one the tool knows, with a
category (`PRODUCT_CATEGORIES` in `transform.py`) and a price. Unknown products
and unrecognised columns stop the conversion with an error rather than being
guessed.

Prints get a placement instruction only on kits, training tops and jackets.
Prints on bags, caps, shorts, trousers and socks use the factory default spot.

## Development

```sh
nix develop                # or a venv with: pip install -r requirements.txt -e .
pytest                     # tests use synthetic fixtures only
ruff check .
ruff format .              # CI rejects unformatted code
```

CI runs on every push to `main` and every pull request. It runs lint, the
format check and the tests on Python 3.12 and 3.13, smoke-tests the installed
CLI, and checks that no order data is committed.
