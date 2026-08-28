from astock_control.adapters.ingest import (
    INGEST_DIR,
    boards_sync_argv,
    parse_trailing_json,
    pool_command_argv,
    quotes_sync_argv,
    stock_command_argv,
)


def test_quotes_sync_argv_defaults() -> None:
    argv = quotes_sync_argv({"type": "quotes.sync", "pool": "default"})
    assert argv[:3] == ["uv", "--directory", str(INGEST_DIR)]
    assert argv[-2:] == ["quotes", "sync"]
    assert "--json" in argv
    assert argv[argv.index("--pool") + 1] == "default"


def test_quotes_sync_argv_optional_flags() -> None:
    argv = quotes_sync_argv(
        {
            "type": "quotes.sync",
            "pool": "p1",
            "sleep": 0.5,
            "adjust": "qfq",
            "limit": 2,
            "history_start": "20000101",
            "periods": ["daily", "weekly"],
        }
    )
    assert argv[argv.index("--pool") + 1] == "p1"
    assert argv[argv.index("--sleep") + 1] == "0.5"
    assert argv[argv.index("--adjust") + 1] == "qfq"
    assert argv[argv.index("--limit") + 1] == "2"
    assert argv[argv.index("--history-start") + 1] == "20000101"
    assert argv[argv.index("--periods") + 1] == "daily,weekly"


def test_quotes_sync_argv_codes() -> None:
    argv = quotes_sync_argv(
        {"type": "quotes.sync", "pool": "default", "codes": ["000001", "600519"]}
    )
    assert argv[argv.index("--codes") + 1] == "000001,600519"


def test_pool_add_codes_argv() -> None:
    argv = pool_command_argv(
        {"type": "pool.add", "pool": "hs", "codes": ["000001", "600519"]}
    )
    assert argv[-4:] == ["pool", "add", "--codes", "000001,600519"]
    assert argv[argv.index("--pool") + 1] == "hs"


def test_pool_add_index_argv() -> None:
    argv = pool_command_argv({"type": "pool.add", "pool": "default", "index": "hs300"})
    assert argv[-4:] == ["pool", "add", "--index", "hs300"]


def test_pool_set_and_remove_argv() -> None:
    set_argv = pool_command_argv({"type": "pool.set", "pool": "p1", "index": "zz500"})
    assert set_argv[-4:] == ["pool", "set", "--index", "zz500"]
    remove_argv = pool_command_argv(
        {"type": "pool.remove", "pool": "p1", "codes": ["000001"]}
    )
    assert remove_argv[-4:] == ["pool", "remove", "--codes", "000001"]


def test_stock_add_index_argv() -> None:
    argv = stock_command_argv({"type": "stock.add", "index": "hs300"})
    assert argv[-4:] == ["stock", "add", "--index", "hs300"]
    assert "--json" in argv


def test_stock_sync_with_statements_argv() -> None:
    argv = stock_command_argv(
        {
            "type": "stock.sync",
            "pool": "default",
            "codes": ["000001"],
            "with_statements": True,
        }
    )
    assert "--statements" in argv
    assert argv[argv.index("sync") + 1] == "000001"
    assert "--json" in argv


def test_boards_sync_argv_defaults() -> None:
    argv = boards_sync_argv({"type": "boards.sync", "pool": "default"})
    assert argv[:3] == ["uv", "--directory", str(INGEST_DIR)]
    assert argv[-4:] == ["boards", "sync", "--kind", "all"]
    assert "--json" in argv


def test_boards_sync_argv_optional_flags() -> None:
    argv = boards_sync_argv(
        {
            "type": "boards.sync",
            "pool": "default",
            "kind": "industry",
            "sleep": 0.2,
            "limit": 3,
        }
    )
    assert argv[argv.index("--kind") + 1] == "industry"
    assert argv[argv.index("--sleep") + 1] == "0.2"
    assert argv[argv.index("--limit") + 1] == "3"


def test_parse_indented_json() -> None:
    text = "noise\n{\n  \"ok\": true,\n  \"n\": 1\n}\n"
    assert parse_trailing_json(text) == {"ok": True, "n": 1}


def test_parse_json_after_dict_repr_noise() -> None:
    text = (
        "Training until validation scores don't improve for 50 rounds\n"
        "{'IC': 0.01, 'ICIR': 0.02}\n"
        '{\n  "ok": true,\n  "n": 2\n}\n'
    )
    assert parse_trailing_json(text) == {"ok": True, "n": 2}

