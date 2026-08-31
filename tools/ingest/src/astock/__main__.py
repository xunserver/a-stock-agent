"""Executable entry point for the ingest command-line tool."""

from astock.cli.handlers import dispatch
from astock.cli.parser import build_parser
from astock.ingest import configure_logging


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging()
    dispatch(args, parser)


if __name__ == "__main__":
    main()
