from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from statistics import mean, median
from typing import Any, Protocol

from app.batch import DisclosureRow, NewsRow, PriceHistoryRow, WarningRow, evaluate_daily_batch
from app.repository import select_top_candidates
from app.scoring import ScoringConfig


@dataclass(slots=True)
class CandidateResult:
    """Result of a single candidate evaluation against future prices."""

    score_date: date
    code: str
    name: str
    sector: str
    score: float
    confidence_grade: str
    entry_price: float
    max_price_3d: float
    min_price_3d: float
    close_price_3d: float
    max_return_pct: float
    min_return_pct: float
    close_return_pct: float
    hit: bool
    stop_loss_hit: bool


@dataclass(slots=True)
class DailyBacktestResult:
    """Aggregated result for a single trading day."""

    score_date: date
    market_regime: str
    total_candidates: int
    selected_count: int
    hit_count: int
    stop_loss_count: int
    hit_rate: float
    avg_max_return: float
    avg_close_return: float
    candidates: list[CandidateResult] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "scoreDate": self.score_date.isoformat(),
            "marketRegime": self.market_regime,
            "totalCandidates": self.total_candidates,
            "selectedCount": self.selected_count,
            "hitCount": self.hit_count,
            "stopLossCount": self.stop_loss_count,
            "hitRate": round(self.hit_rate, 4),
            "avgMaxReturn": round(self.avg_max_return, 2),
            "avgCloseReturn": round(self.avg_close_return, 2),
        }


@dataclass(slots=True)
class BacktestReport:
    """Aggregated report for the entire backtest period."""

    from_date: date
    to_date: date
    total_days: int
    total_candidates: int
    overall_hit_rate: float
    overall_stop_loss_rate: float
    avg_max_return: float
    median_max_return: float
    avg_close_return: float
    hit_rate_by_regime: dict[str, float]
    daily_results: list[DailyBacktestResult] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "fromDate": self.from_date.isoformat(),
            "toDate": self.to_date.isoformat(),
            "totalDays": self.total_days,
            "totalCandidates": self.total_candidates,
            "overallHitRate": round(self.overall_hit_rate, 4),
            "overallStopLossRate": round(self.overall_stop_loss_rate, 4),
            "avgMaxReturn": round(self.avg_max_return, 2),
            "medianMaxReturn": round(self.median_max_return, 2),
            "avgCloseReturn": round(self.avg_close_return, 2),
            "hitRateByRegime": {
                regime: round(rate, 4)
                for regime, rate in self.hit_rate_by_regime.items()
            },
            "dailyResults": [item.as_dict() for item in self.daily_results],
        }


class BacktestDataSource(Protocol):
    def fetch_price_history_for_batch(self, score_date: date, history_limit: int = 25) -> list[PriceHistoryRow]: ...
    def fetch_market_warnings_for_date(self, score_date: date) -> list[WarningRow]: ...
    def fetch_disclosures_for_date(self, score_date: date) -> list[DisclosureRow]: ...
    def fetch_news_for_date(self, score_date: date) -> list[NewsRow]: ...
    def get_next_trading_prices(self, code: str, after_date: date, days: int) -> list[PriceHistoryRow]: ...


def _safe_mean(values: list[float]) -> float:
    return float(mean(values)) if values else 0.0


