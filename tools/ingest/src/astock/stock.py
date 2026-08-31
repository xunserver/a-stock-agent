from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from astock.config import default_adjust, request_sleep_seconds
from astock.financial import sync_financial_statements
from astock.providers.defaults import (
    default_fundamental_source,
    default_stock_info_source,
)
from astock.providers.protocols import (
    FundamentalSource,
    InstrumentProfileSource,
    QuoteSnapshotSource,
    StatementSource,
    ValuationSource,
)
from astock.quotes import sync_quotes
from astock_core.db import MarketDB
from astock_core.market_data import (
    FundamentalQuery,
    InstrumentId,
    InstrumentQuery,
    SnapshotQuery,
    ValuationQuery,
    fill_quote_limits,
    fill_share_counts,
    from_legacy_symbol,
    to_legacy_symbol,
)
from astock_core.paths import DEFAULT_POOL_ID

logger = logging.getLogger(__name__)
_SHANGHAI = ZoneInfo("Asia/Shanghai")


def sync_stock_info(
    db: MarketDB,
    codes: list[str],
    *,
    sleep: float | None = None,
    with_statements: bool = False,
    profile_source: InstrumentProfileSource | None = None,
    snapshot_source: QuoteSnapshotSource | None = None,
    valuation_source: ValuationSource | None = None,
    fundamental_source: FundamentalSource | None = None,
    statement_source: StatementSource | None = None,
) -> dict[str, int]:
    resolved_sleep = request_sleep_seconds() if sleep is None else sleep
    if profile_source is None and snapshot_source is None and valuation_source is None:
        adapter = default_stock_info_source(pause=resolved_sleep)
        profile_source = snapshot_source = valuation_source = adapter
    else:
        adapter = default_stock_info_source(pause=resolved_sleep)
        profile_source = profile_source or adapter
        snapshot_source = snapshot_source or adapter
        valuation_source = valuation_source or adapter
    if fundamental_source is None:
        fundamental_source = default_fundamental_source()

    wanted = [code.zfill(6) for code in codes if str(code).strip()]
    if not wanted:
        return {
            "info_ok": 0,
            "info_error": 0,
            "info_total": 0,
            "profile_ok": 0,
            "profile_error": 0,
            "snapshot_ok": 0,
            "snapshot_error": 0,
            "valuation_ok": 0,
            "valuation_error": 0,
        }
    instrument_ids = tuple(from_legacy_symbol(code) for code in wanted)

    fundamentals = _fetch_capability(
        "财务摘要",
        lambda: fundamental_source.fetch_fundamentals(
            FundamentalQuery(instruments=instrument_ids)
        ),
    )
    if fundamentals is not None and fundamentals.items:
        try:
            db.upsert_fundamental_periods(fundamentals.items)
        except Exception as exc:
            logger.warning("财务摘要入库失败：%s", exc)

    profiles = _fetch_capability(
        "资料",
        lambda: profile_source.fetch_profiles(InstrumentQuery(instruments=instrument_ids)),
    )
    snapshots = _fetch_capability(
        "行情快照",
        lambda: snapshot_source.fetch_snapshots(SnapshotQuery(instruments=instrument_ids)),
    )
    valuations = _fetch_capability(
        "估值",
        lambda: valuation_source.fetch_valuations(ValuationQuery(instruments=instrument_ids)),
    )
    profiles_by_id = {item.instrument_id: item for item in (profiles.items if profiles else ())}
    snapshots_by_id = {item.instrument_id: item for item in (snapshots.items if snapshots else ())}
    valuations_by_id = {item.instrument_id: item for item in (valuations.items if valuations else ())}

    ok = 0
    error = 0
    profile_ok = snapshot_ok = valuation_ok = 0
    profile_error = 0 if profiles is not None else 1
    snapshot_error = 0 if snapshots is not None else 1
    valuation_error = 0 if valuations is not None else 1

    for i, code in enumerate(wanted, start=1):
        instrument_id = from_legacy_symbol(code)
        try:
            wrote = _persist_capabilities(
                db,
                instrument_id,
                profile=profiles_by_id.get(instrument_id),
                snapshot=snapshots_by_id.get(instrument_id),
                valuation=valuations_by_id.get(instrument_id),
            )
            if wrote["profile"]:
                profile_ok += 1
            if wrote["snapshot"]:
                snapshot_ok += 1
            if wrote["valuation"]:
                valuation_ok += 1
            if not any(wrote.values()):
                raise RuntimeError("未返回可用资料")
            ok += 1
            existing = db.get_stock(code) or {}
            if i == 1 or i % 20 == 0 or i == len(wanted):
                logger.info(
                    "个股资料 %s/%s  %s %s",
                    i,
                    len(wanted),
                    code,
                    existing.get("name") or code,
                )
        except Exception as exc:
            error += 1
            logger.warning("个股资料失败 %s: %s", code, exc)

    result: dict[str, int] = {
        "info_ok": ok,
        "info_error": error,
        "info_total": len(wanted),
        "profile_ok": profile_ok,
        "profile_error": profile_error,
        "snapshot_ok": snapshot_ok,
        "snapshot_error": snapshot_error,
        "valuation_ok": valuation_ok,
        "valuation_error": valuation_error,
    }
    if with_statements:
        try:
            result.update(sync_financial_statements(db, wanted, statement_source=statement_source))
        except Exception as exc:
            logger.warning("报表明细批量入库失败：%s", exc)
    return result


