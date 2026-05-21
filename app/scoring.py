from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain import CandidateEvaluation, ScoreBreakdown, StockSnapshot


@dataclass(slots=True)
class ScoringConfig:
    """Centralized scoring weights for tuning via backtest."""

    # Liquidity
    liquidity_turnover_mult: float = 12.0
    liquidity_volume_mult: float = 7.0
    liquidity_expansion_bonus: float = 2.0
    liquidity_expansion_turnover_threshold: float = 2.0
    liquidity_expansion_volume_threshold: float = 1.8
    liquidity_exhaustion_penalty: float = 2.0
    liquidity_exhaustion_threshold: float = 10.0

    # Close strength
    close_base_mult: float = 16.0
    close_base_offset: float = 4.0
    close_wick_penalty: float = 6.0
    close_wick_threshold: float = 0.35
    close_overheat_penalty: float = 2.0
    close_overheat_threshold: float = 15.0
    close_bullish_bonus: float = 2.0
    close_body_bonus_mult: float = 2.0

    # Catalyst
    catalyst_kind_weights: dict[str, float] = field(default_factory=lambda: {
        "disclosure": 6.0,
        "earnings": 10.0,
        "contract": 10.0,
        "buyback": 8.0,
        "dividend": 7.0,
        "approval": 8.0,
        "policy": 6.0,
        "capital_event": 6.0,
        "corporate_action": 7.0,
        "capex": 7.0,
        "industry": 5.0,
        "news": 4.0,
    })
    catalyst_default_weight: float = 3.0

    # Sector
    sector_peers_mult: float = 2.5
    sector_turnover_mult: float = 5.0
    sector_unclassified_peers_mult: float = 1.2
    sector_unclassified_turnover_mult: float = 2.0

    # Continuity
    continuity_optimal_low: float = 1.0
    continuity_optimal_high: float = 9.0
    continuity_moderate_high: float = 15.0
    continuity_max_high: float = 22.0
    continuity_lead_bonus: float = 3.0

    # Risk penalty
    risk_bear_penalty: float = 12.0
    risk_weak_penalty: float = 6.0
    risk_strong_bonus: float = 3.0
    risk_max_penalty: float = -35.0


NEGATIVE_CATALYST_KINDS = {
    "capital_reduction",
    "dilution",
    "debt_financing",
    "trading_risk",
    "management_risk",
}

DEFAULT_CONFIG = ScoringConfig()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def is_eligible(snapshot: StockSnapshot) -> tuple[bool, list[str]]:
    exclusions: list[str] = []

    if snapshot.market not in {"KOSPI", "KOSDAQ"}:
        exclusions.append("unsupported_market")
    if not snapshot.is_common_stock:
        exclusions.append("not_common_stock")
    if snapshot.is_etf or snapshot.is_etn:
        exclusions.append("fund_like_security")
    if snapshot.is_preferred:
        exclusions.append("preferred_stock")
    if snapshot.is_spac:
        exclusions.append("spac")
    if snapshot.is_under_management:
        exclusions.append("under_management")
    if snapshot.is_trading_halted:
        exclusions.append("trading_halt")
    if snapshot.listed_days < 60:
        exclusions.append("listed_under_60_days")
    if snapshot.avg_turnover_20d < 1_000_000_000:
        exclusions.append("avg_turnover_under_1b_krw")

    return (len(exclusions) == 0, exclusions)


def _liquidity_score(snapshot: StockSnapshot, cfg: ScoringConfig) -> tuple[float, list[str]]:
    turnover_points = _clamp((snapshot.turnover_ratio_20d - 1.0) * cfg.liquidity_turnover_mult, 0.0, 16.0)
    volume_points = _clamp((snapshot.volume_ratio_20d - 1.0) * cfg.liquidity_volume_mult, 0.0, 7.0)
    expansion_bonus = cfg.liquidity_expansion_bonus if (
        snapshot.turnover_ratio_20d >= cfg.liquidity_expansion_turnover_threshold
        and snapshot.volume_ratio_20d >= cfg.liquidity_expansion_volume_threshold
    ) else 0.0
    exhaustion_penalty = cfg.liquidity_exhaustion_penalty if snapshot.turnover_ratio_20d >= cfg.liquidity_exhaustion_threshold else 0.0
    score = _clamp(turnover_points + volume_points + expansion_bonus - exhaustion_penalty, 0.0, 25.0)

    reasons: list[str] = []
    if snapshot.turnover_ratio_20d >= cfg.liquidity_expansion_turnover_threshold:
        reasons.append("최근 20일 대비 거래대금이 크게 확대됐습니다.")
    if snapshot.volume_ratio_20d >= cfg.liquidity_expansion_volume_threshold:
        reasons.append("평균 대비 거래량이 유의미하게 증가했습니다.")
    if snapshot.turnover_ratio_20d >= cfg.liquidity_exhaustion_threshold:
        reasons.append("거래대금이 과도하게 급증해 단기 소진 가능성도 함께 확인됩니다.")
    return score, reasons


