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
    open_price: float
    prev_close: float
    volume: float
    turnover: float
    turnover_ratio_20d: float
    volume_ratio_20d: float
    return_3d_pct: float
    sector_rising_peers: int
    sector_turnover_ratio: float
    has_leading_move: bool
    market_regime: str = "neutral"
    market_breadth_pct: float = 0.0
    market_avg_return_pct: float = 0.0
    market_regime_source: str = "breadth"
    market_index_name: str | None = None
    market_index_close: float = 0.0
    market_index_return_pct: float = 0.0
    market_index_return_5d_pct: float = 0.0
    market_index_return_20d_pct: float = 0.0
    market_index_return_60d_pct: float = 0.0
    market_index_ma20_gap_pct: float = 0.0
    market_index_ma60_gap_pct: float = 0.0
    market_short_trend: str = "neutral"
    market_mid_trend: str = "neutral"
    market_long_trend: str = "neutral"
    warning_level: str | None = None
    is_etf: bool = False
    is_etn: bool = False
    is_preferred: bool = False
    is_spac: bool = False
    is_under_management: bool = False
    is_trading_halted: bool = False
    speculative_theme: bool = False
    rumor_news: bool = False
    candidate_profile: str = "stable"
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
    def is_bullish(self) -> bool:
        return self.close >= self.open_price

    @property
    def body_ratio(self) -> float:
        if self.day_range <= 0:
            return 0.0
        return abs(self.close - self.open_price) / self.day_range

    @property
    def lower_wick_ratio(self) -> float:
        if self.day_range <= 0:
            return 0.0
        return max(0.0, min(1.0, (min(self.open_price, self.close) - self.low) / self.day_range))

    @property
    def gap_up_pct(self) -> float:
        if self.prev_close <= 0:
            return 0.0
        return ((self.low - self.prev_close) / self.prev_close) * 100.0

    @property
    def day_change_pct(self) -> float:
        if self.prev_close <= 0:
            return 0.0
        return ((self.close - self.prev_close) / self.prev_close) * 100.0

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
        payload["is_bullish"] = self.is_bullish
        payload["body_ratio"] = round(self.body_ratio, 4)
        payload["lower_wick_ratio"] = round(self.lower_wick_ratio, 4)
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

    @property
    def day_change_pct(self) -> float:
        if self.snapshot.prev_close <= 0:
            return 0.0
        return round(((self.snapshot.close - self.snapshot.prev_close) / self.snapshot.prev_close) * 100.0, 2)

    def profile_scores_payload(self) -> dict[str, object]:
        risk_score = max(0.0, min(100.0, 100.0 + self.breakdown.risk_penalty * 2.0))
        if self.snapshot.candidate_profile != "trend":
            entry_signal = "ready" if self.score >= 70 else "watch"
            return {
                "scoreMode": "daily_entry",
                "trendScore": None,
                "entryScore": self.score,
                "riskScore": round(risk_score, 2),
                "entrySignal": entry_signal,
                "entrySignalLabel": "진입 후보" if entry_signal == "ready" else "관찰 후보",
            }

        entry_score = 45.0
        day_change = self.snapshot.day_change_pct
        turnover_ratio = self.snapshot.turnover_ratio_20d

        if -2.0 <= day_change <= 5.0:
            entry_score += 15.0
        elif 5.0 < day_change <= 8.0:
            entry_score += 8.0
        elif day_change > 8.0:
            entry_score -= 12.0
        elif day_change < -5.0:
            entry_score -= 8.0

        if 0.8 <= turnover_ratio <= 2.5:
            entry_score += 12.0
        elif 2.5 < turnover_ratio <= 5.0:
            entry_score += 8.0
        elif turnover_ratio > 5.0:
            entry_score += 2.0
        elif turnover_ratio < 0.6:
            entry_score -= 8.0

        if self.snapshot.close_position >= 0.65:
            entry_score += 12.0
        elif self.snapshot.close_position >= 0.45:
            entry_score += 7.0
        elif self.snapshot.close_position < 0.25:
            entry_score -= 8.0

        if self.snapshot.upper_wick_ratio <= 0.25:
            entry_score += 8.0
        elif self.snapshot.upper_wick_ratio >= 0.45:
            entry_score -= 10.0

        entry_score += min(self.breakdown.catalyst_score, 5.0) * 2.0
        if self.snapshot.market_mid_trend == "up":
            entry_score += 5.0
        if self.snapshot.market_long_trend == "up":
            entry_score += 5.0
        if self.snapshot.market_regime in {"bear", "weak"}:
            entry_score -= 10.0
        entry_score += self.breakdown.risk_penalty * 0.8
        entry_score = max(0.0, min(100.0, entry_score))

        if self.score < 55.0:
            entry_signal = "invalid"
            entry_label = "추세 약화"
        elif entry_score >= 72.0:
            entry_signal = "entry_ready"
            entry_label = "진입 가능"
        elif entry_score >= 55.0:
            entry_signal = "watch"
            entry_label = "분할 관찰"
        else:
            entry_signal = "wait_pullback"
            entry_label = "눌림 대기"

        return {
            "scoreMode": "trend_quality",
            "trendScore": self.score,
            "entryScore": round(entry_score, 2),
            "riskScore": round(risk_score, 2),
            "entrySignal": entry_signal,
            "entrySignalLabel": entry_label,
        }

    def confidence_grade(self) -> str:
        """확신도 등급: A(강), B(보통), C(약)."""
        score = self.score
        catalyst = self.breakdown.catalyst_score
        risk = self.breakdown.risk_penalty
        
        # 주도주 여부 확인 (거래대금 300억 이상 & 20일 평균 대비 5배 이상)
        is_leader = self.snapshot.turnover >= 30_000_000_000 and self.snapshot.turnover_ratio_20d >= 5.0

        if score >= 80 and catalyst >= 10 and risk >= -5 and is_leader:
            return "A"
        if score >= 70 and risk >= -10:
            return "B"
        return "C"

    def target_price_payload(self) -> dict[str, float]:
        close = max(self.snapshot.close, 0.0)
        if close <= 0:
            return {
                "conservativeTarget": 0.0,
                "baseTarget": 0.0,
                "aggressiveTarget": 0.0,
                "stopLoss": 0.0,
                "baseUpsidePct": 0.0,
            }

        if self.snapshot.candidate_profile == "trend":
            volatility_pct = max(self.snapshot.intraday_range_pct, 2.0)
            catalyst_bonus = min(self.breakdown.catalyst_score / 5.0, 1.0) * 2.0
            price_structure_bonus = min(self.breakdown.close_strength_score / 30.0, 1.0) * 5.0
            continuity_bonus = min(self.breakdown.continuity_score / 20.0, 1.0) * 4.0
            trend_bonus = 3.0 if self.snapshot.market_mid_trend == "up" else 0.0
            trend_bonus += 3.0 if self.snapshot.market_long_trend == "up" else 0.0
            liquidity_bonus = min(self.breakdown.liquidity_score / 20.0, 1.0) * 3.0
            score_bonus = max(min((self.score - 45.0) / 55.0, 1.0), 0.0) * 8.0
            risk_discount = min(abs(self.breakdown.risk_penalty), 25.0) * 0.15
            is_bear_market = self.snapshot.market_regime in ("bear", "weak")
            min_upside = 7.0 if is_bear_market else 10.0
            max_upside = 16.0 if is_bear_market else 25.0
            base_upside_pct = max(
                min_upside,
                min(
                    max_upside,
                    volatility_pct * 1.4
                    + catalyst_bonus
                    + price_structure_bonus
                    + continuity_bonus
                    + trend_bonus
                    + liquidity_bonus
                    + score_bonus
                    - risk_discount,
                ),
            )
            conservative_upside_pct = max(4.0 if is_bear_market else 6.0, base_upside_pct * 0.6)
            aggressive_upside_pct = min(24.0 if is_bear_market else 38.0, base_upside_pct * 1.45)
            stop_loss_pct = max(7.0, min(16.0, volatility_pct * 1.35 + 4.5))
            return {
                "conservativeTarget": round(close * (1 + conservative_upside_pct / 100.0), 2),
                "baseTarget": round(close * (1 + base_upside_pct / 100.0), 2),
                "aggressiveTarget": round(close * (1 + aggressive_upside_pct / 100.0), 2),
                "stopLoss": round(close * (1 - stop_loss_pct / 100.0), 2),
                "baseUpsidePct": round(base_upside_pct, 2),
            }

        volatility_pct = max(self.snapshot.intraday_range_pct, 1.5)
        momentum_bonus = max(min(self.snapshot.turnover_ratio_20d - 1.0, 3.0), 0.0) * 0.6
        close_strength_bonus = max(self.snapshot.close_position - 0.5, 0.0) * 2.0
        catalyst_bonus = min(self.breakdown.catalyst_score / 20.0, 1.0) * 1.2
        risk_discount = min(abs(self.breakdown.risk_penalty), 20.0) * 0.08

        # Market Regime 반영 (보수적 접근)
        is_bear_market = self.snapshot.market_regime in ("bear", "weak")
        if is_bear_market:
            momentum_bonus *= 0.5
            max_upside = 8.0
        else:
            max_upside = 12.0

        base_upside_pct = max(
            1.5,
            min(max_upside, volatility_pct * 0.55 + momentum_bonus + close_strength_bonus + catalyst_bonus - risk_discount),
        )
        conservative_upside_pct = max(0.8, base_upside_pct * 0.65)
        
        if is_bear_market:
            aggressive_upside_pct = min(12.0, base_upside_pct * 1.2)
            stop_loss_pct = max(1.5, min(5.0, volatility_pct * 0.4))
        else:
            aggressive_upside_pct = min(18.0, base_upside_pct * 1.45)
            stop_loss_pct = max(2.0, min(8.0, volatility_pct * 0.65))

        return {
            "conservativeTarget": round(close * (1 + conservative_upside_pct / 100.0), 2),
            "baseTarget": round(close * (1 + base_upside_pct / 100.0), 2),
            "aggressiveTarget": round(close * (1 + aggressive_upside_pct / 100.0), 2),
            "stopLoss": round(close * (1 - stop_loss_pct / 100.0), 2),
            "baseUpsidePct": round(base_upside_pct, 2),
        }

    def trade_plan_payload(self) -> dict[str, Any]:
        target = self.target_price_payload()
        if self.snapshot.candidate_profile == "trend":
            profile_scores = self.profile_scores_payload()
            stop_loss_pct = 0.0 if self.snapshot.close <= 0 else max(
                0.0,
                ((self.snapshot.close - target["stopLoss"]) / self.snapshot.close) * 100.0,
            )
            max_entry_price = round(self.snapshot.close * 1.03, 2)
            pullback_entry = round(self.snapshot.close * 0.97, 2)
            breakout_trigger = round(max(self.snapshot.high, self.snapshot.close * 1.02), 2)
            return {
                "confidenceGrade": self.confidence_grade(),
                "closeSignal": str(profile_scores["entrySignal"]),
                "closeSignalLabel": str(profile_scores["entrySignalLabel"]),
                "entryMode": "scale_in_trend",
                "nextSessionPlan": "20/60일 추세가 유지되는 동안 분할 진입하고 단기 급등 추격은 피합니다.",
                "entry": {
                    "maxOpenGapPct": 3.0,
                    "maxEntryPrice": max_entry_price,
                    "breakoutTrigger": breakout_trigger,
                    "pullbackEntry": pullback_entry,
                    "openGapRule": "시초가가 전일 종가 대비 +3.0%를 넘으면 1차 진입을 보류하고 눌림을 기다립니다.",
                    "invalidateRule": "종가 기준 60일선 이탈 또는 거래대금 동반 장대 음봉이면 후보에서 제외합니다.",
                    "rules": [
                        "1차 40%, 20일선 지지 확인 후 2차 30%, 신고가 재돌파 시 3차 30% 분할 진입",
                        "종가가 20일선 위에서 유지될 때만 비중을 늘립니다.",
                        "단기 급등일에는 추격 매수보다 3~5거래일 눌림을 기다립니다.",
                    ],
                },
                "exit": {
                    "firstTarget": target["conservativeTarget"],
                    "baseTarget": target["baseTarget"],
                    "aggressiveTarget": target["aggressiveTarget"],
                    "stopLoss": target["stopLoss"],
                    "maxHoldingDays": 60,
                    "timeStopRule": "20거래일 안에 추세 고점 갱신이 없고 20일선 아래에 머물면 비중을 줄입니다.",
                    "rules": [
                        f"종가 기준 -{stop_loss_pct:.1f}% 또는 60일선 이탈 시 전량 또는 절반 청산",
                        "1차 목표 도달 시 30~50% 익절 후 20일선 추세가 유지되면 잔여 보유",
                        "20일선 이탈 후 3거래일 내 회복 실패 시 잔여 물량 청산",
                        "60거래일 내 추세 확장이 없으면 시간 손절을 적용합니다.",
                    ],
                },
                "riskManagement": {
                    "maxConsecutiveLosses": 3,
                    "cooldownRule": "장기 후보 연속 손절 시 신규 추세 진입을 5거래일 쉬어갑니다.",
                    "maxDailyExposure": "총 투자금의 50% 이내",
                    "positionSizing": {
                        "A": "기본 비중의 120%까지 분할 진입",
                        "B": "기본 비중 100%",
                        "C": "기본 비중의 50~60% 또는 관망",
                    },
                },
            }
        max_open_gap_pct = 5.0
        entry_mode = "breakout_confirm"
        close_signal = "watchlist"
        close_signal_label = "관심 후보"
        next_session_plan = "익일 장 초반 가격/거래대금 확인 후 조건부 진입"
        if self.snapshot.candidate_profile == "pullback":
            max_open_gap_pct = 2.5
            entry_mode = "pullback_reversal"
            close_signal = "conditional_entry" if self.score >= 60.0 else "entry_wait"
            close_signal_label = "눌림 확인"
            next_session_plan = "추격 매수보다 전일 저가 이탈 여부와 장 초반 고가/VWAP 회복을 확인합니다."
        elif self.snapshot.day_change_pct >= 15.0 or self.snapshot.turnover_ratio_20d >= 8.0:
            max_open_gap_pct = 3.0
            entry_mode = "pullback_reclaim"
            close_signal = "entry_wait"
            close_signal_label = "매수 보류"
            next_session_plan = "급등 소진 위험이 있어 눌림 후 전일 종가/VWAP 회복 시에만 진입"
        elif self.breakdown.catalyst_score >= 12.0 and self.breakdown.risk_penalty >= -6.0:
            max_open_gap_pct = 6.0
            close_signal = "conditional_entry"
            close_signal_label = "조건부 진입 후보"
            next_session_plan = "촉매가 강해 시초 갭 과열이 없고 거래대금이 이어질 때만 진입"
        elif self.breakdown.risk_penalty <= -10.0:
            max_open_gap_pct = min(max_open_gap_pct, 3.0)
            entry_mode = "risk_confirm"
            close_signal = "entry_wait"
            close_signal_label = "매수 보류"
            next_session_plan = "리스크 감점이 커서 익일 회복 신호 확인 전까지 진입 보류"

        max_entry_price = round(self.snapshot.close * (1 + max_open_gap_pct / 100.0), 2)
        breakout_trigger = round(max(self.snapshot.high, self.snapshot.close * 1.005), 2)
        pullback_entry = round(self.snapshot.close * 0.985, 2)

        return {
            "confidenceGrade": self.confidence_grade(),
            "closeSignal": close_signal,
            "closeSignalLabel": close_signal_label,
            "entryMode": entry_mode,
            "nextSessionPlan": next_session_plan,
            "entry": {
                "maxOpenGapPct": max_open_gap_pct,
                "maxEntryPrice": max_entry_price,
                "breakoutTrigger": breakout_trigger,
                "pullbackEntry": pullback_entry,
                "openGapRule": f"익일 시초가가 전일 종가 대비 +{max_open_gap_pct:.1f}%를 넘으면 진입 보류",
                "invalidateRule": "전일 저가 이탈 또는 장 초반 거래대금 둔화 시 후보 제외",
                "rules": [
                    "장 시작 직후 5~15분 대기 (Opening Range Breakout 확인)",
                    "익일 시초가가 maxEntryPrice를 넘으면 추격 매수 보류",
                    "전일 고가 돌파 또는 장중 VWAP 회복 확인 후 진입",
                    "장 초반 거래대금이 전일 대비 약하면 후보에서 제외",
                ],
            },
            "exit": {
                "firstTarget": target["conservativeTarget"],
                "baseTarget": target["baseTarget"],
                "aggressiveTarget": target["aggressiveTarget"],
                "stopLoss": target["stopLoss"],
                "maxHoldingDays": 3,
                "timeStopRule": "3거래일 안에 기준 목표가의 절반 이상 움직이지 못하면 현금화",
                "rules": [
                    "전일 저가 또는 stopLoss 이탈 시 전량 손절",
                    "목표가 도달 시 50% 1차 익절 (비중 축소)",
                    "나머지 물량은 5일선 이탈 또는 고점 대비 3% 하락 시 트레일링 스탑",
                    "3거래일 안에 +2% 이상 움직이지 못하면 시간 손절",
                ],
            },
            "riskManagement": {
                "maxConsecutiveLosses": 3,
                "cooldownRule": "3연속 손절 시 다음 1거래일 진입 보류",
                "maxDailyExposure": "총 투자금의 50% 이내",
                "positionSizing": {
                    "A": "기본 비중의 120% (시장 주도주 파악)",
                    "B": "기본 비중의 100%",
                    "C": "기본 비중의 60% 또는 관망 (단순 후발주)",
                },
            },
        }

    def to_candidate_payload(self, rank: int) -> dict[str, Any]:
        target = self.target_price_payload()
        return {
            "rank": rank,
            "code": self.snapshot.code,
            "name": self.snapshot.name,
            "score": self.score,
            "confidenceGrade": self.confidence_grade(),
            "candidateProfile": self.snapshot.candidate_profile,
            "profileScores": self.profile_scores_payload(),
            "sector": self.snapshot.sector,
            "close": self.snapshot.close,
            "prevClose": self.snapshot.prev_close,
            "dayChangePct": self.day_change_pct,
            "targetPrice": target["baseTarget"],
            "targetUpsidePct": target["baseUpsidePct"],
            "tradePlan": self.trade_plan_payload(),
            "reasons": self.reasons[:3],
            "riskFlags": self.risk_flags[:2],
            "newsLinks": [asdict(link) for link in self.snapshot.news_links],
            "disclosureLinks": [asdict(link) for link in self.snapshot.disclosure_links],
            "marketRegime": self.snapshot.market_regime,
            "marketRegimeSource": self.snapshot.market_regime_source,
            "marketIndexName": self.snapshot.market_index_name,
            "marketIndexClose": round(self.snapshot.market_index_close, 2),
            "marketIndexReturnPct": round(self.snapshot.market_index_return_pct, 2),
            "marketIndexReturn5dPct": round(self.snapshot.market_index_return_5d_pct, 2),
            "marketIndexReturn20dPct": round(self.snapshot.market_index_return_20d_pct, 2),
            "marketIndexReturn60dPct": round(self.snapshot.market_index_return_60d_pct, 2),
            "marketIndexMa20GapPct": round(self.snapshot.market_index_ma20_gap_pct, 2),
            "marketIndexMa60GapPct": round(self.snapshot.market_index_ma60_gap_pct, 2),
            "marketShortTrend": self.snapshot.market_short_trend,
            "marketMidTrend": self.snapshot.market_mid_trend,
            "marketLongTrend": self.snapshot.market_long_trend,
        }

    def to_search_payload(self) -> dict[str, Any]:
        target = self.target_price_payload()
        return {
            "code": self.snapshot.code,
            "name": self.snapshot.name,
            "score": self.score,
            "confidenceGrade": self.confidence_grade(),
            "candidateProfile": self.snapshot.candidate_profile,
            "profileScores": self.profile_scores_payload(),
            "sector": self.snapshot.sector,
            "close": self.snapshot.close,
            "prevClose": self.snapshot.prev_close,
            "dayChangePct": self.day_change_pct,
            "targetPrice": target["baseTarget"],
            "targetUpsidePct": target["baseUpsidePct"],
            "tradePlan": self.trade_plan_payload(),
            "turnoverRatio20d": round(self.snapshot.turnover_ratio_20d, 2),
            "volumeRatio20d": round(self.snapshot.volume_ratio_20d, 2),
            "return3dPct": round(self.snapshot.return_3d_pct, 2),
            "reasons": self.reasons[:3],
            "riskFlags": self.risk_flags[:2],
            "marketRegime": self.snapshot.market_regime,
            "marketRegimeSource": self.snapshot.market_regime_source,
            "marketIndexName": self.snapshot.market_index_name,
            "marketIndexClose": round(self.snapshot.market_index_close, 2),
            "marketIndexReturnPct": round(self.snapshot.market_index_return_pct, 2),
            "marketIndexReturn5dPct": round(self.snapshot.market_index_return_5d_pct, 2),
            "marketIndexReturn20dPct": round(self.snapshot.market_index_return_20d_pct, 2),
            "marketIndexReturn60dPct": round(self.snapshot.market_index_return_60d_pct, 2),
            "marketIndexMa20GapPct": round(self.snapshot.market_index_ma20_gap_pct, 2),
            "marketIndexMa60GapPct": round(self.snapshot.market_index_ma60_gap_pct, 2),
            "marketShortTrend": self.snapshot.market_short_trend,
            "marketMidTrend": self.snapshot.market_mid_trend,
            "marketLongTrend": self.snapshot.market_long_trend,
        }

    def to_signal_summary_payload(self) -> dict[str, Any]:
        return {
            "componentScores": self.breakdown.as_dict(),
            "profileScores": self.profile_scores_payload(),
            "rawFeatures": self.snapshot.raw_features(),
            "priceStats": {
                "close": self.snapshot.close,
                "high": self.snapshot.high,
                "low": self.snapshot.low,
                "prevClose": self.snapshot.prev_close,
                "dayChangePct": round(self.snapshot.day_change_pct, 4),
                "closePosition": round(self.snapshot.close_position, 4),
                "upperWickRatio": round(self.snapshot.upper_wick_ratio, 4),
                "gapUpPct": round(self.snapshot.gap_up_pct, 4),
                "intradayRangePct": round(self.snapshot.intraday_range_pct, 4),
            },
            "targetPrice": self.target_price_payload(),
            "tradePlan": self.trade_plan_payload(),
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
