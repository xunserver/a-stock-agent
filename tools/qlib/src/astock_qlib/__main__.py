"""Entrypoint for the Qlib command-line tool."""

from __future__ import annotations

import logging

from astock_qlib.cli.handlers import dispatch
from astock_qlib.cli.parser import build_parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    dispatch(build_parser().parse_args())


if __name__ == "__main__":
    main()
