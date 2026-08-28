from __future__ import annotations

import argparse
import json

from astock.config import index_aliases
from astock.boards import sync_boards
from astock.ingest import configure_logging
from astock.pool import add_codes_to_pool, add_codes_to_stocks, add_index_to_pool, add_index_to_stocks
from astock.quotes import sync_quotes
from astock.events import EVENT_KINDS, fetch_stock_events, format_stock_events
from astock.news import fetch_stock_news, format_stock_news
from astock.stock import (
    format_stock_snapshot,
    resolve_sync_codes,
    stock_snapshot,
    sync_stock,
    sync_stock_info,
)
from astock_core.db import MarketDB
from astock_core.paths import DB_PATH, DEFAULT_POOL_ID


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _codes(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip().zfill(6) for item in raw.split(",") if item.strip()]


def _format_pool_summary(db: MarketDB, pool_id: str) -> str:
    plan = db.pool_quote_plan(pool_id)
    counts = db.counts(pool_id)
    active = counts.get("pool_active", 0)
    return "\n".join(
        [
            f"池 {pool_id}",
            f"在池 {active}  已移除 {counts.get('pool_removed', 0)}",
            f"行情  需同步 {len(plan['full']) + len(plan['fill'])}  已齐 {len(plan['current'])}",
            f"资料  已同步行业 {db.profile_filled_count(pool_id)} / {active}",
            f"库    {DB_PATH}",
        ]
    )


def _format_pool_list(members: list[dict]) -> str:
    if not members:
        return "(空)"
    header = f"{'代码':<8} {'名称':<10} {'状态':<8} {'最新K':<12} {'来源'}"
    lines = [header, "-" * 56]
    for item in members:
        lines.append(
            f"{item.get('code', ''):<8} {str(item.get('name') or ''):<10} "
            f"{item.get('status', ''):<8} {str(item.get('last_bar') or '-'):<12} "
            f"{item.get('source') or ''}"
        )
    return "\n".join(lines)


def _format_stock_catalog(stocks: list[dict]) -> str:
    if not stocks:
        return "(空)"
    header = f"{'代码':<8} {'名称':<10} {'行业':<10} {'最新K':<12} {'所在池'}"
    lines = [header, "-" * 64]
    for item in stocks:
        pools = item.get("pools") or []
        pool_text = ",".join(str(pool.get("id") or "") for pool in pools) or "-"
        lines.append(
            f"{item.get('code', ''):<8} {str(item.get('name') or ''):<10} "
            f"{str(item.get('industry') or '-'):<10} {str(item.get('last_bar') or '-'):<12} "
            f"{pool_text}"
        )
    return "\n".join(lines)


def _common_args() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--pool", default=DEFAULT_POOL_ID, help="股票池 id，默认 default")
    common.add_argument("--json", action="store_true", help="JSON 输出")
    return common


