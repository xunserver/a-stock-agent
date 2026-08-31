from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

from astock_ctl.client import (
    CoreUnavailable,
    base_url,
    find_repo_root,
    follow_events,
    request,
)


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _format_status(data: dict[str, Any]) -> str:
    pool = data.get("pool", "default")
    active = data.get("pool_active", 0)
    trade_date = data.get("trade_date") or "—"
    return "\n".join(
        [
            f"池 {pool}",
            f"当前交易日 {trade_date}",
            f"在池 {active}  已移除 {data.get('pool_removed', 0)}",
            (
                f"行情  需同步 {data.get('need_sync', (data.get('need_full') or 0) + (data.get('need_fill') or 0))}  "
                f"已齐 {data.get('already_current', 0)}"
            ),
            f"资料  已同步行业 {data.get('profile_filled', 0)} / {active}",
            f"库    {data.get('db', '')}",
        ]
    )


def _format_job(job: dict[str, Any]) -> str:
    name = str(job.get("name") or job.get("type") or "")
    line = f"{job['id']}  {job['status']:<10}  {name}"
    if job.get("error"):
        line += f"  {job['error']}"
    return line


def _common_args() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON 输出")
    return common


def main() -> None:
    common = _common_args()
    parser = argparse.ArgumentParser(
        description="My Trading CLI：把命令提交给 core 常驻进程。core 未运行时会直接报错。",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="启动 core 常驻进程")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)

    status = sub.add_parser("status", help="查询库规模与当前池摘要", parents=[common])
    status.add_argument("--pool", default=None, help="不写则用系统设置里的默认股票池")

    quotes = sub.add_parser("quotes", help="按股票池批量同步日线", parents=[common])
    quotes_sub = quotes.add_subparsers(dest="quotes_cmd", required=True)
    qsync = quotes_sub.add_parser(
        "sync",
        help="提交 quotes.sync，并默认跟踪日志直到结束",
        parents=[common],
    )
    qsync.add_argument("--pool", default=None, help="不写则用系统设置里的默认股票池")
    qsync.add_argument("--sleep", type=float)
    qsync.add_argument("--adjust")
    qsync.add_argument("--limit", type=int)
    qsync.add_argument("--no-wait", action="store_true", help="只提交，不跟踪")

    settings = sub.add_parser("settings", help="查看或更新系统设置", parents=[common])
    settings_sub = settings.add_subparsers(dest="settings_cmd")
    sget = settings_sub.add_parser("get", help="读取当前设置，可指定模块和小类", parents=[common])
    sget.add_argument("--module")
    sget.add_argument("--section")
    settings_sub.add_parser("catalog", help="列出模块、小类和 schema", parents=[common])
    sset = settings_sub.add_parser("set", help="更新设置（只改传入的项）", parents=[common])
    sset.add_argument("--module", help="设置模块，例如 ingest / analyze / qlib")
    sset.add_argument("--section", help="小类，例如 quotes / llm / workflow")
    sset.add_argument("--values", help="该小类的 JSON 对象")
    sset.add_argument("--pool")
    sset.add_argument("--adjust", choices=["", "qfq", "hfq"])
    sset.add_argument("--sleep", type=float)
    sset.add_argument("--sync-enabled", action=argparse.BooleanOptionalAction)
    sset.add_argument("--sync-time")
    sset.add_argument("--timezone")

    pool = sub.add_parser("pool", help="创建/删除股票池，或增减成员", parents=[common])
    pool_sub = pool.add_subparsers(dest="pool_cmd", required=True)
    pool_sub.add_parser("ls", help="列出全部股票池", parents=[common])
    pcreate = pool_sub.add_parser("create", help="新建股票池", parents=[common])
    pcreate.add_argument("pool_id")
    pcreate.add_argument("--name")
    pdelete = pool_sub.add_parser("delete", help="删除股票池（不删日线）", parents=[common])
    pdelete.add_argument("pool_id")
    padd = pool_sub.add_parser("add", help="加入成分：--codes 或 --index（成员须已在系统股票里）", parents=[common])
    padd.add_argument("--pool", default=None)
    padd.add_argument("--index")
    padd.add_argument("--codes")
    pset = pool_sub.add_parser("set", help="用指数覆盖当前池（只保留系统里已有的成分）", parents=[common])
    pset.add_argument("--pool", default=None)
    pset.add_argument("--index", required=True)
    premove = pool_sub.add_parser("remove", help="移出成分", parents=[common])
    premove.add_argument("--pool", default=None)
    premove.add_argument("--codes", required=True)

    stock = sub.add_parser("stock", help="管理系统内有哪些股票", parents=[common])
    stock_sub = stock.add_subparsers(dest="stock_cmd", required=True)
    stock_sub.add_parser("ls", help="列出系统股票", parents=[common])
    sadd = stock_sub.add_parser("add", help="加入系统：--codes 或 --index", parents=[common])
    sadd.add_argument("--index")
    sadd.add_argument("--codes")
    srm = stock_sub.add_parser("remove", help="从系统移除（在池则拒绝，不删日线）", parents=[common])
    srm.add_argument("--codes", required=True)

    analyze = sub.add_parser("analyze", help="AI 分析", parents=[common])
    analyze_sub = analyze.add_subparsers(dest="analyze_cmd", required=True)
    arun = analyze_sub.add_parser(
        "run",
        help="提交 analyze.run，并默认跟踪日志直到结束",
        parents=[common],
    )
    arun.add_argument("--code", required=True)
    arun.add_argument("--date")
    arun.add_argument("--pool", default=None)
    arun.add_argument("--no-wait", action="store_true", help="只提交，不跟踪")
    alist = analyze_sub.add_parser("list", help="列出已落盘的分析报告", parents=[common])
    alist.add_argument("--code")
    ashow = analyze_sub.add_parser("show", help="查看一份分析报告", parents=[common])
    ashow.add_argument("--code", required=True)
    ashow.add_argument("--date", required=True)
    ashow.add_argument("--run-id")

    jobs = sub.add_parser("jobs", help="查看任务", parents=[common])
    jobs_sub = jobs.add_subparsers(dest="jobs_cmd")
    jobs_sub.add_parser("list", help="列出最近任务", parents=[common])
    show = jobs_sub.add_parser("show", help="查看单个任务", parents=[common])
    show.add_argument("job_id")
    logs = jobs_sub.add_parser("logs", help="跟踪任务日志直到结束", parents=[common])
    logs.add_argument("job_id")
    cancel = jobs_sub.add_parser("cancel", help="取消排队或运行中的任务", parents=[common])
    cancel.add_argument("job_id")

    args = parser.parse_args()
    try:
        _dispatch(args)
    except CoreUnavailable as exc:
        print(exc, file=sys.stderr)
        sys.exit(2)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