def _fetch_capability(label: str, fetch):
    try:
        return fetch()
    except Exception as exc:
        logger.warning("%s拉取失败：%s", label, exc)
        return None


def _persist_capabilities(
    db: MarketDB,
    instrument_id: InstrumentId,
    *,
    profile,
    snapshot,
    valuation,
) -> dict[str, bool]:
    wrote = {"profile": False, "snapshot": False, "valuation": False}
    is_st = bool(profile.is_st) if profile is not None else False
    if snapshot is not None:
        snapshot, limit_warnings = fill_quote_limits(snapshot, is_st=is_st)
        for warning in limit_warnings:
            logger.info("%s %s", to_legacy_symbol(instrument_id), warning)
    if valuation is not None and snapshot is not None:
        valuation, share_warnings = fill_share_counts(
            valuation,
            last_price=snapshot.last_price,
            price_as_of=snapshot.observed_at.astimezone(_SHANGHAI).date(),
        )
        for warning in share_warnings:
            logger.info("%s %s", to_legacy_symbol(instrument_id), warning)
    if profile is not None:
        db.upsert_instrument_profiles((profile,))
        wrote["profile"] = True
    if snapshot is not None:
        db.upsert_quote_snapshots((snapshot,))
        wrote["snapshot"] = True
    if valuation is not None:
        db.upsert_valuation_snapshots((valuation,))
        wrote["valuation"] = True
    return wrote


def stock_snapshot(
    db: MarketDB,
    code: str,
    *,
    pool_id: str = DEFAULT_POOL_ID,
    adjust: str | None = None,
) -> dict:
    resolved_adjust = default_adjust() if adjust is None else adjust
    profile = db.get_stock(code)
    membership = db.pool_membership(pool_id, code)
    summary = db.bar_summary(code, adjust=resolved_adjust)
    latest = db.latest_bar(code, adjust=resolved_adjust)
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
        f"行业  {profile.get('industry') or '-'}    地域 {profile.get('region') or '-'}",
        f"上市  {profile.get('list_date') or '-'}",
        f"总股本 { _fmt_num(profile.get('total_shares')) }    流通股 { _fmt_num(profile.get('float_shares')) }",
        f"总市值 { _fmt_num(profile.get('total_mv')) }    流通市值 { _fmt_num(profile.get('float_mv')) }",
        f"PE动 { _fmt_num(profile.get('pe_dyn')) }    PE静 { _fmt_num(profile.get('pe_static')) }    PB { _fmt_num(profile.get('pb')) }",
        f"昨收 { _fmt_num(profile.get('pre_close')) }    均价 { _fmt_num(profile.get('avg_price')) }    量比 { _fmt_num(profile.get('volume_ratio')) }",
        f"涨停 { _fmt_num(profile.get('high_limit')) }    跌停 { _fmt_num(profile.get('low_limit')) }",
        f"外盘 { _fmt_num(profile.get('outer_vol')) }    内盘 { _fmt_num(profile.get('inner_vol')) }",
        f"EPS { _fmt_num(profile.get('eps')) }    BPS { _fmt_num(profile.get('bps')) }    ROE { _fmt_pct(profile.get('roe')) }",
        f"营收 { _fmt_num(profile.get('revenue')) }    营收同比 { _fmt_pct(profile.get('revenue_yoy')) }",
        f"净利同比 { _fmt_pct(profile.get('net_profit_yoy')) }    毛利率 { _fmt_pct(profile.get('gross_margin')) }",
        f"净利率 { _fmt_pct(profile.get('net_margin')) }    资产负债率 { _fmt_pct(profile.get('debt_ratio')) }",
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


def _fmt_pct(value: object) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f}%"


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
    sleep: float | None = None,
    with_statements: bool = False,
) -> dict:
    resolved_sleep = request_sleep_seconds() if sleep is None else sleep
    result: dict = {"codes": len(codes), "pool": pool_id}
    if do_info:
        result.update(
            sync_stock_info(
                db,
                codes,
                sleep=resolved_sleep,
                with_statements=with_statements,
            )
        )
    if do_quotes:
        result.update(
            sync_quotes(
                db,
                pool_id=pool_id,
                codes=codes,
                sleep=resolved_sleep,
            )
        )
    return result