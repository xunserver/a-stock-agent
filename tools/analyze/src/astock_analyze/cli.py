"""CLI: status / run / report."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from astock_analyze.config import AnalyzeError, parse_analysts
from astock_analyze.run import collect_status, load_complete_report, run_analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A 股多智能体分析（TradingAgents 包装层）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON 输出（进度仍在 stderr；成功时 stdout 最后一段是 JSON）",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    status = sub.add_parser("status", help="检查依赖、密钥是否已配、最近报告")
    status.add_argument("--json", action="store_true")

    run = sub.add_parser("run", help="对一只股票跑一次分析")
    run.add_argument("--code", required=True, help="6 位代码，如 000001")
    run.add_argument("--date", help="交易日 YYYY-MM-DD；省略则用库内 last_bar 或今天")
    run.add_argument(
        "--analysts",
        help="逗号分隔：market,news,fundamentals,social",
    )
    run.add_argument("--pool", help="若给出，则要求代码在该池活跃成员中")
    run.add_argument("--json", action="store_true")

    report = sub.add_parser("report", help="把 complete_report.md 打到 stdout")
    report.add_argument("--code", required=True)
    report.add_argument("--date", required=True, help="YYYY-MM-DD")
    report.add_argument("--run-id", dest="run_id", help="省略则取该日最新一次")
    report.add_argument("--json", action="store_true")
    return parser


def emit_json(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")
    sys.stdout.flush()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.cmd == "status":
            emit_json(collect_status())
            return 0
        if args.cmd == "run":
            analysts = parse_analysts(args.analysts) if args.analysts is not None else None
            result = run_analysis(
                raw_code=args.code,
                date=args.date,
                analysts=analysts,
                pool=args.pool,
            )
            emit_json(result)
            return 0
        if args.cmd == "report":
            text = load_complete_report(args.code, args.date, args.run_id)
            sys.stdout.write(text)
            if not text.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()
            return 0
        parser.error(f"未知命令: {args.cmd}")
    except AnalyzeError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return exc.exit_code
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr, flush=True)
        return 130
    return 1
