"""Argument parsing for ``python -m astock_qlib``."""

from __future__ import annotations

import argparse

from astock_core.paths import DEFAULT_ADJUST, DEFAULT_POOL_ID

from astock_qlib.workflow import DEFAULT_CONFIG


def split_csv_keep_parens(raw: str) -> list[str]:
    """Split comma-separated Qlib expressions without splitting function calls."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in raw:
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == "," and depth == 0:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
        else:
            buf.append(ch)
    part = "".join(buf).strip()
    if part:
        parts.append(part)
    return parts


def build_parser() -> argparse.ArgumentParser:
    """Build the stable public CLI parser shared by all command invocations."""
    parser = argparse.ArgumentParser(description="把本地 market.db 接到 Qlib 研究框架")
    parser.add_argument("--pool", default=DEFAULT_POOL_ID)
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    dump = sub.add_parser("dump", help="从 SQLite 生成 Qlib .bin 数据（全市场，旧版）")
    dump.add_argument("--adjust", default=DEFAULT_ADJUST, choices=["", "qfq", "hfq"])

    prepare = sub.add_parser("prepare", help="为股票池准备量化数据")
    prepare.add_argument("--benchmark", default="SH000300")

    sub.add_parser("status", help="查看 data/qlib 是否已就绪")
    sub.add_parser("smoke", help="初始化 Qlib 并读几根 K，确认数据可用")

    features = sub.add_parser("features", help="用 Qlib 表达式取特征")
    features.add_argument("--codes", required=True, help="逗号分隔，6 位代码或 SH/SZ 代码")
    features.add_argument(
        "--fields",
        default="$close,$volume",
        help="逗号分隔字段；括号内的逗号会保留，如 $close,Ref($close,1)/$close",
    )
    features.add_argument("--start")
    features.add_argument("--end")

    workflow = sub.add_parser("workflow", help="跑 LightGBM + Alpha158 全流程（训练/信号/回测）")
    workflow.add_argument("--config", default=str(DEFAULT_CONFIG), help="workflow yaml，默认 configs/workflow_lightgbm_alpha158.yaml")
    workflow.add_argument("--experiment", default="astock_lightgbm", help="mlflow experiment 名")

    top = sub.add_parser("top", help="从最近一次 300 池预测里取出分数最高的 N 只")
    top.add_argument("-n", type=int, default=5, help="取前 N，默认 5")
    top.add_argument("--as-of", help="指定交易日 YYYY-MM-DD；默认用 pred 里最后一天")

    select = sub.add_parser("select", help="按股票池运行 workflow 并生成候选结果")
    select.add_argument("--run-id", required=True)
    select.add_argument("--config", required=True)
    select.add_argument("--benchmark", required=True)
    select.add_argument("--topk", required=True, type=int)
    select.add_argument("--n-drop", required=True, type=int)
    select.add_argument("--account", required=True, type=float)
    select.add_argument("--data-end")
    select.add_argument("--test-start")
    select.add_argument("--learning-rate", type=float)
    return parser
