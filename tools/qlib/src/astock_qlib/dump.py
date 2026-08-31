from __future__ import annotations

import logging
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from astock_core.db import MarketDB
from astock_core.paths import DEFAULT_ADJUST, DEFAULT_POOL_ID, QLIB_DIR, pool_qlib_dir

from astock_qlib.symbols import code_to_fname, to_qlib_symbol

logger = logging.getLogger(__name__)

FIELDS = ("open", "close", "high", "low", "volume", "amount", "factor", "vwap")


def dump_qlib(
    db: MarketDB,
    *,
    dest: Path | None = None,
    adjust: str = DEFAULT_ADJUST,
    pool_id: str = DEFAULT_POOL_ID,
) -> dict:
    """把 market.db 日线写成 Qlib 的 calendars / instruments / features/*.bin。"""
    dest = Path(dest or QLIB_DIR)
    stocks = _load_stock_bars(db, adjust=adjust)
    indexes = _load_index_bars(db)
    if stocks.empty and indexes.empty:
        raise RuntimeError(f"库里没有可导出的日线: {db.path}")

    combined = (
        pd.concat([stocks, indexes], ignore_index=True) if not indexes.empty else stocks
    )
    calendar = _build_calendar(db, combined["date"])
    instruments = _instrument_table(combined)

    tmp = dest.parent / f".{dest.name}.building"
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "calendars").mkdir(parents=True)
    (tmp / "instruments").mkdir()
    (tmp / "features").mkdir()

    _write_calendar(tmp / "calendars" / "day.txt", calendar)
    _write_instruments(tmp / "instruments" / "all.txt", instruments)

    pool_counts: dict[str, int] = {}
    pool_inst = instruments.iloc[0:0]
    for pool in db.list_pools():
        current_pool_id = str(pool["id"])
        pool_codes = set(db.active_pool_codes(current_pool_id))
        pool_symbols = {to_qlib_symbol(code) for code in pool_codes}
        current_pool_inst = instruments[instruments["symbol"].isin(pool_symbols)]
        _write_instruments(
            tmp / "instruments" / f"{current_pool_id}.txt",
            current_pool_inst,
        )
        pool_counts[current_pool_id] = len(current_pool_inst)
        if current_pool_id == pool_id:
            pool_inst = current_pool_inst
    # 研究用 csi300 跟沪深300成分，不跟当前 default 池（可能被裁过）
    hs300_codes = set(db.universe_codes("hs300"))
    if hs300_codes:
        csi_symbols = {to_qlib_symbol(code) for code in hs300_codes}
        csi_inst = instruments[instruments["symbol"].isin(csi_symbols)]
    else:
        csi_inst = pool_inst
    _write_instruments(tmp / "instruments" / "csi300.txt", csi_inst)

    n_written = 0
    grouped = list(combined.groupby("symbol", sort=True))
    total = len(grouped)
    for i, (symbol, frame) in enumerate(grouped, start=1):
        _dump_symbol(tmp / "features", symbol, frame, calendar)
        n_written += 1
        if i % 50 == 0 or i == total:
            logger.info("写入特征 %s/%s  %s", i, total, symbol)

    if dest.exists():
        shutil.rmtree(dest)
    tmp.rename(dest)

    return {
        "qlib_dir": str(dest),
        "adjust": adjust,
        "pool": pool_id,
        "calendar_days": len(calendar),
        "calendar_first": calendar[0].strftime("%Y-%m-%d"),
        "calendar_last": calendar[-1].strftime("%Y-%m-%d"),
        "instruments": len(instruments),
        "pool_instruments": len(pool_inst),
        "pool_instruments_all": pool_counts,
        "csi300_instruments": len(csi_inst),
        "features": n_written,
        "rows": len(combined),
    }


