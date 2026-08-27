from __future__ import annotations

from pathlib import Path

from astock_core.paths import QLIB_DIR


def init_qlib(provider_uri: Path | None = None):
    """指向 data/qlib，按 A 股规则初始化。"""
    import qlib
    from qlib.constant import REG_CN

    uri = Path(provider_uri or QLIB_DIR)
    calendar = uri / "calendars" / "day.txt"
    if not calendar.is_file():
        raise FileNotFoundError(f"未找到 Qlib 数据，请先执行 dump：{uri}")
    qlib.init(
        provider_uri=str(uri),
        region=REG_CN,
        expression_cache=None,
        dataset_cache=None,
    )
    return uri


def smoke(provider_uri: Path | None = None) -> dict:
    from qlib.data import D

    uri = init_qlib(provider_uri)
    calendar = D.calendar(freq="day")
    all_list = D.list_instruments(D.instruments("all"), as_list=True)
    pool = []
    csi_path = uri / "instruments" / "csi300.txt"
    if csi_path.is_file() and csi_path.stat().st_size > 0:
        pool = D.list_instruments(D.instruments("csi300"), as_list=True)
    sample = "SZ000001" if "SZ000001" in all_list else all_list[0]
    start = calendar[0]
    end = calendar[min(20, len(calendar) - 1)]
    frame = D.features(
        [sample],
        ["$open", "$close", "$high", "$low", "$volume", "$vwap", "$factor"],
        start_time=start,
        end_time=end,
        freq="day",
    )
    close = frame["$close"].dropna()
    return {
        "qlib_dir": str(uri),
        "calendar_days": int(len(calendar)),
        "calendar_first": str(pd_ts(calendar[0])),
        "calendar_last": str(pd_ts(calendar[-1])),
        "instruments_all": int(len(all_list)),
        "instruments_csi300": int(len(pool)),
        "sample": sample,
        "sample_rows": int(len(frame)),
        "sample_close_first": float(close.iloc[0]) if not close.empty else None,
        "sample_close_last": float(close.iloc[-1]) if not close.empty else None,
    }


def feature_frame(
    codes: list[str],
    fields: list[str],
    *,
    start: str | None = None,
    end: str | None = None,
    provider_uri: Path | None = None,
):
    from qlib.data import D

    init_qlib(provider_uri)
    symbols = [code if code.isupper() and len(code) > 6 else _as_symbol(code) for code in codes]
    return D.features(symbols, fields, start_time=start, end_time=end, freq="day")


def _as_symbol(code: str) -> str:
    from astock_qlib.symbols import to_qlib_symbol

    return to_qlib_symbol(code)


def pd_ts(value: object) -> str:
    return str(value)[:10]


def qlib_status(provider_uri: Path | None = None) -> dict:
    uri = Path(provider_uri or QLIB_DIR)
    calendar = uri / "calendars" / "day.txt"
    instruments = uri / "instruments" / "all.txt"
    features = uri / "features"
    payload = {
        "qlib_dir": str(uri),
        "ready": calendar.is_file() and instruments.is_file(),
    }
    if calendar.is_file():
        lines = [line.strip() for line in calendar.read_text(encoding="utf-8").splitlines() if line.strip()]
        payload["calendar_days"] = len(lines)
        payload["calendar_first"] = lines[0] if lines else None
        payload["calendar_last"] = lines[-1] if lines else None
    if instruments.is_file():
        payload["instruments"] = sum(1 for line in instruments.read_text(encoding="utf-8").splitlines() if line.strip())
    if features.is_dir():
        payload["feature_dirs"] = sum(1 for path in features.iterdir() if path.is_dir())
    return payload
