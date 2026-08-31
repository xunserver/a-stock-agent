from __future__ import annotations

import argparse

import pandas as pd

from astock_qlib.cli import handlers
from astock_qlib.cli.formatters import print_features, print_top_scores
from astock_qlib.cli.parser import build_parser, split_csv_keep_parens


def test_parser_preserves_public_feature_arguments() -> None:
    args = build_parser().parse_args(
        ["--pool", "focus", "--json", "features", "--codes", "000001,SH600519"]
    )

    assert args.cmd == "features"
    assert args.pool == "focus"
    assert args.json is True
    assert args.fields == "$close,$volume"


def test_split_csv_keeps_qlib_function_arguments() -> None:
    assert split_csv_keep_parens("$close,Ref($close, 1)/$close,Mean($volume,5)") == [
        "$close",
        "Ref($close, 1)/$close",
        "Mean($volume,5)",
    ]


def test_dispatch_features_passes_parsed_expressions(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_frame(codes, fields, *, start, end):
        captured.update(codes=codes, fields=fields, start=start, end=end)
        return pd.DataFrame({"$close": [10]}, index=pd.Index(["000001"], name="instrument"))

    monkeypatch.setattr(handlers, "feature_frame", fake_frame)
    monkeypatch.setattr(handlers, "print_features", lambda frame, *, as_json: captured.update(json=as_json))
    handlers.dispatch(
        argparse.Namespace(
            cmd="features",
            codes="000001,SH600519",
            fields="$close,Ref($close,1)",
            start="2026-08-01",
            end="2026-08-28",
            json=True,
        )
    )

    assert captured == {
        "codes": ["000001", "SH600519"],
        "fields": ["$close", "Ref($close,1)"],
        "start": "2026-08-01",
        "end": "2026-08-28",
        "json": True,
    }


def test_formatters_keep_human_and_json_feature_output(capsys) -> None:
    print_top_scores(
        {
            "as_of": "2026-08-28",
            "universe_size": 1,
            "pred_path": "/tmp/pred.pkl",
            "top": [{"rank": 1, "code": "000001", "name": "平安银行", "symbol": "SZ000001", "score": 0.5}],
        },
        5,
    )
    assert "日期 2026-08-28  池子 1 只  取 Top5" in capsys.readouterr().out

    frame = pd.DataFrame({"$close": [10]}, index=pd.Index(["000001"], name="instrument"))
    print_features(frame, as_json=True)
    assert '"$close": 10' in capsys.readouterr().out
