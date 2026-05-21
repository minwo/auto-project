from __future__ import annotations

from pathlib import Path

from app.scripts.sync_stock_names_from_codes import build_parser


def test_sync_stock_names_parser_defaults_to_stock_codes_file() -> None:
    args = build_parser().parse_args([])

    assert args.file == Path("data/stock_codes.txt")
