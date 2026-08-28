from __future__ import annotations

import sqlite3

import pytest

from astock_control.adapters.pool import PoolRunner
from astock_control.protocol import ProtocolError, normalize_command
from astock_core.db import MarketDB


def _seed(db: MarketDB) -> None:
    db.add_stocks(
        [("000001", "平安银行"), ("000002", "万科A"), ("600519", "贵州茅台")]
    )
    db.add_pool_members(
        "default",
        [("000001", "平安银行"), ("000002", "万科A"), ("600519", "贵州茅台")],
    )


def test_new_members_keep_insertion_order(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        _seed(db)
        assert db.active_pool_codes("default") == ["000001", "000002", "600519"]


def test_reorder_pool_members_persists(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        _seed(db)
        db.reorder_pool_members("default", ["600519", "000001", "000002"])
        assert db.active_pool_codes("default") == ["600519", "000001", "000002"]
        listed = db.list_pool_members("default")
        assert [item["code"] for item in listed] == ["600519", "000001", "000002"]


def test_new_and_reactivated_members_append(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        _seed(db)
        db.reorder_pool_members("default", ["600519", "000001", "000002"])
        db.add_stocks([("000858", "五粮液")])
        db.add_pool_members("default", [("000858", "五粮液")])
        assert db.active_pool_codes("default") == [
            "600519",
            "000001",
            "000002",
            "000858",
        ]
        db.remove_pool_members("default", ["000001"])
        db.add_pool_members("default", [("000001", "平安银行")])
        assert db.active_pool_codes("default") == [
            "600519",
            "000002",
            "000858",
            "000001",
        ]


def test_reorder_rejects_partial_list(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        _seed(db)
        with pytest.raises(ValueError, match="必须覆盖"):
            db.reorder_pool_members("default", ["600519", "000001"])


def test_migrates_sort_order_from_code_order(tmp_path) -> None:
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE pools (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE pool_members (
            pool_id TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            first_added_at TEXT NOT NULL,
            last_added_at TEXT NOT NULL,
            removed_at TEXT,
            PRIMARY KEY (pool_id, code)
        );
        INSERT INTO pools VALUES ('default', '默认股票池', '2020-01-01');
        INSERT INTO pool_members VALUES
          ('default', '600519', '茅台', 'active', 'manual', 't', 't', NULL),
          ('default', '000001', '平安', 'active', 'manual', 't', 't', NULL);
        """
    )
    conn.close()
    with MarketDB(path) as db:
        assert db.active_pool_codes("default") == ["000001", "600519"]


def test_pool_reorder_command_is_immediate() -> None:
    cmd = normalize_command(
        {"type": "pool.reorder", "pool": "default", "codes": ["600519", "000001"]}
    )
    assert cmd == {
        "type": "pool.reorder",
        "pool": "default",
        "codes": ["600519", "000001"],
    }
    with pytest.raises(ProtocolError, match="不支持后台运行"):
        from astock_control.protocol import resolve_job_background

        resolve_job_background(cmd, requested=True)


def test_pool_runner_reorders(tmp_path) -> None:
    db_path = tmp_path / "market.db"
    with MarketDB(db_path) as db:
        _seed(db)
    logs: list[str] = []
    result = PoolRunner(db_path).run(
        {
            "type": "pool.reorder",
            "pool": "default",
            "codes": ["600519", "000002", "000001"],
        },
        logs.append,
    )
    assert result["count"] == 3
    with MarketDB(db_path) as db:
        assert db.active_pool_codes("default") == ["600519", "000002", "000001"]
    assert logs == ["调整顺序 3 只"]
