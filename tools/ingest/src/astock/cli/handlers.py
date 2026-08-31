"""Use-case dispatch for already-parsed ingest CLI arguments."""

from __future__ import annotations

import argparse

from astock.boards import sync_boards
from astock.cli.formatters import format_pool_list, format_pool_summary, format_stock_catalog, print_json
from astock.cli.parser import parse_codes
from astock.events import fetch_stock_events, format_stock_events
from astock.ingest import ingest_calendar
from astock.news import fetch_stock_news, format_stock_news
from astock.pool import add_codes_to_pool, add_codes_to_stocks, add_index_to_pool, add_index_to_stocks
from astock.providers.defaults import default_bar_source, default_calendar_source
from astock.quotes import sync_quotes
from astock.stock import format_stock_snapshot, resolve_sync_codes, stock_snapshot, sync_stock, sync_stock_info
from astock_core.db import MarketDB
from astock_core.paths import DB_PATH


def dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Run the selected use case while preserving the public CLI output contract."""
    if args.cmd == "stock" and args.stock_cmd == "news":
        code = args.code.strip().zfill(6)
        items = fetch_stock_news(code, limit=args.limit)
        payload = {"code": code, "count": len(items), "news": items}
        print_json(payload) if args.json else print(format_stock_news(payload))
        return
    if args.cmd == "stock" and args.stock_cmd == "events":
        code = args.code.strip().zfill(6)
        items = fetch_stock_events(code, args.kind, limit=args.limit)
        payload = {"code": code, "kind": args.kind, "count": len(items), "events": items}
        print_json(payload) if args.json else print(format_stock_events(payload))
        return

    with MarketDB(DB_PATH) as db:
        if args.cmd == "status":
            plan = db.pool_quote_plan(args.pool)
            payload = {
                "db": str(DB_PATH), "pool": args.pool,
                "need_sync": len(plan["full"]) + len(plan["fill"]),
                "need_full": len(plan["full"]), "need_fill": len(plan["fill"]),
                "already_current": len(plan["current"]),
                "profile_filled": db.profile_filled_count(args.pool), **db.counts(args.pool),
            }
            print_json(payload) if args.json else print(format_pool_summary(db, args.pool))
            return

        if args.cmd == "pool":
            if not args.pool_cmd:
                payload = {"pool": args.pool, "profile_filled": db.profile_filled_count(args.pool), **db.counts(args.pool)}
                print_json(payload) if args.json else print(format_pool_summary(db, args.pool))
                return
            if args.pool_cmd == "add":
                if bool(args.index) == bool(args.codes):
                    parser.error("pool add 需要恰好一个：--index 或 --codes")
                print_json(add_index_to_pool(db, args.index, pool_id=args.pool, replace=False) if args.index else add_codes_to_pool(db, parse_codes(args.codes), pool_id=args.pool))
                return
            if args.pool_cmd == "set":
                print_json(add_index_to_pool(db, args.index, pool_id=args.pool, replace=True))
                return
            if args.pool_cmd == "remove":
                result = db.remove_pool_members(args.pool, parse_codes(args.codes))
                result["pool"] = args.pool
                result["active"] = len(db.active_pool_codes(args.pool))
                print_json(result)
                return
            members = db.list_pool_members(args.pool, include_removed=args.all)
            if args.json:
                print_json({"pool": args.pool, "count": len(members), "members": members})
            else:
                print(f"池 {args.pool}  {len(members)} 只")
                print(format_pool_list(members))
            return

        if args.cmd == "stock":
            if args.stock_cmd == "list":
                stocks = db.list_stocks()
                payload = {"count": len(stocks), "stocks": stocks}
                if args.json:
                    print_json(payload)
                else:
                    print(f"系统内 {len(stocks)} 只")
                    print(format_stock_catalog(stocks))
                return
            if args.stock_cmd == "add":
                if bool(args.index) == bool(args.codes):
                    parser.error("stock add 需要恰好一个：--index 或 --codes")
                print_json(add_index_to_stocks(db, args.index) if args.index else add_codes_to_stocks(db, parse_codes(args.codes)))
                return
            if args.stock_cmd == "remove":
                print_json(db.remove_stocks(parse_codes(args.codes)))
                return
            if args.stock_cmd == "show":
                snap = stock_snapshot(db, args.code.strip().zfill(6), pool_id=args.pool)
                print_json(snap) if args.json else print(format_stock_snapshot(snap))
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
            print_json(sync_stock(db, codes, pool_id=args.pool, do_info=do_info, do_quotes=do_quotes, sleep=args.sleep, with_statements=bool(getattr(args, "statements", False))))
            return

        if args.cmd == "boards":
            kinds = ("industry", "concept") if args.kind == "all" else (args.kind,)
            result = sync_boards(db, kinds=kinds, sleep=args.sleep, limit=args.limit)
            result["db"] = str(DB_PATH)
            result.update(db.counts(args.pool))
            print_json(result)
            return

        if args.cmd == "calendar":
            rows = ingest_calendar(
                db,
                force=bool(getattr(args, "force", False)),
                calendar_source=default_calendar_source(),
            )
            print_json({"calendar": rows, "market": "cn_a", "db": str(DB_PATH)})
            return

        if args.cmd != "quotes":
            parser.error(f"未知命令: {args.cmd}")
        if args.quotes_cmd == "pending":
            plan = db.pool_quote_plan(args.pool)
            print_json({"pool": args.pool, "need_sync": plan["full"] + plan["fill"], "need_full": plan["full"], "need_fill": plan["fill"], "already_current": len(plan["current"])})
            return
        result = sync_quotes(
            db, pool_id=args.pool, codes=parse_codes(getattr(args, "codes", None)) or None,
            adjust=args.adjust, sleep=args.sleep, limit=args.limit,
            start_date=getattr(args, "history_start", None),
            periods=tuple(item.strip() for item in args.periods.split(",") if item.strip()) if getattr(args, "periods", None) else None,
            bar_source=default_bar_source(),
            calendar_source=default_calendar_source(),
        )
        info_codes = parse_codes(getattr(args, "codes", None)) or db.active_pool_codes(args.pool)
        if info_codes:
            result.update(sync_stock_info(db, info_codes, sleep=args.sleep))
        result["db"] = str(DB_PATH)
        result.update(db.counts(args.pool))
        print_json(result)
