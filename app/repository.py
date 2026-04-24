from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

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


class CandidateRepository:
    def __init__(self) -> None:
        self._daily_scores: dict[date, list[CandidateEvaluation]] = {}
        self._backtests: dict[tuple[date, date], BacktestSummary] = {}

    def upsert_daily_scores(self, score_date: date, evaluations: list[CandidateEvaluation]) -> None:
        ordered = sorted(evaluations, key=lambda item: item.score, reverse=True)
        self._daily_scores[score_date] = ordered

    def get_daily_scores(self, score_date: date) -> list[CandidateEvaluation]:
        return list(self._daily_scores.get(score_date, []))

    def latest_score_date(self) -> date | None:
        if not self._daily_scores:
            return None
        return max(self._daily_scores.keys())

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
) -> list[CandidateEvaluation]:
    selected: list[CandidateEvaluation] = []
    per_sector: dict[str, int] = defaultdict(int)

    for evaluation in sorted(evaluations, key=lambda item: item.score, reverse=True):
        if evaluation.score < min_score:
            continue
        sector = evaluation.snapshot.sector
        if per_sector[sector] >= max_per_sector:
            continue
        selected.append(evaluation)
        per_sector[sector] += 1
        if len(selected) == limit:
            break

    return selected
