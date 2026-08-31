"""AKShare Classification and Membership Adapters."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from astock_core.market_data import (
    CSINDEX_TAXONOMY,
    Classification,
    ClassificationKind,
    ClassificationQuery,
    Dataset,
    EASTMONEY_TAXONOMY,
    InstrumentId,
    InvalidSourcePayload,
    Membership,
    MembershipQuery,
    UnsupportedQuery,
    from_legacy_symbol,
    validate_classification_dataset,
    validate_membership_dataset,
)

from astock.providers._support import call_with_retries, translate_transport_error
from astock.providers.akshare._tables import lookup_column, records_from_source_table

SOURCE = "akshare"
_BOARD_ID_COLUMNS = ("板块代码",)
_BOARD_NAME_COLUMNS = ("板块名称",)
_MEMBER_CODE_COLUMNS = ("代码", "code")
_MEMBER_NAME_COLUMNS = ("名称", "name")
_INDEX_CODE_COLUMNS = ("成分券代码",)
_INDEX_NAME_COLUMNS = ("成分券名称",)

BoardNames = Callable[[], object]
IndexNames = Callable[[], object]
BoardMembers = Callable[..., object]
IndexMembersCsindex = Callable[..., object]
IndexMembersSina = Callable[..., object]
Sleep = Callable[[float], None]
Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _default_sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


def _default_industry_names() -> object:
    import akshare as ak

    return ak.stock_board_industry_name_em()


def _default_concept_names() -> object:
    import akshare as ak

    return ak.stock_board_concept_name_em()


def _default_index_names() -> object:
    import akshare as ak

    return ak.index_stock_info()


def _default_industry_members(symbol: str) -> object:
    import akshare as ak

    return ak.stock_board_industry_cons_em(symbol=symbol)


def _default_concept_members(symbol: str) -> object:
    import akshare as ak

    return ak.stock_board_concept_cons_em(symbol=symbol)


def _default_index_members_csindex(symbol: str) -> object:
    import akshare as ak

    return ak.index_stock_cons_csindex(symbol=symbol)


def _default_index_members_sina(symbol: str) -> object:
    import akshare as ak

    return ak.index_stock_cons_sina(symbol=symbol)


def _normalize_legacy_code(raw: object) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) < 6:
        return None
    return digits[-6:].zfill(6)


def _classification_kind_for_query(query: ClassificationQuery) -> ClassificationKind:
    if query.kind is None:
        raise UnsupportedQuery("ClassificationQuery.kind is required for AKShare boards")
    return query.kind


class AkshareClassificationAdapter:
    """Translate AKShare Eastmoney board catalogs into Classifications."""

    def __init__(
        self,
        *,
        industry_names: BoardNames | None = None,
        concept_names: BoardNames | None = None,
        index_names: IndexNames | None = None,
        timeout: float = 20.0,
        retries: int = 1,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._industry_names = industry_names or _default_industry_names
        self._concept_names = concept_names or _default_concept_names
        self._index_names = index_names or _default_index_names
        self._timeout = timeout
        self._retries = retries
        self._sleep = sleep or _default_sleep
        self._clock = clock or _default_clock

    def fetch_classifications(self, query: ClassificationQuery) -> Dataset[Classification]:
        fetched_at = self._clock()
        kind = _classification_kind_for_query(query)
        taxonomy = (
            CSINDEX_TAXONOMY
            if kind == ClassificationKind.INDEX
            else EASTMONEY_TAXONOMY
        )
        if query.taxonomy is not None and query.taxonomy != taxonomy:
            raise UnsupportedQuery(f"unsupported classification taxonomy: {query.taxonomy}")
        if kind == ClassificationKind.INDEX:
            fetcher = self._index_names
            id_columns = ("index_code", "指数代码")
            name_columns = ("display_name", "指数名称")
        else:
            fetcher = (
                self._industry_names
                if kind == ClassificationKind.INDUSTRY
                else self._concept_names
            )
            id_columns = _BOARD_ID_COLUMNS
            name_columns = _BOARD_NAME_COLUMNS
        try:
            records = records_from_source_table(
                call_with_retries(
                    fetcher,
                    retries=self._retries,
                    sleep=self._sleep,
                )
            )
        except Exception as exc:
            raise translate_transport_error(exc) from exc
        items: list[Classification] = []
        for index, record in enumerate(records):
            classification_id = str(lookup_column(record, id_columns) or "").strip()
            classification_name = str(lookup_column(record, name_columns) or "").strip()
            if not classification_id or not classification_name:
                raise InvalidSourcePayload(
                    f"malformed {kind.value} classification at row {index}: "
                    "missing id or name"
                )
            if kind == ClassificationKind.INDEX:
                classification_id = classification_id.zfill(6)
            if query.ids and classification_id not in query.ids:
                continue
            items.append(
                Classification(
                    id=classification_id,
                    kind=kind,
                    name=classification_name,
                    taxonomy=taxonomy,
                )
            )
        items.sort(key=lambda item: (item.taxonomy, item.kind.value, item.id))
        dataset = Dataset(
            items=tuple(items),
            source=SOURCE,
            fetched_at=fetched_at,
            complete=True,
        )
        return validate_classification_dataset(dataset, query)


class AkshareMembershipAdapter:
    """Translate AKShare board and index constituent tables into Memberships."""

    def __init__(
        self,
        *,
        industry_members: BoardMembers | None = None,
        concept_members: BoardMembers | None = None,
        index_members_csindex: IndexMembersCsindex | None = None,
        index_members_sina: IndexMembersSina | None = None,
        timeout: float = 20.0,
        retries: int = 1,
        sleep: Sleep | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._industry_members = industry_members or _default_industry_members
        self._concept_members = concept_members or _default_concept_members
        self._index_members_csindex = index_members_csindex or _default_index_members_csindex
        self._index_members_sina = index_members_sina or _default_index_members_sina
        self._timeout = timeout
        self._retries = retries
        self._sleep = sleep or _default_sleep
        self._clock = clock or _default_clock
        self._display_names: dict[str, str] = {}

    def display_names(self) -> dict[str, str]:
        """Return display names from the most recent fetch keyed by legacy code."""
        return dict(self._display_names)

    def fetch_memberships(self, query: MembershipQuery) -> Dataset[Membership]:
        fetched_at = self._clock()
        self._display_names = {}
        if query.taxonomy == EASTMONEY_TAXONOMY:
            dataset = self._fetch_board_memberships(query, fetched_at=fetched_at)
        elif query.taxonomy == CSINDEX_TAXONOMY:
            dataset = self._fetch_index_memberships(query, fetched_at=fetched_at)
        elif query.taxonomy is None:
            raise UnsupportedQuery("MembershipQuery.taxonomy is required")
        else:
            raise UnsupportedQuery(f"unsupported membership taxonomy: {query.taxonomy}")
        return validate_membership_dataset(dataset, query)

    def _fetch_board_memberships(
        self,
        query: MembershipQuery,
        *,
        fetched_at: datetime,
    ) -> Dataset[Membership]:
        if not query.classification_id:
            raise UnsupportedQuery(
                "eastmoney memberships require MembershipQuery.classification_id"
            )
        board_id = query.classification_id
        kind = query.kind
        if kind not in (ClassificationKind.INDUSTRY, ClassificationKind.CONCEPT):
            raise UnsupportedQuery(
                "eastmoney board memberships require industry or concept kind"
            )
        fetcher = (
            self._industry_members
            if kind == ClassificationKind.INDUSTRY
            else self._concept_members
        )
        try:
            records = records_from_source_table(
                call_with_retries(
                    lambda: fetcher(board_id),
                    retries=self._retries,
                    sleep=self._sleep,
                )
            )
        except Exception as exc:
            raise translate_transport_error(exc) from exc
        items: list[Membership] = []
        seen: set[InstrumentId] = set()
        for index, record in enumerate(records):
            code = _normalize_legacy_code(lookup_column(record, _MEMBER_CODE_COLUMNS))
            if not code:
                raise InvalidSourcePayload(
                    f"malformed board member at row {index}: missing instrument code"
                )
            instrument_id = from_legacy_symbol(code)
            if instrument_id in seen:
                raise InvalidSourcePayload(
                    f"duplicate board member at row {index}: {code}"
                )
            seen.add(instrument_id)
            name = str(lookup_column(record, _MEMBER_NAME_COLUMNS) or code).strip() or code
            self._display_names[code] = name
            if query.instrument_id is not None and instrument_id != query.instrument_id:
                continue
            items.append(
                Membership(
                    classification_id=board_id,
                    taxonomy=EASTMONEY_TAXONOMY,
                    instrument_id=instrument_id,
                )
            )
        items.sort(
            key=lambda item: (
                item.taxonomy,
                item.classification_id,
                item.instrument_id.value,
            )
        )
        return Dataset(
            items=tuple(items),
            source=SOURCE,
            fetched_at=fetched_at,
            complete=True,
        )

    def _fetch_index_memberships(
        self,
        query: MembershipQuery,
        *,
        fetched_at: datetime,
    ) -> Dataset[Membership]:
        if not query.classification_id:
            raise UnsupportedQuery(
                "csindex memberships require MembershipQuery.classification_id"
            )
        symbol = query.classification_id.zfill(6)
        if query.kind not in (None, ClassificationKind.INDEX):
            raise UnsupportedQuery("csindex memberships require index kind")
        records, warnings = self._index_member_records(symbol)
        items: list[Membership] = []
        seen: set[InstrumentId] = set()
        for index, record in enumerate(records):
            code = _normalize_legacy_code(lookup_column(record, _INDEX_CODE_COLUMNS))
            if not code:
                code = _normalize_legacy_code(lookup_column(record, ("code",)))
            if not code:
                raise InvalidSourcePayload(
                    f"malformed index member at row {index}: missing instrument code"
                )
            instrument_id = from_legacy_symbol(code)
            if instrument_id in seen:
                raise InvalidSourcePayload(
                    f"duplicate index member at row {index}: {code}"
                )
            seen.add(instrument_id)
            name = str(
                lookup_column(record, _INDEX_NAME_COLUMNS)
                or lookup_column(record, ("name",))
                or code
            ).strip() or code
            self._display_names[code] = name
            if query.instrument_id is not None and instrument_id != query.instrument_id:
                continue
            items.append(
                Membership(
                    classification_id=symbol,
                    taxonomy=CSINDEX_TAXONOMY,
                    instrument_id=instrument_id,
                )
            )
        items.sort(
            key=lambda item: (
                item.taxonomy,
                item.classification_id,
                item.instrument_id.value,
            )
        )
        return Dataset(
            items=tuple(items),
            source=SOURCE,
            fetched_at=fetched_at,
            complete=True,
            warnings=warnings,
        )

    def _index_member_records(self, symbol: str) -> tuple[list[dict[str, object]], tuple[str, ...]]:
        try:
            payload = call_with_retries(
                lambda: self._index_members_csindex(symbol),
                retries=self._retries,
                sleep=self._sleep,
            )
            return records_from_source_table(payload), ()
        except Exception as exc:
            warning = f"csindex failed for {symbol}: {exc}"
            try:
                payload = call_with_retries(
                    lambda: self._index_members_sina(symbol),
                    retries=self._retries,
                    sleep=self._sleep,
                )
                return records_from_source_table(payload), (warning,)
            except Exception as fallback_exc:
                raise translate_transport_error(fallback_exc) from exc
