"""Command-line entry point: ``apparel <command> ...``."""

from __future__ import annotations

import argparse

from . import __version__, lookup, prices, transform

DESCRIPTION = "Order tools for TSI Volleyball apparel."
EPILOG = "Run 'apparel help <command>' (or 'apparel <command> --help') for details."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apparel", description=DESCRIPTION, epilog=EPILOG
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    convert_parser = commands.add_parser(
        "convert",
        help="Fill the supplier order sheet from the form answers",
        description=transform.__doc__,
    )
    transform.add_arguments(convert_parser)
    convert_parser.set_defaults(
        handler=lambda args: transform.run(args, convert_parser)
    )

    lookup_parser = commands.add_parser(
        "lookup",
        help="Look up a person's order and what it costs",
        description=lookup.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    lookup.add_arguments(lookup_parser)
    lookup_parser.set_defaults(handler=lookup.run)

    prices_parser = commands.add_parser(
        "prices",
        help="Show garment and print prices",
        description=prices.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    prices.add_arguments(prices_parser)
    prices_parser.set_defaults(handler=prices.run)

    help_parser = commands.add_parser(
        "help", help="Show help for a command", description="Show help for a command."
    )
    help_parser.add_argument(
        "topic", nargs="?", choices=sorted(commands.choices), metavar="<command>"
    )
    help_parser.set_defaults(
        handler=lambda args: (
            commands.choices[args.topic] if args.topic else parser
        ).print_help()
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command is None:
        parser.print_help()
        return
    arguments.handler(arguments)