def _close_strength_score(snapshot: StockSnapshot, cfg: ScoringConfig) -> tuple[float, list[str]]:
    base = snapshot.close_position * cfg.close_base_mult
    wick_penalty = cfg.close_wick_penalty if snapshot.upper_wick_ratio >= cfg.close_wick_threshold else 0.0
    overheat_penalty = cfg.close_overheat_penalty if snapshot.day_change_pct >= cfg.close_overheat_threshold else 0.0
    bullish_bonus = cfg.close_bullish_bonus if snapshot.is_bullish else 0.0
    body_bonus = snapshot.body_ratio * cfg.close_body_bonus_mult if snapshot.is_bullish else 0.0
    score = _clamp(base + cfg.close_base_offset - wick_penalty - overheat_penalty + bullish_bonus + body_bonus, 0.0, 20.0)

    reasons: list[str] = []
    if snapshot.close_position >= 0.75:
        reasons.append("종가가 당일 고가권에 가까워 마감 강도가 좋습니다.")
    if snapshot.upper_wick_ratio <= 0.2:
        reasons.append("윗꼬리가 짧아 매물 소화 흐름이 양호합니다.")
    if snapshot.is_bullish and snapshot.body_ratio >= 0.5:
        reasons.append("양봉 몸통이 크고 매수 의지가 강합니다.")
    if snapshot.day_change_pct >= cfg.close_overheat_threshold:
        reasons.append("당일 상승률이 커서 익일 추격 매수 조건은 보수적으로 봐야 합니다.")
    return score, reasons


def _catalyst_score(snapshot: StockSnapshot, cfg: ScoringConfig) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    seen_titles: set[str] = set()

    for catalyst in snapshot.catalysts:
        if catalyst.kind in NEGATIVE_CATALYST_KINDS:
            if catalyst.title not in seen_titles:
                reasons.append(f"주의 공시 확인: {catalyst.title}")
                seen_titles.add(catalyst.title)
            continue

        score += cfg.catalyst_kind_weights.get(catalyst.kind, cfg.catalyst_default_weight) * catalyst.trust_score
        if catalyst.title not in seen_titles:
            reasons.append(f"촉매 확인: {catalyst.title}")
            seen_titles.add(catalyst.title)

    return _clamp(score, 0.0, 20.0), reasons


def _sector_score(snapshot: StockSnapshot, cfg: ScoringConfig) -> tuple[float, list[str]]:
    if snapshot.sector == "Unclassified":
        peers_points = _clamp(snapshot.sector_rising_peers * cfg.sector_unclassified_peers_mult, 0.0, 4.0)
        turnover_points = _clamp((snapshot.sector_turnover_ratio - 1.0) * cfg.sector_unclassified_turnover_mult, 0.0, 2.0)
    else:
        peers_points = _clamp(snapshot.sector_rising_peers * cfg.sector_peers_mult, 0.0, 10.0)
        turnover_points = _clamp((snapshot.sector_turnover_ratio - 1.0) * cfg.sector_turnover_mult, 0.0, 5.0)
    score = _clamp(peers_points + turnover_points, 0.0, 15.0)

    reasons: list[str] = []
    if snapshot.sector == "Unclassified" and score > 0:
        reasons.append("업종 분류가 임시 상태라 섹터 점수는 보수적으로 반영했습니다.")
    elif snapshot.sector_rising_peers >= 3:
        reasons.append("동일 섹터 내 동반 상승 종목이 충분히 확인됩니다.")
    if snapshot.sector != "Unclassified" and snapshot.sector_turnover_ratio >= 1.4:
        reasons.append("섹터 전체 거래대금도 함께 유입되고 있습니다.")
    return score, reasons


def _continuity_score(snapshot: StockSnapshot, cfg: ScoringConfig) -> tuple[float, list[str]]:
    move_score = 0.0
    if cfg.continuity_optimal_low <= snapshot.return_3d_pct <= cfg.continuity_optimal_high:
        move_score = 7.0
    elif cfg.continuity_optimal_high < snapshot.return_3d_pct <= cfg.continuity_moderate_high:
        move_score = 5.0
    elif cfg.continuity_moderate_high < snapshot.return_3d_pct <= cfg.continuity_max_high:
        move_score = 2.0

    lead_bonus = cfg.continuity_lead_bonus if snapshot.has_leading_move and snapshot.return_3d_pct <= cfg.continuity_moderate_high else 0.0
    score = _clamp(move_score + lead_bonus, 0.0, 10.0)

    reasons: list[str] = []
    if move_score >= 5.0:
        reasons.append("최근 3거래일 추세 연속성이 유지되고 있습니다.")
    if lead_bonus > 0:
        reasons.append("급등 전 선행 움직임이 포착됐습니다.")
    if snapshot.return_3d_pct > cfg.continuity_max_high:
        reasons.append("최근 3거래일 상승률이 높아 추세 연속성 점수는 제한했습니다.")
    return score, reasons


