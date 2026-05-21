from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from app.domain import CandidateEvaluation


@dataclass(slots=True)
class BacktestSummary:
    top10_hit_rate: float
    median_max_return: float
    false_positive_rate: float
    sector_concentration: float
    warning_hit_rate: float

    def as_dict(self) -> dict[str, float]:
        return {
            "top10HitRate": self.top10_hit_rate,
            "medianMaxReturn": self.median_max_return,
            "falsePositiveRate": self.false_positive_rate,
            "sectorConcentration": self.sector_concentration,
            "warningHitRate": self.warning_hit_rate,
        }


@dataclass(slots=True)
class DailyTopPick:
    pick_date: date
    recommendation_end_date: date | None
    code: str
    name: str
    sector: str
    score: float
    base_close: float
    latest_date: date
    latest_close: float
    change_pct: float
    reasons: list[str]
    risk_flags: list[str]
    market_regime: str = "neutral"
    market_regime_source: str = "breadth"
    market_index_name: str | None = None
    market_index_close: float = 0.0
    market_index_return_pct: float = 0.0
    market_index_return_5d_pct: float = 0.0
    market_index_return_20d_pct: float = 0.0
    market_index_return_60d_pct: float = 0.0
    market_short_trend: str = "neutral"
    market_mid_trend: str = "neutral"
    market_long_trend: str = "neutral"

    def as_dict(self) -> dict[str, object]:
        return {
            "pickDate": self.pick_date.isoformat(),
            "recommendationStartDate": self.pick_date.isoformat(),
            "recommendationEndDate": (self.recommendation_end_date or self.pick_date).isoformat(),
            "code": self.code,
            "name": self.name,
            "sector": self.sector,
            "score": round(self.score, 2),
            "baseClose": self.base_close,
            "latestDate": self.latest_date.isoformat(),
            "latestClose": self.latest_close,
            "changePct": round(self.change_pct, 2),
            "reasons": self.reasons[:3],
            "riskFlags": self.risk_flags[:2],
            "marketRegime": self.market_regime,
            "marketRegimeSource": self.market_regime_source,
            "marketIndexName": self.market_index_name,
            "marketIndexClose": round(self.market_index_close, 2),
            "marketIndexReturnPct": round(self.market_index_return_pct, 2),
            "marketIndexReturn5dPct": round(self.market_index_return_5d_pct, 2),
            "marketIndexReturn20dPct": round(self.market_index_return_20d_pct, 2),
            "marketIndexReturn60dPct": round(self.market_index_return_60d_pct, 2),
            "marketShortTrend": self.market_short_trend,
            "marketMidTrend": self.market_mid_trend,
            "marketLongTrend": self.market_long_trend,
        }


@dataclass(slots=True)
class PriceChartPoint:
    trade_date: date
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float

    def as_dict(self) -> dict[str, object]:
        return {
            "date": self.trade_date.isoformat(),
            "open": self.open_price,
            "high": self.high_price,
            "low": self.low_price,
            "close": self.close_price,
            "volume": self.volume,
        }