def _dispatch(args: argparse.Namespace) -> None:
    if args.cmd == "serve":
        _serve(args.host, args.port)
        return
    if args.cmd == "status":
        params = {"pool": args.pool} if args.pool else None
        data = request("GET", "/api/status", params=params)
        _print_json(data) if args.json else print(_format_status(data))
        return
    if args.cmd == "quotes":
        payload: dict[str, Any] = {"type": "quotes.sync"}
        if args.pool:
            payload["pool"] = args.pool
        if args.sleep is not None:
            payload["sleep"] = args.sleep
        if args.adjust is not None:
            payload["adjust"] = args.adjust
        if args.limit is not None:
            payload["limit"] = args.limit
        job = request("POST", "/api/jobs", payload=payload)
        if args.no_wait:
            _print_json(job) if args.json else print(job["id"])
            return
        print(f"任务 {job['id']}  {base_url()}", file=sys.stderr)
        final = follow_events(job["id"])
        if args.json:
            _print_json(final)
        elif final.get("result") is not None:
            _print_json(final["result"])
        if final.get("status") == "failed":
            raise RuntimeError(final.get("error") or "任务失败")
        return
    if args.cmd == "settings":
        if args.settings_cmd == "catalog":
            data = request("GET", "/api/settings/catalog")
            _print_json(data)
            return
        if args.settings_cmd == "set":
            if args.module or args.section:
                if not args.module or not args.section:
                    raise RuntimeError("分段保存需要同时提供 --module 和 --section")
                if not args.values:
                    raise RuntimeError("分段保存需要 --values JSON")
                try:
                    values = json.loads(args.values)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"values 不是合法 JSON: {exc}") from exc
                if not isinstance(values, dict):
                    raise RuntimeError("values 必须是 JSON 对象")
                job = request(
                    "POST",
                    "/api/jobs",
                    payload={
                        "type": "settings.update",
                        "module": args.module,
                        "section": args.section,
                        "values": values,
                    },
                )
                if job.get("status") == "failed":
                    raise RuntimeError(job.get("error") or "保存失败")
                data = job.get("result") or request(
                    "GET",
                    "/api/settings",
                    params={"module": args.module, "section": args.section},
                )
                _print_json(data)
                return
            patch: dict[str, Any] = {}
            if args.pool is not None:
                patch["pool"] = args.pool
            if args.adjust is not None:
                patch["adjust"] = args.adjust
            quotes_patch: dict[str, Any] = {}
            if args.sleep is not None:
                quotes_patch["sleep"] = args.sleep
            if args.sync_enabled is not None:
                quotes_patch["sync_enabled"] = args.sync_enabled
            if args.sync_time is not None:
                quotes_patch["sync_time"] = args.sync_time
            if args.timezone is not None:
                quotes_patch["timezone"] = args.timezone
            if quotes_patch:
                patch["quotes"] = quotes_patch
            if not patch:
                raise RuntimeError("没有要更新的设置项")
            job = request("POST", "/api/jobs", payload={"type": "settings.update", "settings": patch})
            if job.get("status") == "failed":
                raise RuntimeError(job.get("error") or "保存失败")
            data = job.get("result") or request("GET", "/api/settings")
            _print_json(data)
            return
        module = getattr(args, "module", None)
        section = getattr(args, "section", None)
        if module or section:
            if not module or not section:
                raise RuntimeError("读取一段设置需要同时提供 --module 和 --section")
        params = {"module": module, "section": section} if module else None
        data = request("GET", "/api/settings", params=params)
        _print_json(data)
        return
    if args.cmd == "pool":
        _dispatch_pool(args)
        return
    if args.cmd == "stock":
        _dispatch_stock(args)
        return
    if args.cmd == "analyze":
        _dispatch_analyze(args)
        return
    if args.cmd != "jobs":
        raise RuntimeError(f"未知命令: {args.cmd}")
    if args.jobs_cmd in {None, "list"}:
        data = request("GET", "/api/jobs")
        jobs = data.get("jobs") or []
        if args.json:
            _print_json(data)
            return
        if not jobs:
            print("(无任务)")
            return
        print("\n".join(_format_job(job) for job in jobs))
        return
    if args.jobs_cmd == "show":
        job = request("GET", f"/api/jobs/{args.job_id}")
        _print_json(job)
        return
    if args.jobs_cmd == "cancel":
        job = request("POST", f"/api/jobs/{args.job_id}/cancel")
        if args.json:
            _print_json(job)
            return
        print(_format_job(job))
        return
    final = follow_events(args.job_id)
    if args.json:
        _print_json(final)
    if final.get("status") == "failed":
        raise RuntimeError(final.get("error") or "任务失败")