def _risk_penalty(snapshot: StockSnapshot, cfg: ScoringConfig) -> tuple[float, list[str]]:
    penalty = 0.0
    flags: list[str] = []

    warning_penalties = {
        "attention": -8.0,
        "warning": -15.0,
        "danger": -20.0,
    }

    if snapshot.warning_level:
        warning_key = snapshot.warning_level.lower()
        applied = warning_penalties.get(warning_key, 0.0)
        if applied:
            penalty += applied
            flags.append(f"시장경보 상태: {snapshot.warning_level}")

    if snapshot.speculative_theme:
        penalty -= 6.0
        flags.append("테마 과열 가능성이 있습니다.")
    if snapshot.rumor_news:
        penalty -= 5.0
        flags.append("소문성 뉴스 비중이 높습니다.")
    if snapshot.upper_wick_ratio >= 0.4:
        penalty -= 6.0
        flags.append("긴 윗꼬리로 차익실현 압력이 보입니다.")
    if snapshot.gap_up_pct >= 7.0:
        penalty -= 6.0
        flags.append("갭상승 폭이 커서 추격 위험이 있습니다.")
    if snapshot.intraday_range_pct >= 18.0:
        penalty -= 7.0
        flags.append("당일 변동성이 과열 구간에 가깝습니다.")
    if snapshot.day_change_pct >= 15.0:
        penalty -= 8.0
        flags.append("당일 상승률이 15% 이상이라 익일 되돌림 위험이 큽니다.")
    if snapshot.turnover_ratio_20d >= 8.0:
        penalty -= 5.0
        flags.append("거래대금이 평균 대비 8배 이상 급증했습니다.")
    if snapshot.volume_ratio_20d >= 7.0:
        penalty -= 4.0
        flags.append("거래량이 평균 대비 7배 이상 급증했습니다.")
    if snapshot.return_3d_pct >= 20.0:
        penalty -= 6.0
        flags.append("최근 3거래일 단기 상승률이 과도합니다.")

    if snapshot.market_regime == "bear":
        penalty -= cfg.risk_bear_penalty
        flags.append(
            f"시장 레짐이 하락장입니다. 상승 종목 비율 {snapshot.market_breadth_pct:.1f}%, 평균 등락 {snapshot.market_avg_return_pct:.2f}%"
        )
    elif snapshot.market_regime == "weak":
        penalty -= cfg.risk_weak_penalty
        flags.append(
            f"시장 레짐이 약세입니다. 상승 종목 비율 {snapshot.market_breadth_pct:.1f}%, 평균 등락 {snapshot.market_avg_return_pct:.2f}%"
        )
    elif snapshot.market_regime == "strong":
        penalty += cfg.risk_strong_bonus
        flags.append(
            f"시장 레짐이 강세입니다. 상승 종목 비율 {snapshot.market_breadth_pct:.1f}%, 평균 등락 {snapshot.market_avg_return_pct:.2f}%"
        )

    negative_catalysts = [item for item in snapshot.catalysts if item.kind in NEGATIVE_CATALYST_KINDS]
    if negative_catalysts:
        penalty -= min(18.0, 8.0 + (len(negative_catalysts) - 1) * 4.0)
        flags.append("희석/감자/관리 리스크성 공시가 확인됐습니다.")

    return max(penalty, cfg.risk_max_penalty), flags


def evaluate_snapshot(
    snapshot: StockSnapshot,
    generated_at: datetime | None = None,
    config: ScoringConfig | None = None,
) -> CandidateEvaluation | None:
    cfg = config or DEFAULT_CONFIG
    eligible, exclusions = is_eligible(snapshot)
    if not eligible:
        return None

    liquidity_score, liquidity_reasons = _liquidity_score(snapshot, cfg)
    close_score, close_reasons = _close_strength_score(snapshot, cfg)
    catalyst_score, catalyst_reasons = _catalyst_score(snapshot, cfg)
    sector_score, sector_reasons = _sector_score(snapshot, cfg)
    continuity_score, continuity_reasons = _continuity_score(snapshot, cfg)
    penalty, risk_flags = _risk_penalty(snapshot, cfg)

    breakdown = ScoreBreakdown(
        liquidity_score=liquidity_score,
        close_strength_score=close_score,
        catalyst_score=catalyst_score,
        sector_score=sector_score,
        continuity_score=continuity_score,
        risk_penalty=penalty,
    )

    generated = generated_at or datetime.now(timezone.utc)
    reasons = [
        *liquidity_reasons,
        *close_reasons,
        *catalyst_reasons,
        *sector_reasons,
        *continuity_reasons,
    ]

    if not reasons:
        reasons.append("유효 유니버스와 기본 모멘텀 조건을 충족했습니다.")

    if exclusions:
        risk_flags.extend(exclusions)

    return CandidateEvaluation(
        date=snapshot.date,
        generated_at=generated,
        snapshot=snapshot,
        breakdown=breakdown,
        reasons=reasons,
        risk_flags=risk_flags,
    )
