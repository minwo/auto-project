from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(slots=True)
class CatalystItem:
    kind: str
    title: str
    url: str
    trust_score: float = 1.0


@dataclass(slots=True)
class NewsLink:
    title: str
    url: str


@dataclass(slots=True)
class DisclosureLink:
    title: str
    url: str


@dataclass(slots=True)
class StockSnapshot:
    date: date
    code: str
    name: str
    market: str
    sector: str
    is_common_stock: bool
    listed_days: int
    avg_turnover_20d: float
    avg_volume_20d: float
    close: float
    high: float
    low: float
    prev_close: float
    volume: float
    turnover: float
    turnover_ratio_20d: float
    volume_ratio_20d: float
    return_3d_pct: float
    sector_rising_peers: int
    sector_turnover_ratio: float
    has_leading_move: bool
    warning_level: str | None = None
    is_etf: bool = False
    is_etn: bool = False
    is_preferred: bool = False
    is_spac: bool = False
    is_under_management: bool = False
    is_trading_halted: bool = False
    speculative_theme: bool = False
    rumor_news: bool = False
    catalysts: list[CatalystItem] = field(default_factory=list)
    news_links: list[NewsLink] = field(default_factory=list)
    disclosure_links: list[DisclosureLink] = field(default_factory=list)

    @property
    def day_range(self) -> float:
        return max(self.high - self.low, 0.0)

    @property
    def close_position(self) -> float:
        if self.day_range <= 0:
            return 0.5
        return max(0.0, min(1.0, (self.close - self.low) / self.day_range))

    @property
    def upper_wick_ratio(self) -> float:
        if self.day_range <= 0:
            return 0.0
        wick = max(self.high - self.close, 0.0)
        return max(0.0, min(1.0, wick / self.day_range))

    @property
    def gap_up_pct(self) -> float:
        if self.prev_close <= 0:
            return 0.0
        return ((self.low - self.prev_close) / self.prev_close) * 100.0

    @property
    def intraday_range_pct(self) -> float:
        if self.prev_close <= 0:
            return 0.0
        return (self.day_range / self.prev_close) * 100.0

    def raw_features(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["close_position"] = round(self.close_position, 4)
        payload["upper_wick_ratio"] = round(self.upper_wick_ratio, 4)
        payload["gap_up_pct"] = round(self.gap_up_pct, 4)
        payload["intraday_range_pct"] = round(self.intraday_range_pct, 4)
        return payload


@dataclass(slots=True)
class ScoreBreakdown:
    liquidity_score: float
    close_strength_score: float
    catalyst_score: float
    sector_score: float
    continuity_score: float
    risk_penalty: float

    @property
    def total_score(self) -> float:
        raw_total = (
            self.liquidity_score
            + self.close_strength_score
            + self.catalyst_score
            + self.sector_score
            + self.continuity_score
            + self.risk_penalty
        )
        return max(0.0, min(100.0, raw_total))

    def as_dict(self) -> dict[str, float]:
        return {
            "liquidityScore": round(self.liquidity_score, 2),
            "closeStrengthScore": round(self.close_strength_score, 2),
            "catalystScore": round(self.catalyst_score, 2),
            "sectorScore": round(self.sector_score, 2),
            "continuityScore": round(self.continuity_score, 2),
            "riskPenalty": round(self.risk_penalty, 2),
            "totalScore": round(self.total_score, 2),
        }


@dataclass(slots=True)
class CandidateEvaluation:
    date: date
    generated_at: datetime
    snapshot: StockSnapshot
    breakdown: ScoreBreakdown
    reasons: list[str]
    risk_flags: list[str]

    @property
    def score(self) -> float:
        return round(self.breakdown.total_score, 2)

    def to_candidate_payload(self, rank: int) -> dict[str, Any]:
        return {
            "rank": rank,
            "code": self.snapshot.code,
            "name": self.snapshot.name,
            "score": self.score,
            "sector": self.snapshot.sector,
            "reasons": self.reasons[:3],
            "riskFlags": self.risk_flags[:2],
            "newsLinks": [asdict(link) for link in self.snapshot.news_links],
            "disclosureLinks": [asdict(link) for link in self.snapshot.disclosure_links],
        }

    def to_search_payload(self) -> dict[str, Any]:
        return {
            "code": self.snapshot.code,
            "name": self.snapshot.name,
            "score": self.score,
            "sector": self.snapshot.sector,
            "turnoverRatio20d": round(self.snapshot.turnover_ratio_20d, 2),
            "volumeRatio20d": round(self.snapshot.volume_ratio_20d, 2),
            "return3dPct": round(self.snapshot.return_3d_pct, 2),
            "reasons": self.reasons[:3],
            "riskFlags": self.risk_flags[:2],
        }

    def to_signal_summary_payload(self) -> dict[str, Any]:
        return {
            "componentScores": self.breakdown.as_dict(),
            "rawFeatures": self.snapshot.raw_features(),
            "priceStats": {
                "close": self.snapshot.close,
                "high": self.snapshot.high,
                "low": self.snapshot.low,
                "prevClose": self.snapshot.prev_close,
                "closePosition": round(self.snapshot.close_position, 4),
                "upperWickRatio": round(self.snapshot.upper_wick_ratio, 4),
                "gapUpPct": round(self.snapshot.gap_up_pct, 4),
                "intradayRangePct": round(self.snapshot.intraday_range_pct, 4),
            },
            "liquidityStats": {
                "turnover": self.snapshot.turnover,
                "avgTurnover20d": self.snapshot.avg_turnover_20d,
                "turnoverRatio20d": self.snapshot.turnover_ratio_20d,
                "volume": self.snapshot.volume,
                "avgVolume20d": self.snapshot.avg_volume_20d,
                "volumeRatio20d": self.snapshot.volume_ratio_20d,
            },
            "sectorStats": {
                "sector": self.snapshot.sector,
                "risingPeers": self.snapshot.sector_rising_peers,
                "sectorTurnoverRatio": self.snapshot.sector_turnover_ratio,
            },
            "catalystSummary": {
                "count": len(self.snapshot.catalysts),
                "items": [asdict(item) for item in self.snapshot.catalysts],
            },
            "reasons": self.reasons,
            "riskFlags": self.risk_flags,
        }