def _dispatch_pool(args: argparse.Namespace) -> None:
    if args.pool_cmd == "ls":
        data = request("GET", "/api/pools")
        if args.json:
            _print_json(data)
            return
        pools = data.get("pools") or []
        if not pools:
            print("(无股票池)")
            return
        print("\n".join(f"{item['id']:<16} {item['name']}  在池 {item['active']}" for item in pools))
        return
    if args.pool_cmd == "create":
        payload = {"type": "pool.create", "pool": args.pool_id}
        if args.name:
            payload["name"] = args.name
        job = request("POST", "/api/jobs", payload=payload)
        _finish_job(job, json_out=args.json)
        return
    if args.pool_cmd == "delete":
        job = request("POST", "/api/jobs", payload={"type": "pool.delete", "pool": args.pool_id})
        _finish_job(job, json_out=args.json)
        return
    payload: dict[str, Any] = {"type": f"pool.{args.pool_cmd}"}
    if args.pool:
        payload["pool"] = args.pool
    if args.pool_cmd == "add":
        if bool(args.index) == bool(args.codes):
            raise RuntimeError("pool add 需要恰好一个：--index 或 --codes")
        if args.index:
            payload["index"] = args.index
        else:
            payload["codes"] = args.codes
    elif args.pool_cmd == "set":
        payload["index"] = args.index
    else:
        payload["codes"] = args.codes
    job = request("POST", "/api/jobs", payload=payload)
    wait = args.pool_cmd in {"add", "set"} and bool(getattr(args, "index", None))
    _finish_job(job, json_out=args.json, wait=wait)


