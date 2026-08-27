from __future__ import annotations

import argparse
import json
import logging

from astock_core.db import MarketDB
from astock_core.paths import DB_PATH, DEFAULT_ADJUST, DEFAULT_POOL_ID, QLIB_DIR
from astock_qlib.dump import dump_qlib
from astock_qlib.ranking import top_scores
from astock_qlib.runtime import feature_frame, qlib_status, smoke
from astock_qlib.workflow import DEFAULT_CONFIG, run_workflow


def _print(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _split_csv_keep_parens(raw: str) -> list[str]:
    """按逗号拆分，但括号内的逗号（如 Ref($close,1)）保留。"""
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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="把本地 market.db 接到 Qlib 研究框架")
    parser.add_argument("--pool", default=DEFAULT_POOL_ID)
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    dump = sub.add_parser("dump", help="从 SQLite 生成 Qlib .bin 数据")
    dump.add_argument("--adjust", default=DEFAULT_ADJUST, choices=["", "qfq", "hfq"])

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

    wf = sub.add_parser("workflow", help="跑 LightGBM + Alpha158 全流程（训练/信号/回测）")
    wf.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="workflow yaml，默认 configs/workflow_lightgbm_alpha158.yaml",
    )
    wf.add_argument("--experiment", default="astock_lightgbm", help="mlflow experiment 名")

    top = sub.add_parser("top", help="从最近一次 300 池预测里取出分数最高的 N 只")
    top.add_argument("-n", type=int, default=5, help="取前 N，默认 5")
    top.add_argument("--as-of", help="指定交易日 YYYY-MM-DD；默认用 pred 里最后一天")

    args = parser.parse_args()
    if args.cmd == "dump":
        with MarketDB(DB_PATH) as db:
            payload = dump_qlib(db, dest=QLIB_DIR, adjust=args.adjust, pool_id=args.pool)
        _print(payload)
        return
    if args.cmd == "status":
        _print(qlib_status())
        return
    if args.cmd == "smoke":
        _print(smoke())
        return
    if args.cmd == "workflow":
        mlruns = run_workflow(args.config, experiment_name=args.experiment)
        _print({"ok": True, "config": args.config, "experiment": args.experiment, "mlruns": str(mlruns)})
        return
    if args.cmd == "top":
        payload = top_scores(args.n, as_of=args.as_of)
        if args.json:
            _print(payload)
            return
        print(f"日期 {payload['as_of']}  池子 {payload['universe_size']} 只  取 Top{args.n}")
        print(f"来源 {payload['pred_path']}")
        for row in payload["top"]:
            print(
                f"{row['rank']}. {row['code']} {row['name']:<8}  "
                f"{row['symbol']}  score={row['score']:.6f}"
            )
        return
    codes = _split_csv_keep_parens(args.codes)
    fields = _split_csv_keep_parens(args.fields)
    frame = feature_frame(codes, fields, start=args.start, end=args.end)
    if args.json:
        _print(json.loads(frame.reset_index().to_json(orient="records", date_format="iso")))
        return
    print(frame.to_string())


if __name__ == "__main__":
    main()
