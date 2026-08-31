"""AKShare Market Event Adapter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from astock_core.market_data import (
    BlockTradeEvent,
    Dataset,
    EventKind,
    EventQuery,
    HolderChangeEvent,
    InstrumentId,
    InvalidSourcePayload,
    MarketEvent,
    NoticeEvent,
    ResearchReportEvent,
    UnsupportedQuery,
    to_legacy_symbol,
    validate_event_dataset,
)

from astock.providers._support import call_with_retries, translate_transport_error
from astock.providers.akshare._ids import stable_record_id
from astock.providers.akshare._tables import (
    as_optional_float,
    lookup_column,
    records_from_source_table,
)
from astock.providers.akshare._text import clean_text
from astock.providers.akshare._time import parse_publication_time
from astock.providers.eastmoney.snapshots import CN_TIMEZONE

SOURCE = "akshare"
_SHANGHAI = ZoneInfo(CN_TIMEZONE)
NOTICES_LOOKBACK_DAYS = 365
BLOCK_TRADES_LOOKBACK_DAYS = 90

NoticeTable = Callable[..., object]
ResearchTable = Callable[..., object]
BlockTradeTable = Callable[..., object]
HolderTable = Callable[..., object]
Sleep = Callable[[float], None]
Clock = Callable[[], datetime]
Today = Callable[[], date]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def _default_today() -> date:
    return datetime.now(_SHANGHAI).date()


def _default_notices(security: str, begin_date: str, end_date: str) -> object:
    import akshare as ak

    return ak.stock_individual_notice_report(
        security=security,
        symbol="全部",
        begin_date=begin_date,
        end_date=end_date,
    )


def _default_research(symbol: str) -> object:
    import akshare as ak

    return ak.stock_research_report_em(symbol=symbol)


def _default_block_trades(start_date: str, end_date: str) -> object:
    import akshare as ak

    return ak.stock_dzjy_mrmx(symbol="A股", start_date=start_date, end_date=end_date)


def _default_holder_sse(symbol: str) -> object:
    import akshare as ak

    return ak.stock_share_hold_change_sse(symbol=symbol)


def _default_holder_bse(symbol: str) -> object:
    import akshare as ak

    return ak.stock_share_hold_change_bse(symbol=symbol)


def _default_holder_szse(symbol: str) -> object:
    import akshare as ak

    return ak.stock_share_hold_change_szse(symbol=symbol)


def _ymd(value: date) -> str:
    return value.strftime("%Y%m%d")


def _holder_exchange(code: str) -> str:
    if code.startswith(("6", "9", "5")):
        return "sse"
    if code.startswith(("4", "8")):
        return "bse"
    return "szse"


class AkshareEventAdapter:
    """Translate AKShare notice/research/block/holder payloads into typed events."""

    def __init__(
        self,
        *,
        notices: NoticeTable | None = None,
        research: ResearchTable | None = None,
        block_trades: BlockTradeTable | None = None,
        holder_sse: HolderTable | None = None,
        holder_bse: HolderTable | None = None,
        holder_szse: HolderTable | None = None,
        retries: int = 1,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
        today: Today | None = None,
    ) -> None:
        self._notices = notices or _default_notices
        self._research = research or _default_research
        self._block_trades = block_trades or _default_block_trades
        self._holder_sse = holder_sse or _default_holder_sse
        self._holder_bse = holder_bse or _default_holder_bse
        self._holder_szse = holder_szse or _default_holder_szse
        self._retries = retries
        self._sleep = sleep or _default_sleep
        self._clock = clock or _default_clock
        self._today = today or _default_today

    def fetch_events(self, query: EventQuery) -> Dataset[MarketEvent]:
        if len(query.instruments) != 1:
            raise UnsupportedQuery("AKShare events support exactly one InstrumentId per query")
        if not query.kinds:
            raise UnsupportedQuery("EventQuery.kinds must specify at least one event kind")
        instrument_id = query.instruments[0]
        symbol = to_legacy_symbol(instrument_id)
        warnings: list[str] = []
        items: list[MarketEvent] = []
        for kind in query.kinds:
            if kind is EventKind.NOTICE:
                items.extend(self._fetch_notices(instrument_id, symbol, warnings))
            elif kind is EventKind.RESEARCH_REPORT:
                items.extend(self._fetch_research(instrument_id, symbol, warnings))
            elif kind is EventKind.BLOCK_TRADE:
                items.extend(self._fetch_block_trades(instrument_id, symbol, warnings))
            elif kind is EventKind.HOLDER_CHANGE:
                items.extend(self._fetch_holder_changes(instrument_id, symbol, warnings))
            else:
                raise UnsupportedQuery(f"unsupported event kind: {kind.value}")
        if query.start is not None:
            items = [item for item in items if item.published_at >= query.start]
        if query.end is not None:
            items = [item for item in items if item.published_at <= query.end]
        items.sort(key=lambda item: (item.published_at, item.kind.value, item.id))
        if query.limit is not None:
            items = items[-query.limit :] if query.limit else []
        dataset = Dataset(
            items=tuple(items),
            source=SOURCE,
            fetched_at=self._clock(),
            complete=True,
            warnings=tuple(warnings),
        )
        return validate_event_dataset(dataset, query)

    def _fetch_notices(
        self,
        instrument_id: InstrumentId,
        symbol: str,
        warnings: list[str],
    ) -> list[NoticeEvent]:
        end = self._today()
        begin = end - timedelta(days=NOTICES_LOOKBACK_DAYS)
        records = records_from_source_table(
            self._call(
                lambda: self._notices(
                    security=symbol,
                    begin_date=_ymd(begin),
                    end_date=_ymd(end),
                )
            )
        )
        items: list[NoticeEvent] = []
        for index, row in enumerate(records):
            title = clean_text(lookup_column(row, ("公告标题",)))
            if not title:
                raise InvalidSourcePayload(
                    f"malformed NoticeEvent at source row {index}: missing title"
                )
            notice_type = clean_text(lookup_column(row, ("公告类型",))) or None
            published_at = parse_publication_time(
                lookup_column(row, ("公告日期",)),
                field=f"公告日期[{index}]",
                warnings=warnings,
                context=f"{symbol} notice {title!r}",
            )
            url = clean_text(lookup_column(row, ("网址",))) or None
            item_id = stable_record_id(
                source=SOURCE,
                instrument_id=instrument_id,
                published_at=published_at,
                title=title,
                url=url,
            )
            items.append(
                NoticeEvent(
                    id=item_id,
                    instrument_id=instrument_id,
                    title=title,
                    published_at=published_at,
                    source=notice_type,
                    url=url,
                    notice_type=notice_type,
                )
            )
        return items

    def _fetch_research(
        self,
        instrument_id: InstrumentId,
        symbol: str,
        warnings: list[str],
    ) -> list[ResearchReportEvent]:
        records = records_from_source_table(
            self._call(lambda: self._research(symbol=symbol))
        )
        items: list[ResearchReportEvent] = []
        for index, row in enumerate(records):
            title = clean_text(lookup_column(row, ("报告名称",)))
            if not title:
                raise InvalidSourcePayload(
                    f"malformed ResearchReportEvent at source row {index}: missing title"
                )
            organization = clean_text(lookup_column(row, ("机构",))) or None
            rating = clean_text(lookup_column(row, ("东财评级",))) or None
            published_at = parse_publication_time(
                lookup_column(row, ("日期",)),
                field=f"日期[{index}]",
                warnings=warnings,
                context=f"{symbol} research {title!r}",
            )
            pdf_url = clean_text(lookup_column(row, ("报告PDF链接",))) or None
            item_id = stable_record_id(
                source=SOURCE,
                instrument_id=instrument_id,
                published_at=published_at,
                title=title,
                url=pdf_url,
            )
            items.append(
                ResearchReportEvent(
                    id=item_id,
                    instrument_id=instrument_id,
                    title=title,
                    published_at=published_at,
                    source=organization,
                    url=pdf_url,
                    organization=organization,
                    rating=rating,
                    pdf_url=pdf_url,
                )
            )
        return items

    def _fetch_block_trades(
        self,
        instrument_id: InstrumentId,
        symbol: str,
        warnings: list[str],
    ) -> list[BlockTradeEvent]:
        end = self._today()
        begin = end - timedelta(days=BLOCK_TRADES_LOOKBACK_DAYS)
        records = records_from_source_table(
            self._call(
                lambda: self._block_trades(
                    start_date=_ymd(begin),
                    end_date=_ymd(end),
                )
            )
        )
        items: list[BlockTradeEvent] = []
        for index, row in enumerate(records):
            code = clean_text(lookup_column(row, ("证券代码",)))
            if not code:
                raise InvalidSourcePayload(
                    f"malformed BlockTradeEvent at source row {index}: missing code"
                )
            if code.zfill(6) != symbol:
                continue
            published_at = parse_publication_time(
                lookup_column(row, ("交易日期",)),
                field=f"交易日期[{index}]",
                warnings=warnings,
                context=f"{symbol} block trade",
            )
            deal_price = as_optional_float(lookup_column(row, ("成交价",)), field="成交价")
            premium_pct = as_optional_float(lookup_column(row, ("折溢率",)), field="折溢率")
            volume = as_optional_float(lookup_column(row, ("成交量",)), field="成交量")
            amount = as_optional_float(lookup_column(row, ("成交额",)), field="成交额")
            buyer = clean_text(lookup_column(row, ("买方营业部",))) or None
            seller = clean_text(lookup_column(row, ("卖方营业部",))) or None
            close_price = as_optional_float(lookup_column(row, ("收盘价",)), field="收盘价")
            pct_change = as_optional_float(lookup_column(row, ("涨跌幅",)), field="涨跌幅")
            title = (
                f"大宗成交 {deal_price}"
                if deal_price is not None
                else "大宗交易"
            )
            item_id = stable_record_id(
                source=SOURCE,
                instrument_id=instrument_id,
                published_at=published_at,
                title=title,
                url=None,
                identity_parts=(deal_price, volume, amount, buyer, seller),
            )
            items.append(
                BlockTradeEvent(
                    id=item_id,
                    instrument_id=instrument_id,
                    title=title,
                    published_at=published_at,
                    source=buyer or seller,
                    deal_price=deal_price,
                    volume=volume,
                    amount=amount,
                    premium_pct=premium_pct,
                    buyer=buyer,
                    seller=seller,
                    close_price=close_price,
                    pct_change=pct_change,
                )
            )
        return items

    def _fetch_holder_changes(
        self,
        instrument_id: InstrumentId,
        symbol: str,
        warnings: list[str],
    ) -> list[HolderChangeEvent]:
        exchange = _holder_exchange(symbol)
        if exchange == "sse":
            payload = self._call(lambda: self._holder_sse(symbol=symbol))
        elif exchange == "bse":
            payload = self._call(lambda: self._holder_bse(symbol=symbol))
        else:
            payload = self._call(lambda: self._holder_szse(symbol=symbol))
        records = records_from_source_table(payload)
        items: list[HolderChangeEvent] = []
        for index, row in enumerate(records):
            if exchange == "sse":
                person = clean_text(lookup_column(row, ("姓名",))) or None
                role = clean_text(lookup_column(row, ("职务",))) or None
                change_shares = as_optional_float(
                    lookup_column(row, ("变动数",)), field="变动数"
                )
                average_price = as_optional_float(
                    lookup_column(row, ("本次变动平均价格",)),
                    field="本次变动平均价格",
                )
                reason = clean_text(lookup_column(row, ("变动原因",))) or None
                published_raw = lookup_column(row, ("变动日期",)) or lookup_column(
                    row, ("填报日期",)
                )
            else:
                person = (
                    clean_text(lookup_column(row, ("股份变动人姓名",)))
                    or clean_text(lookup_column(row, ("董监高姓名",)))
                    or None
                )
                role = clean_text(lookup_column(row, ("职务",))) or None
                change_shares = as_optional_float(
                    lookup_column(row, ("变动股份数量",)), field="变动股份数量"
                )
                average_price = as_optional_float(
                    lookup_column(row, ("成交均价",)), field="成交均价"
                )
                reason = clean_text(lookup_column(row, ("变动原因",))) or None
                published_raw = lookup_column(row, ("变动日期",))
            if not person and change_shares is None:
                raise InvalidSourcePayload(
                    f"malformed HolderChangeEvent at source row {index}: "
                    "missing person and change_shares"
                )
            published_at = parse_publication_time(
                published_raw,
                field=f"变动日期[{index}]",
                warnings=warnings,
                context=f"{symbol} holder change",
            )
            title = person or "股东变更"
            if role:
                title = f"{person}（{role}）" if person else role
            item_id = stable_record_id(
                source=SOURCE,
                instrument_id=instrument_id,
                published_at=published_at,
                title=title,
                url=None,
                identity_parts=(person, role, change_shares, average_price, reason),
            )
            items.append(
                HolderChangeEvent(
                    id=item_id,
                    instrument_id=instrument_id,
                    title=title,
                    published_at=published_at,
                    source=reason,
                    person=person,
                    role=role,
                    change_shares=change_shares,
                    average_price=average_price,
                    reason=reason,
                )
            )
        return items

    def _call(self, operation: Callable[[], object]) -> object:
        try:
            return call_with_retries(operation, retries=self._retries, sleep=self._sleep)
        except Exception as exc:
            raise translate_transport_error(exc) from exc