def main() -> None:
    common = _common_args()
    parser = argparse.ArgumentParser(
        description="股票管理：系统股票目录 + 股票池 + 个股资料/行情。--pool 不写则用 default。",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    pool = sub.add_parser("pool", help="股票池：增删、指数填池、查看", parents=[common])
    pool_sub = pool.add_subparsers(dest="pool_cmd")

    add = pool_sub.add_parser(
        "add",
        help="加入成分（指数并入或手工代码），不剔除已有成员",
        parents=[common],
    )
    add.add_argument("--index", help=f"指数别名或代码，如 hs300。别名：{', '.join(index_aliases())}")
    add.add_argument("--codes", help="逗号分隔股票代码")

    replace = pool_sub.add_parser(
        "set",
        help="用指数成分覆盖股票池（不在指数中的标为移除，行情保留）",
        parents=[common],
    )
    replace.add_argument("--index", required=True)

    remove = pool_sub.add_parser("remove", help="移出股票池（不删历史行情）", parents=[common])
    remove.add_argument("--codes", required=True)

    listing = pool_sub.add_parser("list", help="列出池内股票", parents=[common])
    listing.add_argument("--all", action="store_true", help="包含已移除成员")

    stock = sub.add_parser(
        "stock",
        help="系统股票目录，以及个股资料/行情查看与补齐",
        parents=[common],
    )
    stock_sub = stock.add_subparsers(dest="stock_cmd", required=True)
    stock_sub.add_parser("list", help="列出系统内股票", parents=[common])
    sadd = stock_sub.add_parser(
        "add",
        help="加入系统股票目录（指数或手工代码）",
        parents=[common],
    )
    sadd.add_argument("--index", help=f"指数别名或代码，如 hs300。别名：{', '.join(index_aliases())}")
    sadd.add_argument("--codes", help="逗号分隔股票代码")
    srm = stock_sub.add_parser(
        "remove",
        help="从系统移除（在任一股票池则拒绝，不删日线）",
        parents=[common],
    )
    srm.add_argument("--codes", required=True)
    show = stock_sub.add_parser(
        "show",
        help="查看个股资料、库内行情摘要、最新交易日 K 线",
        parents=[common],
    )
    show.add_argument("code", help="股票代码，如 000001")
    news = stock_sub.add_parser(
        "news",
        help="东方财富个股新闻（实时，不入库）",
        parents=[common],
    )
    news.add_argument("code", help="股票代码，如 000001")
    news.add_argument("--limit", type=int, default=20, help="最多返回条数")
    events = stock_sub.add_parser(
        "events",
        help="个股公告/研报/大宗/股东变更（实时，不入库）",
        parents=[common],
    )
    events.add_argument("code", help="股票代码，如 000001")
    events.add_argument(
        "--kind",
        required=True,
        choices=sorted(EVENT_KINDS),
        help="事件类型",
    )
    events.add_argument("--limit", type=int, default=None, help="最多返回条数")
    sync = stock_sub.add_parser(
        "sync",
        help="同步个股资料并/或补齐日线；不写代码则处理当前池全部活跃成员",
        parents=[common],
    )
    sync.add_argument("codes", nargs="?", help="一个或多个代码，逗号分隔")
    sync.add_argument("--info", action="store_true", help="只同步资料（行情快照/估值/财务/ST/停牌）")
    sync.add_argument("--quotes", action="store_true", help="只补齐日线")
    sync.add_argument("--statements", action="store_true", help="同步三大报表明细（较慢，默认关闭）")
    sync.add_argument("--sleep", type=float, default=None)
    sync.add_argument("--add-to-pool", action="store_true", help="若代码不在当前池则加入")

    quotes = sub.add_parser("quotes", help="按股票池批量同步日线", parents=[common])
    quotes_sub = quotes.add_subparsers(dest="quotes_cmd", required=True)
    qsync = quotes_sub.add_parser(
        "sync",
        help="池内新票拉全历史，其余补齐到最近交易日，并写入估值/财务资料",
        parents=[common],
    )
    qsync.add_argument("--sleep", type=float, default=None)
    qsync.add_argument("--adjust", default=None, choices=["", "qfq", "hfq"])
    qsync.add_argument("--history-start", default=None, help="历史起点 YYYYMMDD，默认读系统设置")
    qsync.add_argument("--periods", default=None, help="逗号分隔周期，默认读系统设置")
    qsync.add_argument("--limit", type=int)
    qsync.add_argument("--codes", help="逗号分隔股票代码；不写则同步当前池全部活跃成员")
    quotes_sub.add_parser("pending", help="只看谁需要拉全历史 / 补齐", parents=[common])

    boards = sub.add_parser("boards", help="东财行业/概念板块", parents=[common])
    boards_sub = boards.add_subparsers(dest="boards_cmd", required=True)
    bsync = boards_sub.add_parser(
        "sync",
        help="同步行业/概念名录与成分；成员只保留系统内已有股票",
        parents=[common],
    )
    bsync.add_argument(
        "--kind",
        default="all",
        choices=["all", "industry", "concept"],
        help="同步范围，默认 all",
    )
    bsync.add_argument("--sleep", type=float, default=None)
    bsync.add_argument("--limit", type=int, help="每种类型最多同步多少个板块（试跑）")

    sub.add_parser("status", help="库规模与当前池摘要", parents=[common])

    args = parser.parse_args()
    if args.cmd == "stock" and args.stock_cmd == "news":
        configure_logging()
        code = args.code.strip().zfill(6)
        items = fetch_stock_news(code, limit=args.limit)
        payload = {"code": code, "count": len(items), "news": items}
        _print(payload) if args.json else print(format_stock_news(payload))
        return
    if args.cmd == "stock" and args.stock_cmd == "events":
        configure_logging()
        code = args.code.strip().zfill(6)
        items = fetch_stock_events(code, args.kind, limit=args.limit)
        payload = {
            "code": code,
            "kind": args.kind,
            "count": len(items),
            "events": items,
        }
        _print(payload) if args.json else print(format_stock_events(payload))
        return

    configure_logging()
    with MarketDB(DB_PATH) as db:
        if args.cmd == "status":
            plan = db.pool_quote_plan(args.pool)
            payload = {
                "db": str(DB_PATH),
                "pool": args.pool,
                "need_sync": len(plan["full"]) + len(plan["fill"]),
                "need_full": len(plan["full"]),
                "need_fill": len(plan["fill"]),
                "already_current": len(plan["current"]),
                "profile_filled": db.profile_filled_count(args.pool),
                **db.counts(args.pool),
            }
            _print(payload) if args.json else print(_format_pool_summary(db, args.pool))
            return

        if args.cmd == "pool":
            if not args.pool_cmd:
                payload = {
                    "pool": args.pool,
                    "profile_filled": db.profile_filled_count(args.pool),
                    **db.counts(args.pool),
                }
                _print(payload) if args.json else print(_format_pool_summary(db, args.pool))
                return
            if args.pool_cmd == "add":
                if bool(args.index) == bool(args.codes):
                    parser.error("pool add 需要恰好一个：--index 或 --codes")
                if args.index:
                    _print(add_index_to_pool(db, args.index, pool_id=args.pool, replace=False))
                else:
                    _print(add_codes_to_pool(db, _codes(args.codes), pool_id=args.pool))
                return
            if args.pool_cmd == "set":
                _print(add_index_to_pool(db, args.index, pool_id=args.pool, replace=True))
                return
            if args.pool_cmd == "remove":
                result = db.remove_pool_members(args.pool, _codes(args.codes))
                result["pool"] = args.pool
                result["active"] = len(db.active_pool_codes(args.pool))
                _print(result)
                return
            members = db.list_pool_members(args.pool, include_removed=args.all)
            if args.json:
                _print({"pool": args.pool, "count": len(members), "members": members})
            else:
                print(f"池 {args.pool}  {len(members)} 只")
                print(_format_pool_list(members))
            return

        if args.cmd == "stock":
            if args.stock_cmd == "list":
                stocks = db.list_stocks()
                payload = {"count": len(stocks), "stocks": stocks}
                if args.json:
                    _print(payload)
                else:
                    print(f"系统内 {len(stocks)} 只")
                    print(_format_stock_catalog(stocks))
                return
            if args.stock_cmd == "add":
                if bool(args.index) == bool(args.codes):
                    parser.error("stock add 需要恰好一个：--index 或 --codes")
                if args.index:
                    _print(add_index_to_stocks(db, args.index))
                else:
                    _print(add_codes_to_stocks(db, _codes(args.codes)))
                return
            if args.stock_cmd == "remove":
                _print(db.remove_stocks(_codes(args.codes)))
                return
            if args.stock_cmd == "show":
                code = args.code.strip().zfill(6)
                snap = stock_snapshot(db, code, pool_id=args.pool)
                _print(snap) if args.json else print(format_stock_snapshot(snap))
                return
            codes = resolve_sync_codes(db, args.codes, args.pool)
            if not codes:
                parser.error("当前池没有活跃成员，请指定代码或先 pool add")
            if args.add_to_pool:
                add_codes_to_stocks(db, codes)
                add_codes_to_pool(db, codes, pool_id=args.pool)
            do_info = args.info or not args.quotes
            do_quotes = args.quotes or not args.info
            if args.info and args.quotes:
                do_info = do_quotes = True
            result = sync_stock(
                db,
                codes,
                pool_id=args.pool,
                do_info=do_info,
                do_quotes=do_quotes,
                sleep=args.sleep,
                with_statements=bool(getattr(args, "statements", False)),
            )
            _print(result)
            return

        if args.cmd == "boards":
            kinds = ("industry", "concept") if args.kind == "all" else (args.kind,)
            result = sync_boards(
                db,
                kinds=kinds,
                sleep=args.sleep,
                limit=args.limit,
            )
            result["db"] = str(DB_PATH)
            result.update(db.counts(args.pool))
            _print(result)
            return

        if args.quotes_cmd == "pending":
            plan = db.pool_quote_plan(args.pool)
            payload = {
                "pool": args.pool,
                "need_sync": plan["full"] + plan["fill"],
                "need_full": plan["full"],
                "need_fill": plan["fill"],
                "already_current": len(plan["current"]),
            }
            _print(payload)
            return
        result = sync_quotes(
            db,
            pool_id=args.pool,
            codes=_codes(getattr(args, "codes", None)) or None,
            adjust=args.adjust,
            sleep=args.sleep,
            limit=args.limit,
            start_date=getattr(args, "history_start", None),
            periods=(
                tuple(item.strip() for item in args.periods.split(",") if item.strip())
                if getattr(args, "periods", None)
                else None
            ),
        )
        info_codes = _codes(getattr(args, "codes", None)) or db.active_pool_codes(args.pool)
        if info_codes:
            result.update(sync_stock_info(db, info_codes, sleep=args.sleep))
        result["db"] = str(DB_PATH)
        result.update(db.counts(args.pool))
        _print(result)


if __name__ == "__main__":
    main()
