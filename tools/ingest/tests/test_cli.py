from __future__ import annotations

from astock.cli import handlers
from astock.cli.formatters import format_pool_list, format_stock_catalog
from astock.cli.parser import build_parser, parse_codes


def test_parser_preserves_public_options_and_normalizes_codes() -> None:
    args = build_parser().parse_args(
        ["stock", "sync", "1, 600519", "--pool", "watch", "--info", "--add-to-pool"]
    )

    assert (args.cmd, args.stock_cmd, args.pool, args.info, args.add_to_pool) == (
        "stock", "sync", "watch", True, True,
    )
    assert parse_codes(args.codes) == ["000001", "600519"]


def test_parser_accepts_calendar_sync_force() -> None:
    args = build_parser().parse_args(["calendar", "sync", "--force", "--json"])
    assert args.cmd == "calendar"
    assert args.calendar_cmd == "sync"
    assert args.force is True
    assert args.json is True


def test_formatters_keep_table_content_readable() -> None:
    assert format_pool_list([]) == "(空)"
    assert "000001" in format_pool_list([{"code": "000001", "name": "平安银行", "status": "active"}])
    catalog = format_stock_catalog([{"code": "600519", "name": "贵州茅台", "pools": [{"id": "value"}]}])
    assert "600519" in catalog and "value" in catalog


def test_dispatch_news_uses_the_parsed_json_contract(monkeypatch, capsys) -> None:
    monkeypatch.setattr(handlers, "fetch_stock_news", lambda code, limit: [{"title": f"{code}/{limit}"}])
    parser = build_parser()
    args = parser.parse_args(["stock", "news", "1", "--limit", "3", "--json"])

    handlers.dispatch(args, parser)

    assert capsys.readouterr().out == '{\n  "code": "000001",\n  "count": 1,\n  "news": [\n    {\n      "title": "000001/3"\n    }\n  ]\n}\n'
