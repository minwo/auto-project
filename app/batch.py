from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from statistics import mean

from app.domain import CandidateEvaluation, CatalystItem, DisclosureLink, NewsLink, StockSnapshot
from app.repository import select_top_candidates
from app.pullback_scoring import evaluate_pullback_snapshot
from app.scoring import evaluate_snapshot
from app.surge_scoring import evaluate_surge_snapshot
from app.trend_scoring import evaluate_trend_snapshot


@dataclass(slots=True)
class PriceHistoryRow:
    code: str
    name: str
    market: str
    sector: str
    listed_at: date | None
    is_common_stock: bool
    is_preferred: bool
    is_etf: bool
    is_etn: bool
    is_spac: bool
    trade_date: date
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    turnover: float


@dataclass(slots=True)
class WarningRow:
    code: str
    warning_level: str | None
    is_halted: bool
    is_under_management: bool


@dataclass(slots=True)
class DisclosureRow:
    code: str
    report_name: str
    report_type: str | None
    material_tag: str | None
    url: str
    is_material: bool


@dataclass(slots=True)
class NewsRow:
    code: str
    title: str
    url: str
    source: str
    published_at: datetime | None
    summary: str | None
    news_type: str | None
    trust_score: float


@dataclass(slots=True)
class MarketRegimeSnapshot:
    regime: str
    breadth_pct: float
    avg_return_pct: float
    source: str = "breadth"
    index_name: str | None = None
    index_close: float = 0.0
    index_return_pct: float = 0.0
    index_return_5d_pct: float = 0.0
    index_return_20d_pct: float = 0.0
    index_return_60d_pct: float = 0.0
    index_ma20_gap_pct: float = 0.0
    index_ma60_gap_pct: float = 0.0
    short_trend: str = "neutral"
    mid_trend: str = "neutral"
    long_trend: str = "neutral"

    def as_dict(self) -> dict[str, object]:
        return {
            "regime": self.regime,
            "breadthPct": round(self.breadth_pct, 2),
            "avgReturnPct": round(self.avg_return_pct, 2),
            "source": self.source,
            "indexName": self.index_name,
            "indexClose": round(self.index_close, 2),
            "indexReturnPct": round(self.index_return_pct, 2),
            "indexReturn5dPct": round(self.index_return_5d_pct, 2),
            "indexReturn20dPct": round(self.index_return_20d_pct, 2),
            "indexReturn60dPct": round(self.index_return_60d_pct, 2),
            "indexMa20GapPct": round(self.index_ma20_gap_pct, 2),
            "indexMa60GapPct": round(self.index_ma60_gap_pct, 2),
            "shortTrend": self.short_trend,
            "midTrend": self.mid_trend,
            "longTrend": self.long_trend,
        }


INDEX_CODES = {"KOSPI", "KOSDAQ", "KOSPI200", "001", "1001", "2001", "069500"}


def _safe_mean(values: list[float]) -> float:
    clean = [value for value in values if value > 0]
    if not clean:
        return 0.0
    return float(mean(clean))


