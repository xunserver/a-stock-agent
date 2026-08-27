from __future__ import annotations

import logging
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from astock_core.db import MarketDB
from astock_core.paths import DEFAULT_ADJUST, DEFAULT_POOL_ID, QLIB_DIR
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

    combined = pd.concat([stocks, indexes], ignore_index=True) if not indexes.empty else stocks
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

    pool_codes = set(db.active_pool_codes(pool_id))
    pool_symbols = {to_qlib_symbol(code) for code in pool_codes}
    pool_inst = instruments[instruments["symbol"].isin(pool_symbols)]
    _write_instruments(tmp / "instruments" / f"{pool_id}.txt", pool_inst)
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
        "instruments": int(len(instruments)),
        "pool_instruments": int(len(pool_inst)),
        "csi300_instruments": int(len(csi_inst)),
        "features": n_written,
        "rows": int(len(combined)),
    }


def _load_stock_bars(db: MarketDB, *, adjust: str) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """
        SELECT code, trade_date AS date, open, close, high, low, volume, amount
        FROM bars_daily
        WHERE adjust = ?
        ORDER BY code, trade_date
        """,
        db.conn,
        params=(adjust,),
        parse_dates=["date"],
    )
    if frame.empty:
        return frame
    frame["symbol"] = frame["code"].map(to_qlib_symbol)
    return _with_derived(frame)


def _load_index_bars(db: MarketDB) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """
        SELECT code, trade_date AS date, open, close, high, low, volume, amount
        FROM index_daily
        ORDER BY code, trade_date
        """,
        db.conn,
        parse_dates=["date"],
    )
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
    rows = db.conn.execute(
        """
        SELECT trade_date FROM trade_calendar
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
        """,
        (start, end),
    ).fetchall()
    calendar = {pd.Timestamp(row[0]) for row in rows}
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
    np.savetxt(path, [ts.strftime("%Y-%m-%d") for ts in calendar], fmt="%s", encoding="utf-8")


def _write_instruments(path: Path, frame: pd.DataFrame) -> None:
    if frame.empty:
        path.write_text("", encoding="utf-8")
        return
    lines = [f"{row.symbol}\t{row.start}\t{row.end}" for row in frame.itertuples(index=False)]
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
        values = pd.to_numeric(aligned[field], errors="coerce").to_numpy(dtype=np.float64)
        payload = np.hstack([date_index, values]).astype("<f")
        payload.tofile(str(out_dir / f"{field}.day.bin"))


def _align_calendar(frame: pd.DataFrame, calendar: list[pd.Timestamp]) -> pd.DataFrame:
    indexed = frame.set_index("date")
    indexed.index = pd.DatetimeIndex(indexed.index)
    cal = pd.DatetimeIndex(calendar)
    window = cal[(cal >= indexed.index.min()) & (cal <= indexed.index.max())]
    return indexed.reindex(window)
