# Changelog

Notable changes to `tsi-apparel`, for people using the `apparel` command.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/).

Add an entry under **Unreleased** in the same pull request as the change.
When releasing, rename **Unreleased** to the new version and date, bump
`__version__` in `src/tsi_apparel/__init__.py`, and tag the commit `vX.Y.Z`.

## [Unreleased]

### Added
- `apparel` command, installable with pipx or pip, with `convert`, `lookup`,
  `prices` and `help` subcommands and `--version` (#7, #8).
- `apparel lookup` shows what each item costs, with clothing, print and grand
  totals. Use `--no-print-costs` to leave transfer prints out of the totals, or
  `--hide-prices` to hide prices entirely.
- `apparel prices` lists every product's list price and discounted price, plus
  the transfer print prices; `--list` shows list prices only (#8).
- Size-based prices for the Rookie and Trip bags (M and L). A bag ordered
  without a size, or in a size with no price, is shown as unpriced instead of
  guessed (#12).
- Prices for Academy Evo (751 kr), Rivet (249 kr) and Barrier (499 kr), before
  the 50% discount. Every product on the form now has a price (#12).
- README with installation, usage, prices and form format (#14).
- `apparel totals` lists every different amount people owe on an order, and
  how many people owe each, for sending invoices. Takes `--input` and
  `--no-print-costs` like `lookup` (#24).
- `apparel totals --amount <kr>` lists the people who owe exactly that amount,
  with email and phone, to know who gets which invoice. `--unpriced` lists the
  people whose total isn't known because an item has no price (#25).

### Changed
- Python 3.15 or newer is now required, up from 3.12. The Nix dev shell uses
  Python 3.15 too.
- `convert` uses the bundled order sheet template by default, so it works from
  any directory (#7).
- Form values are trimmed of stray leading and trailing spaces when the
  answer sheet is read (#11).
- The Nix dev shell now includes pip and pipx (#9).

### Fixed
- A shirt number is now printed on both the front and the back of the shirt.
  Before, it only filled in the back number on the order sheet.

### Removed
- The `transform_apparel_orders.py` and `lookup_order.py` scripts. Use
  `apparel convert` and `apparel lookup` instead (#7).

[Unreleased]: https://github.com/leifeggenfellner/tsi-apparel/commits/main