def _pct_change(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return ((current - previous) / previous) * 100.0


def _classify_market_regime(returns: list[float]) -> tuple[str, float, float]:
    if not returns:
        return "neutral", 0.0, 0.0

    rising_count = sum(1 for value in returns if value > 0)
    breadth_pct = (rising_count / len(returns)) * 100.0
    avg_return_pct = float(mean(returns))

    if breadth_pct <= 35.0 and avg_return_pct <= -1.0:
        return "bear", breadth_pct, avg_return_pct
    if breadth_pct <= 45.0 or avg_return_pct <= -0.5:
        return "weak", breadth_pct, avg_return_pct
    if breadth_pct >= 62.0 and avg_return_pct >= 0.4:
        return "strong", breadth_pct, avg_return_pct
    return "neutral", breadth_pct, avg_return_pct


def _is_index_row(row: PriceHistoryRow) -> bool:
    normalized_name = row.name.upper()
    return (
        row.code.upper() in INDEX_CODES
        or row.market.upper() == "INDEX"
        or "KOSPI" in normalized_name
        or "KOSDAQ" in normalized_name
        or "코스피" in row.name
        or "코스닥" in row.name
    )


def _gap_pct(value: float, base: float) -> float:
    if base <= 0:
        return 0.0
    return ((value - base) / base) * 100.0


def _trend_from_return(return_pct: float, ma_gap_pct: float, *, strong_threshold: float, weak_threshold: float) -> str:
    if return_pct >= strong_threshold and ma_gap_pct >= 0:
        return "up"
    if return_pct <= -strong_threshold and ma_gap_pct <= 0:
        return "down"
    if return_pct >= weak_threshold:
        return "up"
    if return_pct <= -weak_threshold:
        return "down"
    return "neutral"


def _classify_index_regime(histories_by_code: dict[str, list[PriceHistoryRow]]) -> MarketRegimeSnapshot | None:
    index_histories = [
        rows
        for rows in histories_by_code.values()
        if rows and _is_index_row(rows[0]) and len(rows) >= 20
    ]
    if not index_histories:
        return None

    def priority(rows: list[PriceHistoryRow]) -> tuple[int, str]:
        current = rows[0]
        name = current.name.upper()
        if current.code.upper() in {"KOSPI", "001", "1001"} or "KOSPI" in name or "코스피" in current.name:
            return (0, current.code)
        if current.code.upper() == "069500":
            return (1, current.code)
        return (2, current.code)

    rows = sorted(index_histories, key=priority)[0]
    current = rows[0]
    previous_close = rows[1].close_price if len(rows) > 1 else current.close_price
    ma5 = _safe_mean([item.close_price for item in rows[:5]]) if len(rows) >= 5 else 0.0
    ma20 = _safe_mean([item.close_price for item in rows[:20]])
    ma60 = _safe_mean([item.close_price for item in rows[:60]]) if len(rows) >= 60 else 0.0
    return_1d = _pct_change(current.close_price, previous_close)
    return_5d = _pct_change(current.close_price, rows[5].close_price) if len(rows) > 5 else return_1d
    return_20d = _pct_change(current.close_price, rows[20].close_price) if len(rows) > 20 else return_5d
    return_60d = _pct_change(current.close_price, rows[60].close_price) if len(rows) > 60 else return_20d
    ma5_gap = _gap_pct(current.close_price, ma5)
    ma20_gap = _gap_pct(current.close_price, ma20)
    ma60_gap = _gap_pct(current.close_price, ma60)
    short_trend = _trend_from_return(return_5d, ma5_gap, strong_threshold=1.2, weak_threshold=0.5)
    mid_trend = _trend_from_return(return_20d, ma20_gap, strong_threshold=3.0, weak_threshold=1.2)
    long_trend = _trend_from_return(return_60d, ma60_gap, strong_threshold=6.0, weak_threshold=2.5)

    if short_trend == "down" and mid_trend == "down" and (long_trend == "down" or ma60 == 0):
        regime = "bear"
    elif short_trend == "down" or mid_trend == "down" or return_1d <= -0.7:
        regime = "weak"
    elif short_trend == "up" and mid_trend == "up":
        regime = "strong"
    else:
        regime = "neutral"

    return MarketRegimeSnapshot(
        regime=regime,
        breadth_pct=0.0,
        avg_return_pct=return_1d,
        source="index",
        index_name=current.name,
        index_close=current.close_price,
        index_return_pct=return_1d,
        index_return_5d_pct=return_5d,
        index_return_20d_pct=return_20d,
        index_return_60d_pct=return_60d,
        index_ma20_gap_pct=ma20_gap,
        index_ma60_gap_pct=ma60_gap,
        short_trend=short_trend,
        mid_trend=mid_trend,
        long_trend=long_trend,
    )


def build_market_regime_snapshot(
    *,
    score_date: date,
    histories_by_code: dict[str, list[PriceHistoryRow]],
    current_rows: dict[str, PriceHistoryRow],
    prev_close_by_code: dict[str, float],
) -> MarketRegimeSnapshot:
    breadth_returns = [
        _pct_change(current.close_price, prev_close_by_code.get(code, 0.0))
        for code, current in current_rows.items()
        if not _is_index_row(current)
    ]
    breadth_regime, breadth_pct, avg_return_pct = _classify_market_regime(breadth_returns)
    breadth_snapshot = MarketRegimeSnapshot(
        regime=breadth_regime,
        breadth_pct=breadth_pct,
        avg_return_pct=avg_return_pct,
        source="breadth",
    )

    index_snapshot = _classify_index_regime(histories_by_code)
    if index_snapshot is None:
        return breadth_snapshot
    return MarketRegimeSnapshot(
        regime=index_snapshot.regime,
        breadth_pct=breadth_pct,
        avg_return_pct=avg_return_pct,
        source=index_snapshot.source,
        index_name=index_snapshot.index_name,
        index_close=index_snapshot.index_close,
        index_return_pct=index_snapshot.index_return_pct,
        index_return_5d_pct=index_snapshot.index_return_5d_pct,
        index_return_20d_pct=index_snapshot.index_return_20d_pct,
        index_return_60d_pct=index_snapshot.index_return_60d_pct,
        index_ma20_gap_pct=index_snapshot.index_ma20_gap_pct,
        index_ma60_gap_pct=index_snapshot.index_ma60_gap_pct,
        short_trend=index_snapshot.short_trend,
        mid_trend=index_snapshot.mid_trend,
        long_trend=index_snapshot.long_trend,
    )


def build_market_regime_for_date(
    *,
    score_date: date,
    price_rows: list[PriceHistoryRow],
) -> MarketRegimeSnapshot:
    histories_by_code: dict[str, list[PriceHistoryRow]] = defaultdict(list)
    for row in price_rows:
        histories_by_code[row.code].append(row)
    for rows in histories_by_code.values():
        rows.sort(key=lambda item: item.trade_date, reverse=True)

    current_rows: dict[str, PriceHistoryRow] = {}
    prev_close_by_code: dict[str, float] = {}
    for code, rows in histories_by_code.items():
        if not rows or rows[0].trade_date != score_date:
            continue
        current_rows[code] = rows[0]
        prev_close_by_code[code] = rows[1].close_price if len(rows) > 1 else rows[0].open_price or rows[0].close_price

    return build_market_regime_snapshot(
        score_date=score_date,
        histories_by_code=histories_by_code,
        current_rows=current_rows,
        prev_close_by_code=prev_close_by_code,
    )


def _classify_disclosure_kind(disclosure: DisclosureRow) -> str:
    haystack = " ".join(
        part.lower()
        for part in [
            disclosure.report_name,
            disclosure.report_type or "",
            disclosure.material_tag or "",
        ]
    )
    if any(keyword in haystack for keyword in ["실적", "earnings", "결산", "영업", "매출", "잠정", "손익", "이익", "매출액", "영업이익"]):
        return "earnings"
    if any(keyword in haystack for keyword in ["contract", "계약", "수주", "공급", "판매", "납품", "체결", "선정", "구매주문", "po"]):
        return "contract"
    if any(keyword in haystack for keyword in ["자기주식", "자사주", "취득", "소각", "신탁계약"]):
        return "buyback"
    if any(keyword in haystack for keyword in ["배당", "현금ㆍ현물배당", "dividend", "중간배당", "분기배당"]):
        return "dividend"
    if any(keyword in haystack for keyword in ["승인", "허가", "품목허가", "approval", "license", "인증", "fda", "임상", "허가신청"]):
        return "approval"
    if any(keyword in haystack for keyword in ["감자", "capital reduction"]):
        return "capital_reduction"
    if any(keyword in haystack for keyword in ["유상증자", "전환사채", "신주인수권", "cb", "bw", "교환사채", "사채권", "전환가액", "발행결정"]):
        return "dilution"
    if any(keyword in haystack for keyword in ["불성실", "관리종목", "상장폐지", "거래정지", "투자주의", "투자경고", "투자위험"]):
        return "trading_risk"
    if any(keyword in haystack for keyword in ["최대주주변경", "횡령", "배임", "소송", "가압류", "회생", "파산", "감사의견"]):
        return "management_risk"
    if any(keyword in haystack for keyword in ["policy", "정책", "정부", "지원", "국책", "과제", "보조금"]):
        return "policy"
    if any(keyword in haystack for keyword in ["무상증자", "액면분할", "주식분할"]):
        return "capital_event"
    if any(keyword in haystack for keyword in ["합병", "분할", "영업양수", "영업양도", "인수", "m&a"]):
        return "corporate_action"
    if any(keyword in haystack for keyword in ["시설투자", "신규시설", "공장", "증설", "투자결정"]):
        return "capex"
    return "disclosure"


def _build_catalysts(disclosures: list[DisclosureRow]) -> tuple[list[CatalystItem], list[DisclosureLink]]:
    catalysts: list[CatalystItem] = []
    links: list[DisclosureLink] = []
    for disclosure in disclosures:
        links.append(DisclosureLink(title=disclosure.report_name, url=disclosure.url))
        catalysts.append(
            CatalystItem(
                kind=_classify_disclosure_kind(disclosure),
                title=disclosure.report_name,
                url=disclosure.url,
                trust_score=1.0 if disclosure.is_material else 0.8,
            )
        )
    return catalysts, links


def _build_news_catalysts(news_rows: list[NewsRow]) -> tuple[list[CatalystItem], list[NewsLink]]:
    catalysts: list[CatalystItem] = []
    links: list[NewsLink] = []
    seen_urls: set[str] = set()
    for news in news_rows:
        if news.url not in seen_urls:
            links.append(NewsLink(title=news.title, url=news.url))
            seen_urls.add(news.url)
        catalysts.append(
            CatalystItem(
                kind=news.news_type or "news",
                title=news.title,
                url=news.url,
                trust_score=max(0.0, min(news.trust_score, 1.0)),
            )
        )
    return catalysts, links


def build_snapshots_for_date(
    *,
    score_date: date,
    price_rows: list[PriceHistoryRow],
    warning_rows: list[WarningRow] | None = None,
    disclosure_rows: list[DisclosureRow] | None = None,
    news_rows: list[NewsRow] | None = None,
) -> list[StockSnapshot]:
    histories_by_code: dict[str, list[PriceHistoryRow]] = defaultdict(list)
    for row in price_rows:
        histories_by_code[row.code].append(row)
    for rows in histories_by_code.values():
        rows.sort(key=lambda item: item.trade_date, reverse=True)

    warnings_by_code = {row.code: row for row in (warning_rows or [])}
    disclosures_by_code: dict[str, list[DisclosureRow]] = defaultdict(list)
    for row in disclosure_rows or []:
        disclosures_by_code[row.code].append(row)
    news_by_code: dict[str, list[NewsRow]] = defaultdict(list)
    for row in news_rows or []:
        news_by_code[row.code].append(row)

    current_rows: dict[str, PriceHistoryRow] = {}
    avg_turnover_by_code: dict[str, float] = {}
    avg_volume_by_code: dict[str, float] = {}
    prev_close_by_code: dict[str, float] = {}

    for code, rows in histories_by_code.items():
        if not rows or rows[0].trade_date != score_date:
            continue
        current_rows[code] = rows[0]
        previous_window = rows[1:21]
        avg_turnover_by_code[code] = _safe_mean([item.turnover for item in previous_window])
        avg_volume_by_code[code] = _safe_mean([item.volume for item in previous_window])
        prev_close_by_code[code] = rows[1].close_price if len(rows) > 1 else rows[0].open_price or rows[0].close_price

    eligible_current_rows = {
        code: row
        for code, row in current_rows.items()
        if not _is_index_row(row)
    }

    sector_current_turnover: dict[str, float] = defaultdict(float)
    sector_prev_turnover: dict[str, float] = defaultdict(float)
    sector_rising_peers: dict[str, int] = defaultdict(int)

    for code, current in eligible_current_rows.items():
        sector = current.sector or "Unclassified"
        sector_current_turnover[sector] += current.turnover
        sector_prev_turnover[sector] += avg_turnover_by_code.get(code, 0.0)
        if current.close_price > prev_close_by_code.get(code, 0.0):
            sector_rising_peers[sector] += 1

    market_snapshot = build_market_regime_for_date(
        score_date=score_date,
        price_rows=price_rows,
    )

    snapshots: list[StockSnapshot] = []
    for code, current in eligible_current_rows.items():
        rows = histories_by_code[code]
        previous_close = prev_close_by_code.get(code, current.open_price or current.close_price)
        ref_close_3d = rows[3].close_price if len(rows) > 3 else previous_close
        prior_returns = [
            _pct_change(rows[index].close_price, rows[index + 1].close_price)
            for index in range(1, min(len(rows) - 1, 3))
        ]
        has_leading_move = any(item > 0 for item in prior_returns)

        disclosures = disclosures_by_code.get(code, [])
        catalysts, disclosure_links = _build_catalysts(disclosures)
        news_catalysts, news_links = _build_news_catalysts(news_by_code.get(code, []))
        catalysts.extend(news_catalysts)
        warning = warnings_by_code.get(code)
        listed_days = (score_date - current.listed_at).days + 1 if current.listed_at else len(rows)
        avg_turnover_20d = avg_turnover_by_code.get(code, 0.0)
        avg_volume_20d = avg_volume_by_code.get(code, 0.0)
        sector = current.sector or "Unclassified"
        sector_prev_avg = sector_prev_turnover.get(sector, 0.0)
        sector_turnover_ratio = (
            sector_current_turnover[sector] / sector_prev_avg if sector_prev_avg > 0 else 0.0
        )

        snapshots.append(
            StockSnapshot(
                date=score_date,
                code=code,
                name=current.name,
                market=current.market,
                sector=sector,
                is_common_stock=current.is_common_stock,
                listed_days=listed_days,
                avg_turnover_20d=avg_turnover_20d,
                avg_volume_20d=avg_volume_20d,
                close=current.close_price,
                high=current.high_price,
                low=current.low_price,
                open_price=current.open_price,
                prev_close=previous_close,
                volume=current.volume,
                turnover=current.turnover,
                turnover_ratio_20d=(current.turnover / avg_turnover_20d) if avg_turnover_20d > 0 else 0.0,
                volume_ratio_20d=(current.volume / avg_volume_20d) if avg_volume_20d > 0 else 0.0,
                return_3d_pct=_pct_change(current.close_price, ref_close_3d),
                sector_rising_peers=max(sector_rising_peers.get(sector, 0) - 1, 0),
                sector_turnover_ratio=sector_turnover_ratio,
                has_leading_move=has_leading_move,
                market_regime=market_snapshot.regime,
                market_breadth_pct=market_snapshot.breadth_pct,
                market_avg_return_pct=market_snapshot.avg_return_pct,
                market_regime_source=market_snapshot.source,
                market_index_name=market_snapshot.index_name,
                market_index_close=market_snapshot.index_close,
                market_index_return_pct=market_snapshot.index_return_pct,
                market_index_return_5d_pct=market_snapshot.index_return_5d_pct,
                market_index_return_20d_pct=market_snapshot.index_return_20d_pct,
                market_index_return_60d_pct=market_snapshot.index_return_60d_pct,
                market_index_ma20_gap_pct=market_snapshot.index_ma20_gap_pct,
                market_index_ma60_gap_pct=market_snapshot.index_ma60_gap_pct,
                market_short_trend=market_snapshot.short_trend,
                market_mid_trend=market_snapshot.mid_trend,
                market_long_trend=market_snapshot.long_trend,
                warning_level=warning.warning_level if warning else None,
                is_etf=current.is_etf,
                is_etn=current.is_etn,
                is_preferred=current.is_preferred,
                is_spac=current.is_spac,
                is_under_management=warning.is_under_management if warning else False,
                is_trading_halted=warning.is_halted if warning else False,
                catalysts=catalysts,
                news_links=news_links,
                disclosure_links=disclosure_links,
            )
        )

    return snapshots


def evaluate_daily_batch(
    *,
    score_date: date,
    price_rows: list[PriceHistoryRow],
    warning_rows: list[WarningRow] | None = None,
    disclosure_rows: list[DisclosureRow] | None = None,
    news_rows: list[NewsRow] | None = None,
    generated_at: datetime | None = None,
) -> list[CandidateEvaluation]:
    snapshots = build_snapshots_for_date(
        score_date=score_date,
        price_rows=price_rows,
        warning_rows=warning_rows,
        disclosure_rows=disclosure_rows,
        news_rows=news_rows,
    )
    evaluations = [
        evaluation
        for evaluation in (
            evaluate_snapshot(snapshot, generated_at=generated_at)
            for snapshot in snapshots
        )
        if evaluation is not None
    ]
    return evaluations


def evaluate_daily_batch_with_surge(
    *,
    score_date: date,
    price_rows: list[PriceHistoryRow],
    warning_rows: list[WarningRow] | None = None,
    disclosure_rows: list[DisclosureRow] | None = None,
    news_rows: list[NewsRow] | None = None,
    generated_at: datetime | None = None,
) -> list[CandidateEvaluation]:
    snapshots = build_snapshots_for_date(
        score_date=score_date,
        price_rows=price_rows,
        warning_rows=warning_rows,
        disclosure_rows=disclosure_rows,
        news_rows=news_rows,
    )
    histories_by_code: dict[str, list[PriceHistoryRow]] = defaultdict(list)
    for row in price_rows:
        histories_by_code[row.code].append(row)
    for rows in histories_by_code.values():
        rows.sort(key=lambda item: item.trade_date, reverse=True)

    evaluations: list[CandidateEvaluation] = []
    for snapshot in snapshots:
        stable = evaluate_snapshot(snapshot, generated_at=generated_at)
        if stable is not None:
            evaluations.append(stable)
        surge = evaluate_surge_snapshot(
            snapshot,
            histories_by_code.get(snapshot.code, []),
            generated_at=generated_at,
        )
        if surge is not None:
            evaluations.append(surge)
        pullback = evaluate_pullback_snapshot(
            snapshot,
            histories_by_code.get(snapshot.code, []),
            generated_at=generated_at,
        )
        if pullback is not None:
            evaluations.append(pullback)
        trend = evaluate_trend_snapshot(
            snapshot,
            histories_by_code.get(snapshot.code, []),
            generated_at=generated_at,
        )
        if trend is not None:
            evaluations.append(trend)
    return evaluations


def build_top_candidates(
    *,
    score_date: date,
    price_rows: list[PriceHistoryRow],
    warning_rows: list[WarningRow] | None = None,
    disclosure_rows: list[DisclosureRow] | None = None,
    news_rows: list[NewsRow] | None = None,
    generated_at: datetime | None = None,
) -> list[CandidateEvaluation]:
    evaluations = evaluate_daily_batch(
        score_date=score_date,
        price_rows=price_rows,
        warning_rows=warning_rows,
        disclosure_rows=disclosure_rows,
        news_rows=news_rows,
        generated_at=generated_at,
    )
    return select_top_candidates(evaluations)