class CandidateRepository:
    def __init__(self) -> None:
        self._daily_scores: dict[date, list[CandidateEvaluation]] = {}
        self._backtests: dict[tuple[date, date], BacktestSummary] = {}
        self._daily_top_picks: dict[date, DailyTopPick] = {}

    def upsert_daily_scores(self, score_date: date, evaluations: list[CandidateEvaluation]) -> None:
        ordered = sorted(evaluations, key=lambda item: item.score, reverse=True)
        self._daily_scores[score_date] = ordered

    def replace_daily_scores(self, score_date: date, evaluations: list[CandidateEvaluation]) -> None:
        self.upsert_daily_scores(score_date, evaluations)
        if not evaluations:
            self._daily_scores.pop(score_date, None)
            self._daily_top_picks.pop(score_date, None)

    def get_daily_scores(self, score_date: date) -> list[CandidateEvaluation]:
        return list(self._daily_scores.get(score_date, []))

    def latest_score_date(self) -> date | None:
        if not self._daily_scores:
            return None
        return max(self._daily_scores.keys())

    def available_trade_dates(self, limit: int = 260) -> list[date]:
        return sorted(self._daily_scores.keys(), reverse=True)[:limit]

    def search_daily_scores(self, score_date: date, query: str = "", limit: int = 30) -> list[CandidateEvaluation]:
        evaluations = self.get_daily_scores(score_date)
        normalized = query.strip().lower()
        if not normalized:
            return evaluations[:limit]

        matched: list[CandidateEvaluation] = []
        for evaluation in evaluations:
            haystacks = (
                evaluation.snapshot.code.lower(),
                evaluation.snapshot.name.lower(),
                evaluation.snapshot.sector.lower(),
                " ".join(evaluation.reasons).lower(),
            )
            if any(normalized in value for value in haystacks):
                matched.append(evaluation)
            if len(matched) == limit:
                break
        return matched

    def get_signal_summary(self, code: str, score_date: date) -> CandidateEvaluation | None:
        for evaluation in self._daily_scores.get(score_date, []):
            if evaluation.snapshot.code == code:
                return evaluation
        return None

    def set_backtest_summary(self, start: date, end: date, summary: BacktestSummary) -> None:
        self._backtests[(start, end)] = summary

    def get_backtest_summary(self, start: date, end: date) -> BacktestSummary | None:
        return self._backtests.get((start, end))

    def refresh_daily_top_picks(self, as_of: date, retention_days: int = 92) -> list[DailyTopPick]:
        cutoff = as_of - timedelta(days=retention_days)
        rebuilt: dict[date, DailyTopPick] = {}
        active_by_code: dict[str, DailyTopPick] = {}

        for score_date in sorted(self._daily_scores.keys()):
            evaluations = self._daily_scores[score_date]
            if score_date < cutoff or not evaluations:
                continue
            inserted_for_day = False
            for top in sorted(evaluations, key=lambda item: (-item.score, item.snapshot.code)):
                snapshot = top.snapshot
                existing = active_by_code.get(snapshot.code)
                if existing is not None:
                    latest_close = snapshot.close
                    existing.latest_date = score_date
                    existing.recommendation_end_date = score_date
                    existing.latest_close = latest_close
                    existing.change_pct = 0.0 if existing.base_close <= 0 else (
                        (latest_close - existing.base_close) / existing.base_close
                    ) * 100.0
                    continue

                if inserted_for_day:
                    continue

                pick = DailyTopPick(
                    pick_date=score_date,
                    recommendation_end_date=score_date,
                    code=snapshot.code,
                    name=snapshot.name,
                    sector=snapshot.sector,
                    score=top.score,
                    base_close=snapshot.close,
                    latest_date=score_date,
                    latest_close=snapshot.close,
                    change_pct=0.0,
                    reasons=top.reasons,
                    risk_flags=top.risk_flags,
                    market_regime=snapshot.market_regime,
                    market_regime_source=snapshot.market_regime_source,
                    market_index_name=snapshot.market_index_name,
                    market_index_close=snapshot.market_index_close,
                    market_index_return_pct=snapshot.market_index_return_pct,
                    market_index_return_5d_pct=snapshot.market_index_return_5d_pct,
                    market_index_return_20d_pct=snapshot.market_index_return_20d_pct,
                    market_index_return_60d_pct=snapshot.market_index_return_60d_pct,
                    market_short_trend=snapshot.market_short_trend,
                    market_mid_trend=snapshot.market_mid_trend,
                    market_long_trend=snapshot.market_long_trend,
                )
                rebuilt[score_date] = pick
                active_by_code[snapshot.code] = pick
                inserted_for_day = True

        self._daily_top_picks = rebuilt
        return self.get_daily_top_picks(as_of, retention_days)

    def get_daily_top_picks(self, as_of: date, retention_days: int = 92) -> list[DailyTopPick]:
        cutoff = as_of - timedelta(days=retention_days)
        return [
            self._daily_top_picks[pick_date]
            for pick_date in sorted(self._daily_top_picks.keys(), reverse=True)
            if pick_date >= cutoff
        ]

    def get_price_chart(self, code: str, to_date: date, limit: int = 60) -> list[PriceChartPoint]:
        points: list[PriceChartPoint] = []
        for score_date in sorted(self._daily_scores.keys()):
            if score_date > to_date:
                continue
            evaluation = self.get_signal_summary(code=code, score_date=score_date)
            if not evaluation:
                continue
            snapshot = evaluation.snapshot
            points.append(
                PriceChartPoint(
                    trade_date=score_date,
                    open_price=snapshot.open_price,
                    high_price=snapshot.high,
                    low_price=snapshot.low,
                    close_price=snapshot.close,
                    volume=snapshot.volume,
                )
            )
        return points[-limit:]


class UnavailableRepository(CandidateRepository):
    def __init__(self, error_message: str, database_configured: bool = False) -> None:
        super().__init__()
        self.error_message = error_message
        self.database_configured = database_configured


def select_top_candidates(
    evaluations: list[CandidateEvaluation],
    min_score: float = 60.0,
    max_per_sector: int = 3,
    limit: int = 10,
    market_regime: str = "neutral",
    separate_profiles: bool = False,
    carry_forward_codes: set[str] | None = None,
    trend_keep_limit: int = 6,
) -> list[CandidateEvaluation]:
    regime_min_score = {
        "bear": max(min_score, 72.0),
        "weak": max(min_score, 66.0),
        "neutral": min_score,
        "strong": min_score,
    }
    effective_min = regime_min_score.get(market_regime, min_score)

    selected: list[CandidateEvaluation] = []
    per_sector: dict[tuple[str, str], int] = defaultdict(int)
    selected_codes: set[str] = set()

    def profile_min_score(evaluation: CandidateEvaluation) -> float:
        profile_key = evaluation.snapshot.candidate_profile if separate_profiles else "all"
        if profile_key == "trend":
            return max(45.0, effective_min - 15.0)
        return effective_min

    def append_if_allowed(evaluation: CandidateEvaluation) -> bool:
        if len(selected) >= limit:
            return False
        if evaluation.score < profile_min_score(evaluation):
            return False
        if evaluation.snapshot.code in selected_codes:
            return False
        profile_key = evaluation.snapshot.candidate_profile if separate_profiles else "all"
        sector_key = (profile_key, evaluation.snapshot.sector)
        if per_sector[sector_key] >= max_per_sector:
            return False
        selected.append(evaluation)
        selected_codes.add(evaluation.snapshot.code)
        per_sector[sector_key] += 1
        return True

    if separate_profiles and carry_forward_codes:
        kept = 0
        retained_trends = [
            evaluation
            for evaluation in evaluations
            if evaluation.snapshot.candidate_profile == "trend"
            and evaluation.snapshot.code in carry_forward_codes
        ]
        for evaluation in sorted(retained_trends, key=lambda item: item.score, reverse=True):
            if append_if_allowed(evaluation):
                kept += 1
            if kept >= trend_keep_limit or len(selected) == limit:
                break

    for evaluation in sorted(evaluations, key=lambda item: item.score, reverse=True):
        append_if_allowed(evaluation)
        if len(selected) == limit:
            break

    return selected