def _safe_median(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


def evaluate_single_day(
    *,
    data_source: BacktestDataSource,
    score_date: date,
    hit_threshold_pct: float = 4.0,
    stop_loss_pct: float = -5.0,
    forward_days: int = 3,
    config: ScoringConfig | None = None,
) -> DailyBacktestResult:
    """Evaluate candidates for a single day and compare against future prices."""

    price_rows = data_source.fetch_price_history_for_batch(score_date, history_limit=25)
    warning_rows = data_source.fetch_market_warnings_for_date(score_date)
    disclosure_rows = data_source.fetch_disclosures_for_date(score_date)
    fetch_news_rows = getattr(data_source, "fetch_news_for_date", None)
    news_rows = fetch_news_rows(score_date) if callable(fetch_news_rows) else []

    evaluations = evaluate_daily_batch(
        score_date=score_date,
        price_rows=price_rows,
        warning_rows=warning_rows,
        disclosure_rows=disclosure_rows,
        news_rows=news_rows,
    )

    market_regime = "neutral"
    if evaluations:
        market_regime = evaluations[0].snapshot.market_regime

    selected = select_top_candidates(evaluations, market_regime=market_regime)

    candidates: list[CandidateResult] = []
    for evaluation in selected:
        code = evaluation.snapshot.code
        future_prices = data_source.get_next_trading_prices(code, score_date, forward_days)

        if not future_prices:
            continue

        entry_price = future_prices[0].open_price if future_prices else evaluation.snapshot.close
        if entry_price <= 0:
            entry_price = evaluation.snapshot.close

        highs = [row.high_price for row in future_prices]
        lows = [row.low_price for row in future_prices]
        closes = [row.close_price for row in future_prices]

        max_price_3d = max(highs) if highs else entry_price
        min_price_3d = min(lows) if lows else entry_price
        close_price_3d = closes[-1] if closes else entry_price

        max_return_pct = ((max_price_3d / entry_price) - 1) * 100 if entry_price > 0 else 0.0
        min_return_pct = ((min_price_3d / entry_price) - 1) * 100 if entry_price > 0 else 0.0
        close_return_pct = ((close_price_3d / entry_price) - 1) * 100 if entry_price > 0 else 0.0

        hit = max_return_pct >= hit_threshold_pct
        stop_loss_hit = min_return_pct <= stop_loss_pct

        candidates.append(
            CandidateResult(
                score_date=score_date,
                code=code,
                name=evaluation.snapshot.name,
                sector=evaluation.snapshot.sector,
                score=evaluation.score,
                confidence_grade=evaluation.confidence_grade(),
                entry_price=round(entry_price, 2),
                max_price_3d=round(max_price_3d, 2),
                min_price_3d=round(min_price_3d, 2),
                close_price_3d=round(close_price_3d, 2),
                max_return_pct=round(max_return_pct, 2),
                min_return_pct=round(min_return_pct, 2),
                close_return_pct=round(close_return_pct, 2),
                hit=hit,
                stop_loss_hit=stop_loss_hit,
            )
        )

    hit_count = sum(1 for c in candidates if c.hit)
    stop_loss_count = sum(1 for c in candidates if c.stop_loss_hit)
    selected_count = len(candidates)

    return DailyBacktestResult(
        score_date=score_date,
        market_regime=market_regime,
        total_candidates=len(evaluations),
        selected_count=selected_count,
        hit_count=hit_count,
        stop_loss_count=stop_loss_count,
        hit_rate=hit_count / selected_count if selected_count > 0 else 0.0,
        avg_max_return=_safe_mean([c.max_return_pct for c in candidates]),
        avg_close_return=_safe_mean([c.close_return_pct for c in candidates]),
        candidates=candidates,
    )


def run_backtest(
    *,
    data_source: BacktestDataSource,
    from_date: date,
    to_date: date,
    hit_threshold_pct: float = 4.0,
    stop_loss_pct: float = -5.0,
    forward_days: int = 3,
    config: ScoringConfig | None = None,
    skip_weekends: bool = True,
) -> BacktestReport:
    """Run backtest over a date range, replaying daily candidate selection."""

    daily_results: list[DailyBacktestResult] = []
    current = from_date

    while current <= to_date:
        if skip_weekends and current.weekday() >= 5:
            current += timedelta(days=1)
            continue

        try:
            result = evaluate_single_day(
                data_source=data_source,
                score_date=current,
                hit_threshold_pct=hit_threshold_pct,
                stop_loss_pct=stop_loss_pct,
                forward_days=forward_days,
                config=config,
            )
            if result.selected_count > 0:
                daily_results.append(result)
        except Exception:
            pass

        current += timedelta(days=1)

    all_candidates = [c for r in daily_results for c in r.candidates]
    all_max_returns = [c.max_return_pct for c in all_candidates]
    total_hits = sum(1 for c in all_candidates if c.hit)
    total_stops = sum(1 for c in all_candidates if c.stop_loss_hit)
    total_count = len(all_candidates)

    regime_hits: dict[str, list[bool]] = {}
    for result in daily_results:
        regime = result.market_regime
        if regime not in regime_hits:
            regime_hits[regime] = []
        for candidate in result.candidates:
            regime_hits[regime].append(candidate.hit)

    hit_rate_by_regime = {
        regime: sum(hits) / len(hits) if hits else 0.0
        for regime, hits in regime_hits.items()
    }

    return BacktestReport(
        from_date=from_date,
        to_date=to_date,
        total_days=len(daily_results),
        total_candidates=total_count,
        overall_hit_rate=total_hits / total_count if total_count > 0 else 0.0,
        overall_stop_loss_rate=total_stops / total_count if total_count > 0 else 0.0,
        avg_max_return=_safe_mean(all_max_returns),
        median_max_return=_safe_median(all_max_returns),
        avg_close_return=_safe_mean([c.close_return_pct for c in all_candidates]),
        hit_rate_by_regime=hit_rate_by_regime,
        daily_results=daily_results,
    )
