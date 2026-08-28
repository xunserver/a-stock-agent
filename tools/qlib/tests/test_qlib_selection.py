from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd
import yaml
from astock_core.db import MarketDB

from astock_qlib.dump import dump_qlib, pool_data_ready, prepare_pool_qlib
from astock_qlib.ranking import top_scores
from astock_qlib.workflow import run_workflow


def test_dump_writes_instruments_for_every_pool(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行"), ("600519", "贵州茅台")])
        db.create_pool("focus", "重点池")
        db.add_pool_members("default", [("000001", "平安银行")], source="manual")
        db.add_pool_members("focus", [("600519", "贵州茅台")], source="manual")
        db.upsert_bars(
            [
                ("000001", "2026-08-25", 10, 11, 12, 9, 100, 1000, 3, 1, 1, 2, "qfq"),
                (
                    "600519",
                    "2026-08-25",
                    100,
                    101,
                    102,
                    99,
                    100,
                    10000,
                    3,
                    1,
                    1,
                    2,
                    "qfq",
                ),
            ]
        )
        result = dump_qlib(db, dest=tmp_path / "qlib", pool_id="focus")

    assert result["pool_instruments_all"] == {"default": 1, "focus": 1}
    assert "SZ000001" in (tmp_path / "qlib/instruments/default.txt").read_text()
    assert "SH600519" in (tmp_path / "qlib/instruments/focus.txt").read_text()


def test_prepare_pool_qlib_writes_pool_directory(tmp_path) -> None:
    with MarketDB(tmp_path / "market.db") as db:
        db.add_stocks([("000001", "平安银行")])
        db.create_pool("focus", "重点池")
        db.add_pool_members("focus", [("000001", "平安银行")], source="manual")
        db.upsert_bars(
            [
                ("000001", "2026-08-25", 10, 11, 12, 9, 100, 1000, 3, 1, 1, 2, "qfq"),
            ]
        )
        dest = tmp_path / "qlib" / "pools" / "focus"
        result = prepare_pool_qlib(db, pool_id="focus", dest=dest)

    assert result["pool_members"] == 1
    assert pool_data_ready("focus", dest=dest)
    assert (dest / "instruments" / "focus.txt").is_file()
    assert "SZ000001" in (dest / "instruments" / "focus.txt").read_text()


def test_top_scores_uses_exact_artifact_and_filters_pool(tmp_path) -> None:
    index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2026-08-25"), "SZ000001"),
            (pd.Timestamp("2026-08-25"), "SH600519"),
        ]
    )
    pred = pd.DataFrame({"score": [0.5, 0.9]}, index=index)
    path = tmp_path / "pred.pkl"
    with path.open("wb") as fh:
        pickle.dump(pred, fh)

    result = top_scores(5, pred_path=path, pool_codes={"000001"})
    assert result["pred_path"] == str(path)
    assert result["universe_size"] == 1
    assert [item["code"] for item in result["top"]] == ["000001"]


def test_workflow_injects_pool_and_backtest_values(tmp_path, monkeypatch) -> None:
    config = {
        "qlib_init": {},
        "market": "csi300",
        "benchmark": "SH000300",
        "data_handler_config": {"instruments": "csi300"},
        "port_analysis_config": {
            "strategy": {"kwargs": {"topk": 50, "n_drop": 5}},
            "backtest": {"account": 100, "benchmark": "SH000300"},
        },
        "task": {
            "dataset": {
                "kwargs": {
                    "handler": {"kwargs": {"instruments": "csi300"}},
                }
            }
        },
    }
    source = tmp_path / "workflow.yaml"
    source.write_text(yaml.safe_dump(config), encoding="utf-8")
    data = tmp_path / "qlib"
    (data / "calendars").mkdir(parents=True)
    (data / "calendars/day.txt").write_text("2026-08-25\n")
    monkeypatch.setattr("astock_qlib.workflow.QLIB_DIR", data)
    captured = {}

    def fake_workflow(path, *, experiment_name, uri_folder):
        captured.update(yaml.safe_load(Path(path).read_text(encoding="utf-8")))

    monkeypatch.setattr("qlib.cli.run.workflow", fake_workflow)
    run_workflow(
        source,
        uri_folder=tmp_path / "mlruns",
        market="focus",
        benchmark="SH000905",
        topk=3,
        n_drop=1,
        account=1_000_000,
    )

    assert captured["market"] == "focus"
    assert captured["data_handler_config"]["instruments"] == "focus"
    assert (
        captured["task"]["dataset"]["kwargs"]["handler"]["kwargs"]["instruments"]
        == "focus"
    )
    port = captured["port_analysis_config"]
    assert port["strategy"]["kwargs"] == {"topk": 3, "n_drop": 1}
    assert port["backtest"]["benchmark"] == "SH000905"
    assert port["backtest"]["account"] == 1_000_000
