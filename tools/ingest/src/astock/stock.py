from __future__ import annotations

import logging
import time
from datetime import date

from astock import eastmoney
from astock.config import REQUEST_SLEEP_SECONDS
from astock.ingest import _call
from astock.quotes import sync_quotes
from astock_core.db import MarketDB
from astock_core.paths import DEFAULT_ADJUST, DEFAULT_POOL_ID

logger = logging.getLogger(__name__)


def _as_yyyymmdd(value: str | None) -> str:
    if not value:
        return date.today().strftime("%Y%m%d")
    return value.replace("-", "")[:8]


def fetch_st_codes() -> set[str]:
    import akshare as ak

    frame = _call(ak.stock_zh_a_st_em)
    if frame is None or frame.empty:
        return set()
    col = "代码" if "代码" in frame.columns else frame.columns[1]
    return {str(code).zfill(6) for code in frame[col] if str(code).strip()}


def fetch_suspend_map(as_of: str) -> dict[str, str]:
    import akshare as ak

    try:
        frame = _call(ak.stock_tfp_em, date=_as_yyyymmdd(as_of))
    except Exception as exc:
        logger.warning("停复牌拉取失败：%s", exc)
        return {}
    if frame is None or frame.empty:
        return {}
    out: dict[str, str] = {}
    for row in frame.to_dict(orient="records"):
        raw_code = row.get("代码") or row.get("code")
        if not raw_code:
            continue
        code = str(raw_code).zfill(6)
        reason = row.get("停牌原因") or row.get("reason") or ""
        until = row.get("预计复牌时间") or row.get("unpause_date") or ""
        note = str(reason).strip()
        if until:
            note = f"{note} 预计复牌 {until}".strip()
        out[code] = note
    return out


def sync_stock_info(
    db: MarketDB,
    codes: list[str],
    *,
    sleep: float = REQUEST_SLEEP_SECONDS,
) -> dict[str, int]:
    last_cal = db.last_calendar_date()
    try:
        st_codes = fetch_st_codes()
    except Exception as exc:
        logger.warning("ST 列表拉取失败：%s", exc)
        st_codes = set()
    suspend_map = fetch_suspend_map(last_cal)
    ok = 0
    error = 0
    for i, code in enumerate(codes, start=1):
        try:
            profile = _call(eastmoney.stock_profile, code)
            db.upsert_stock_profile(
                code,
                name=profile["name"],
                industry=profile.get("industry"),
                list_date=profile.get("list_date"),
                total_shares=profile.get("total_shares"),
                float_shares=profile.get("float_shares"),
                total_mv=profile.get("total_mv"),
                float_mv=profile.get("float_mv"),
                latest_price=profile.get("latest_price"),
                is_st=1 if code in st_codes else 0,
                is_suspended=1 if code in suspend_map else 0,
                suspend_info=suspend_map.get(code),
            )
            ok += 1
            if i == 1 or i % 20 == 0 or i == len(codes):
                logger.info("个股资料 %s/%s  %s %s", i, len(codes), code, profile.get("name"))
        except Exception as exc:
            error += 1
            logger.warning("个股资料失败 %s: %s", code, exc)
        time.sleep(sleep)
    return {"info_ok": ok, "info_error": error, "info_total": len(codes)}


def stock_snapshot(
    db: MarketDB,
    code: str,
    *,
    pool_id: str = DEFAULT_POOL_ID,
    adjust: str = DEFAULT_ADJUST,
) -> dict:
    profile = db.get_stock(code)
    membership = db.pool_membership(pool_id, code)
    summary = db.bar_summary(code, adjust=adjust)
    latest = db.latest_bar(code, adjust=adjust)
    plan_kind = None
    last_cal = summary.get("calendar_as_of")
    last = summary.get("last")
    if summary["bars"] == 0:
        plan_kind = "full"
    elif last_cal and last and last < last_cal:
        plan_kind = "fill"
    else:
        plan_kind = "current"
    return {
        "code": code,
        "pool": pool_id,
        "membership": membership,
        "profile": profile,
        "quotes_summary": summary,
        "latest_bar": latest,
        "quotes_plan": plan_kind,
    }


def format_stock_snapshot(data: dict) -> str:
    code = data["code"]
    profile = data.get("profile") or {}
    name = profile.get("name") or code
    member = data.get("membership")
    summary = data.get("quotes_summary") or {}
    latest = data.get("latest_bar")
    lines = [
        f"=== {code}  {name} ===",
        f"池 {data['pool']}: "
        + (
            f"{member['status']}  来源={member['source']}  首次加入={member['first_added_at']}"
            if member
            else "未加入该池"
        ),
        "",
        "【资料】",
        f"行业  {profile.get('industry') or '-'}",
        f"上市  {profile.get('list_date') or '-'}",
        f"总股本 { _fmt_num(profile.get('total_shares')) }    流通股 { _fmt_num(profile.get('float_shares')) }",
        f"总市值 { _fmt_num(profile.get('total_mv')) }    流通市值 { _fmt_num(profile.get('float_mv')) }",
        f"ST    {'是' if profile.get('is_st') else '否'}    停牌 {'是 ' + (profile.get('suspend_info') or '') if profile.get('is_suspended') else '否'}",
        f"资料更新  {profile.get('updated_at') or '-'}",
    ]
    if not profile.get("industry"):
        lines.append(f"（资料未同步，可执行: python -m astock stock sync {code} --info）")
    plan_label = {"full": "需拉全历史", "fill": "需补缺口", "current": "已齐"}.get(
        data.get("quotes_plan"), "-"
    )
    lines.extend(
        [
            "",
            f"【行情摘要】 复权={summary.get('adjust')}",
            f"区间  {summary.get('first') or '-'} ~ {summary.get('last') or '-'}  "
            f"根数 {summary.get('bars', 0)}  缺交易日 {summary.get('missing_sessions', 0)}  "
            f"日历截止 {summary.get('calendar_as_of') or '-'}",
            f"补齐状态  {plan_label}",
            "",
            "【最新交易日】",
        ]
    )
    if not latest:
        lines.append("库中无日线，请执行: python -m astock stock sync {code} --quotes".format(code=code))
    else:
        lines.append(
            f"{latest.get('trade_date')}  "
            f"开 {latest.get('open')}  高 {latest.get('high')}  "
            f"低 {latest.get('low')}  收 {latest.get('close')}  "
            f"涨跌幅 {latest.get('pct_chg')}%  "
            f"额 { _fmt_num(latest.get('amount')) }  "
            f"换手 {latest.get('turnover')}%"
        )
    return "\n".join(lines)


def _fmt_num(value: object) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 1e8:
        return f"{number / 1e8:.2f}亿"
    if abs(number) >= 1e4:
        return f"{number / 1e4:.2f}万"
    return f"{number:.2f}"


def resolve_sync_codes(db: MarketDB, raw: str | None, pool_id: str) -> list[str]:
    if raw:
        return [item.strip().zfill(6) for item in raw.split(",") if item.strip()]
    return db.active_pool_codes(pool_id)


def sync_stock(
    db: MarketDB,
    codes: list[str],
    *,
    pool_id: str = DEFAULT_POOL_ID,
    do_info: bool = True,
    do_quotes: bool = True,
    sleep: float = REQUEST_SLEEP_SECONDS,
) -> dict:
    result: dict = {"codes": len(codes), "pool": pool_id}
    if do_info:
        result.update(sync_stock_info(db, codes, sleep=sleep))
    if do_quotes:
        result.update(
            sync_quotes(
                db,
                pool_id=pool_id,
                codes=codes,
                sleep=sleep,
            )
        )
    return result