def _dispatch_analyze(args: argparse.Namespace) -> None:
    if args.analyze_cmd == "run":
        payload: dict[str, Any] = {"type": "analyze.run", "code": args.code}
        if args.date:
            payload["date"] = args.date
        if args.pool:
            payload["pool"] = args.pool
        job = request("POST", "/api/jobs", payload=payload)
        if args.no_wait:
            _print_json(job) if args.json else print(job["id"])
            return
        print(f"任务 {job['id']}  {base_url()}", file=sys.stderr)
        final = follow_events(job["id"])
        if args.json:
            _print_json(final)
        elif final.get("result") is not None:
            _print_json(final["result"])
        if final.get("status") == "failed":
            raise RuntimeError(final.get("error") or "任务失败")
        return
    if args.analyze_cmd == "list":
        params = {"code": args.code} if args.code else None
        data = request("GET", "/api/analyses", params=params)
        if args.json:
            _print_json(data)
            return
        reports = data.get("reports") or []
        if not reports:
            print("(无报告)")
            return
        print(
            "\n".join(
                f"{item.get('code') or '-':<8} {item.get('name') or '-':<10} "
                f"{item.get('date') or '-':<12} {item.get('decision') or '-':<8} "
                f"{item.get('run_id') or '-'}"
                for item in reports
            )
        )
        return
    params = {"run_id": args.run_id} if args.run_id else None
    data = request("GET", f"/api/analyses/{args.code}/{args.date}", params=params)
    _print_json(data)


def _dispatch_stock(args: argparse.Namespace) -> None:
    if args.stock_cmd == "ls":
        data = request("GET", "/api/stocks")
        if args.json:
            _print_json(data)
            return
        stocks = data.get("stocks") or []
        if not stocks:
            print("(无股票)")
            return
        print(
            "\n".join(
                f"{item['code']:<8} {item.get('name') or '-':<10} "
                f"{','.join(pool['id'] for pool in item.get('pools') or []) or '-'}"
                for item in stocks
            )
        )
        return
    if args.stock_cmd == "add":
        if bool(args.index) == bool(args.codes):
            raise RuntimeError("stock add 需要恰好一个：--index 或 --codes")
        payload: dict[str, Any] = {"type": "stock.add"}
        if args.index:
            payload["index"] = args.index
        else:
            payload["codes"] = args.codes
        job = request("POST", "/api/jobs", payload=payload)
        _finish_job(job, json_out=args.json, wait=bool(args.index))
        return
    job = request(
        "POST",
        "/api/jobs",
        payload={"type": "stock.remove", "codes": args.codes},
    )
    _finish_job(job, json_out=args.json)


def _finish_job(job: dict[str, Any], *, json_out: bool, wait: bool = False) -> None:
    if wait and job.get("status") not in {"succeeded", "failed", "cancelled"}:
        print(f"任务 {job['id']}  {base_url()}", file=sys.stderr)
        job = follow_events(job["id"])
    if json_out:
        _print_json(job)
    elif job.get("result") is not None:
        _print_json(job["result"])
    elif job.get("error"):
        pass
    else:
        print(job.get("id", ""))
    if job.get("status") == "failed":
        raise RuntimeError(job.get("error") or "任务失败")


def _serve(host: str, port: int) -> None:
    core_dir = find_repo_root() / "apps" / "control-plane" / "core"
    cmd = [
        "uv",
        "--directory",
        str(core_dir),
        "run",
        "python",
        "-m",
        "astock_control",
        "--host",
        host,
        "--port",
        str(port),
    ]
    print(f"启动 core  {host}:{port}", file=sys.stderr)
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
