"""AKShare News Adapter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from astock_core.market_data import (
    Dataset,
    InstrumentId,
    InvalidSourcePayload,
    NewsItem,
    NewsQuery,
    UnsupportedQuery,
    to_legacy_symbol,
    validate_news_dataset,
)

from astock.providers._support import call_with_retries, translate_transport_error
from astock.providers.akshare._ids import stable_record_id
from astock.providers.akshare._tables import lookup_column, records_from_source_table
from astock.providers.akshare._text import clean_text
from astock.providers.akshare._time import parse_publication_time

SOURCE = "akshare"
_TITLE_COLUMNS = ("新闻标题",)
_SUMMARY_COLUMNS = ("新闻内容",)
_PUBLISHED_COLUMNS = ("发布时间",)
_PUBLISHER_COLUMNS = ("文章来源",)
_URL_COLUMNS = ("新闻链接",)

StockNews = Callable[..., object]
Sleep = Callable[[float], None]
Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def _default_stock_news(symbol: str) -> object:
    import akshare as ak

    return ak.stock_news_em(symbol=symbol)


class AkshareNewsAdapter:
    """Translate AKShare Eastmoney stock news into NewsItem records."""

    def __init__(
        self,
        *,
        stock_news: StockNews | None = None,
        retries: int = 1,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._stock_news = stock_news or _default_stock_news
        self._retries = retries
        self._sleep = sleep or _default_sleep
        self._clock = clock or _default_clock

    def fetch_news(self, query: NewsQuery) -> Dataset[NewsItem]:
        if len(query.instruments) != 1:
            raise UnsupportedQuery("AKShare news supports exactly one InstrumentId per query")
        instrument_id = query.instruments[0]
        symbol = to_legacy_symbol(instrument_id)
        records = records_from_source_table(
            self._call(lambda: self._stock_news(symbol=symbol))
        )
        warnings: list[str] = []
        items: list[NewsItem] = []
        seen: set[str] = set()
        for index, row in enumerate(records):
            title = clean_text(lookup_column(row, _TITLE_COLUMNS))
            if not title:
                raise InvalidSourcePayload(
                    f"malformed NewsItem at source row {index}: missing title"
                )
            published_at = parse_publication_time(
                lookup_column(row, _PUBLISHED_COLUMNS),
                field=f"发布时间[{index}]",
                warnings=warnings,
                context=f"{symbol} news {title!r}",
            )
            summary = clean_text(lookup_column(row, _SUMMARY_COLUMNS)) or None
            publisher = clean_text(lookup_column(row, _PUBLISHER_COLUMNS)) or None
            url = clean_text(lookup_column(row, _URL_COLUMNS)) or None
            item_id = stable_record_id(
                source=SOURCE,
                instrument_id=instrument_id,
                published_at=published_at,
                title=title,
                url=url,
            )
            if item_id in seen:
                raise InvalidSourcePayload(
                    f"duplicate NewsItem id {item_id!r} at source row {index}"
                )
            seen.add(item_id)
            items.append(
                NewsItem(
                    id=item_id,
                    instrument_id=instrument_id,
                    title=title,
                    published_at=published_at,
                    publisher=publisher,
                    summary=summary,
                    url=url,
                )
            )
        if query.start is not None:
            items = [item for item in items if item.published_at >= query.start]
        if query.end is not None:
            items = [item for item in items if item.published_at <= query.end]
        items.sort(key=lambda item: (item.published_at, item.id))
        if query.limit is not None:
            items = items[-query.limit :] if query.limit else []
        dataset = Dataset(
            items=tuple(items),
            source=SOURCE,
            fetched_at=self._clock(),
            complete=True,
            warnings=tuple(warnings),
        )
        return validate_news_dataset(dataset, query)

    def _call(self, operation: Callable[[], object]) -> object:
        try:
            return call_with_retries(operation, retries=self._retries, sleep=self._sleep)
        except Exception as exc:
            raise translate_transport_error(exc) from exc
