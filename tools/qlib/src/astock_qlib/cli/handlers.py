"""Dispatch parsed CLI arguments to Qlib use-cases."""

from __future__ import annotations

import argparse

from astock_core.db import MarketDB
from astock_core.paths import DB_PATH, QLIB_DIR

from astock_qlib.cli.formatters import print_features, print_json, print_top_scores
from astock_qlib.cli.parser import split_csv_keep_parens
from astock_qlib.dump import dump_qlib
from astock_qlib.ranking import top_scores
from astock_qlib.runtime import feature_frame, qlib_status, smoke
from astock_qlib.selection import prepare_pool_data, run_selection
from astock_qlib.workflow import run_workflow


def dispatch(args: argparse.Namespace) -> None:
    """Run one parsed command while preserving the public CLI's output contract."""
    if args.cmd == "dump":
        with MarketDB(DB_PATH) as db:
            print_json(dump_qlib(db, dest=QLIB_DIR, adjust=args.adjust, pool_id=args.pool))
    elif args.cmd == "prepare":
        print_json(prepare_pool_data(pool_id=args.pool, benchmark=args.benchmark))
    elif args.cmd == "status":
        print_json(qlib_status())
    elif args.cmd == "smoke":
        print_json(smoke())
    elif args.cmd == "workflow":
        mlruns = run_workflow(args.config, experiment_name=args.experiment)
        print_json({"ok": True, "config": args.config, "experiment": args.experiment, "mlruns": str(mlruns)})
    elif args.cmd == "top":
        payload = top_scores(args.n, as_of=args.as_of)
        if args.json:
            print_json(payload)
        else:
            print_top_scores(payload, args.n)
    elif args.cmd == "select":
        workflow: dict[str, object] = {"config": args.config, "benchmark": args.benchmark, "topk": args.topk, "n_drop": args.n_drop, "account": args.account}
        for option in ("data_end", "test_start", "learning_rate"):
            value = getattr(args, option)
            if value is not None:
                workflow[option] = value
        print_json(run_selection(pool_id=args.pool, run_id=args.run_id, workflow=workflow))
    elif args.cmd == "features":
        frame = feature_frame(split_csv_keep_parens(args.codes), split_csv_keep_parens(args.fields), start=args.start, end=args.end)
        print_features(frame, as_json=args.json)
    else:  # argparse guarantees this is unreachable; keep dispatch safe for library callers.
        raise ValueError(f"unsupported Qlib command: {args.cmd}")