def _benchmark_index_code(benchmark: str) -> str:
    digits = "".join(ch for ch in str(benchmark).strip().upper() if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else digits


def pool_data_ready(pool_id: str, *, dest: Path | None = None) -> bool:
    root = Path(dest or pool_qlib_dir(pool_id))
    calendar_path = root / "calendars" / "day.txt"
    instrument_path = root / "instruments" / f"{pool_id}.txt"
    return calendar_path.is_file() and instrument_path.is_file() and bool(
        instrument_path.read_text(encoding="utf-8").strip()
    )


def prepare_pool_qlib(
    db: MarketDB,
    *,
    pool_id: str,
    benchmark: str = "SH000300",
    dest: Path | None = None,
    adjust: str = DEFAULT_ADJUST,
) -> dict:
    """Export one pool's universe (+ benchmark index) into a dedicated Qlib directory."""
    pool_codes = set(db.active_pool_codes(pool_id))
    if not pool_codes:
        raise RuntimeError(f"股票池没有活跃成员: {pool_id}")

    dest = Path(dest or pool_qlib_dir(pool_id))
    benchmark_code = _benchmark_index_code(benchmark)

    stocks = _load_stock_bars(db, adjust=adjust)
    stocks = stocks[stocks["code"].isin(pool_codes)]
    if stocks.empty:
        raise RuntimeError(
            f"池 {pool_id} 成员在 market.db 中没有 {adjust or '不复权'} 日线"
        )

    indexes = _load_index_bars(db)
    if benchmark_code:
        benchmark_rows = indexes[indexes["code"] == benchmark_code]
    else:
        benchmark_rows = indexes.iloc[0:0]

    combined = (
        pd.concat([stocks, benchmark_rows], ignore_index=True)
        if not benchmark_rows.empty
        else stocks
    )
    calendar = _build_calendar(db, combined["date"])
    instruments = _instrument_table(combined)
    pool_symbols = {to_qlib_symbol(code) for code in pool_codes}
    pool_inst = instruments[instruments["symbol"].isin(pool_symbols)]

    tmp = dest.parent / f".{dest.name}.building"
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "calendars").mkdir(parents=True)
    (tmp / "instruments").mkdir()
    (tmp / "features").mkdir()

    _write_calendar(tmp / "calendars" / "day.txt", calendar)
    _write_instruments(tmp / "instruments" / f"{pool_id}.txt", pool_inst)

    n_written = 0
    grouped = list(combined.groupby("symbol", sort=True))
    total = len(grouped)
    for i, (symbol, frame) in enumerate(grouped, start=1):
        _dump_symbol(tmp / "features", symbol, frame, calendar)
        n_written += 1
        if i % 50 == 0 or i == total:
            logger.info("写入特征 %s/%s  %s", i, total, symbol)

    if dest.exists():
        shutil.rmtree(dest)
    tmp.rename(dest)

    return {
        "ok": True,
        "qlib_dir": str(dest),
        "adjust": adjust,
        "pool": pool_id,
        "benchmark": benchmark,
        "pool_members": len(pool_codes),
        "symbols": int(combined["symbol"].nunique()),
        "calendar_days": len(calendar),
        "calendar_first": calendar[0].strftime("%Y-%m-%d"),
        "calendar_last": calendar[-1].strftime("%Y-%m-%d"),
        "features": n_written,
        "rows": len(combined),
    }


def _load_stock_bars(db: MarketDB, *, adjust: str) -> pd.DataFrame:
    columns = ["code", "date", "open", "close", "high", "low", "volume", "amount"]
    frame = pd.DataFrame.from_records(
        db.list_bar_export_rows(adjust=adjust), columns=columns
    )
    frame["date"] = pd.to_datetime(frame["date"])
    if frame.empty:
        return frame
    frame["symbol"] = frame["code"].map(to_qlib_symbol)
    return _with_derived(frame)


def _load_index_bars(db: MarketDB) -> pd.DataFrame:
    columns = ["code", "date", "open", "close", "high", "low", "volume", "amount"]
    frame = pd.DataFrame.from_records(
        db.list_index_bar_export_rows(), columns=columns
    )
    frame["date"] = pd.to_datetime(frame["date"])
    if frame.empty:
        return frame
    frame["symbol"] = frame["code"].map(to_qlib_symbol)
    return _with_derived(frame)


def _with_derived(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["factor"] = 1.0
    out["vwap"] = (out["high"] + out["low"] + out["close"]) / 3.0
    return out


def _build_calendar(db: MarketDB, dates: pd.Series) -> list[pd.Timestamp]:
    start = pd.Timestamp(dates.min()).strftime("%Y-%m-%d")
    end = pd.Timestamp(dates.max()).strftime("%Y-%m-%d")
    calendar = {pd.Timestamp(value) for value in db.list_calendar_dates(start, end)}
    calendar.update(pd.Timestamp(value) for value in dates.dropna().unique())
    return sorted(calendar)


def _instrument_table(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby("symbol", sort=True)["date"].agg(["min", "max"])
    return pd.DataFrame(
        {
            "symbol": grouped.index,
            "start": grouped["min"].dt.strftime("%Y-%m-%d").to_numpy(),
            "end": grouped["max"].dt.strftime("%Y-%m-%d").to_numpy(),
        }
    )


def _write_calendar(path: Path, calendar: list[pd.Timestamp]) -> None:
    np.savetxt(
        path, [ts.strftime("%Y-%m-%d") for ts in calendar], fmt="%s", encoding="utf-8"
    )


def _write_instruments(path: Path, frame: pd.DataFrame) -> None:
    if frame.empty:
        path.write_text("", encoding="utf-8")
        return
    lines = [
        f"{row.symbol}\t{row.start}\t{row.end}" for row in frame.itertuples(index=False)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _dump_symbol(
    features_dir: Path,
    symbol: str,
    frame: pd.DataFrame,
    calendar: list[pd.Timestamp],
) -> None:
    frame = frame.drop_duplicates("date").sort_values("date")
    aligned = _align_calendar(frame, calendar)
    if aligned.empty:
        logger.warning("%s 对齐日历后为空，跳过", symbol)
        return
    date_index = int(pd.DatetimeIndex(calendar).get_loc(aligned.index.min()))
    out_dir = features_dir / code_to_fname(symbol).lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    for field in FIELDS:
        values = pd.to_numeric(aligned[field], errors="coerce").to_numpy(
            dtype=np.float64
        )
        payload = np.hstack([date_index, values]).astype("<f")
        payload.tofile(str(out_dir / f"{field}.day.bin"))


def _align_calendar(frame: pd.DataFrame, calendar: list[pd.Timestamp]) -> pd.DataFrame:
    indexed = frame.set_index("date")
    indexed.index = pd.DatetimeIndex(indexed.index)
    cal = pd.DatetimeIndex(calendar)
    window = cal[(cal >= indexed.index.min()) & (cal <= indexed.index.max())]
    return indexed.reindex(window)
