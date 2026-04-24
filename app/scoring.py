from __future__ import annotations

from datetime import datetime, timezone

from app.domain import CandidateEvaluation, ScoreBreakdown, StockSnapshot


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


def _liquidity_score(snapshot: StockSnapshot) -> tuple[float, list[str]]:
    turnover_points = _clamp((snapshot.turnover_ratio_20d - 1.0) * 12.0, 0.0, 16.0)
    volume_points = _clamp((snapshot.volume_ratio_20d - 1.0) * 7.0, 0.0, 7.0)
    expansion_bonus = 2.0 if snapshot.turnover_ratio_20d >= 2.0 and snapshot.volume_ratio_20d >= 1.8 else 0.0
    score = _clamp(turnover_points + volume_points + expansion_bonus, 0.0, 25.0)

    reasons: list[str] = []
    if snapshot.turnover_ratio_20d >= 2.0:
        reasons.append("최근 20일 대비 거래대금이 크게 확대됐습니다.")
    if snapshot.volume_ratio_20d >= 1.8:
        reasons.append("평균 대비 거래량이 유의미하게 증가했습니다.")
    return score, reasons


def _close_strength_score(snapshot: StockSnapshot) -> tuple[float, list[str]]:
    base = snapshot.close_position * 16.0
    wick_penalty = 6.0 if snapshot.upper_wick_ratio >= 0.35 else 0.0
    score = _clamp(base + 4.0 - wick_penalty, 0.0, 20.0)

    reasons: list[str] = []
    if snapshot.close_position >= 0.75:
        reasons.append("종가가 당일 고가권에 가까워 마감 강도가 좋습니다.")
    if snapshot.upper_wick_ratio <= 0.2:
        reasons.append("윗꼬리가 짧아 매물 소화 흐름이 양호합니다.")
    return score, reasons


def _catalyst_score(snapshot: StockSnapshot) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    seen_titles: set[str] = set()

    kind_weights = {
        "disclosure": 8.0,
        "earnings": 8.0,
        "contract": 8.0,
        "policy": 6.0,
        "industry": 5.0,
        "news": 4.0,
    }

    for catalyst in snapshot.catalysts:
        score += kind_weights.get(catalyst.kind, 3.0) * catalyst.trust_score
        if catalyst.title not in seen_titles:
            reasons.append(f"촉매 확인: {catalyst.title}")
            seen_titles.add(catalyst.title)

    return _clamp(score, 0.0, 20.0), reasons


def _sector_score(snapshot: StockSnapshot) -> tuple[float, list[str]]:
    peers_points = _clamp(snapshot.sector_rising_peers * 2.5, 0.0, 10.0)
    turnover_points = _clamp((snapshot.sector_turnover_ratio - 1.0) * 5.0, 0.0, 5.0)
    score = _clamp(peers_points + turnover_points, 0.0, 15.0)

    reasons: list[str] = []
    if snapshot.sector_rising_peers >= 3:
        reasons.append("동일 섹터 내 동반 상승 종목이 충분히 확인됩니다.")
    if snapshot.sector_turnover_ratio >= 1.4:
        reasons.append("섹터 전체 거래대금도 함께 유입되고 있습니다.")
    return score, reasons


def _continuity_score(snapshot: StockSnapshot) -> tuple[float, list[str]]:
    move_score = 0.0
    if 1.0 <= snapshot.return_3d_pct <= 9.0:
        move_score = 7.0
    elif 9.0 < snapshot.return_3d_pct <= 15.0:
        move_score = 5.0
    elif snapshot.return_3d_pct > 15.0:
        move_score = 2.0

    lead_bonus = 3.0 if snapshot.has_leading_move else 0.0
    score = _clamp(move_score + lead_bonus, 0.0, 10.0)

    reasons: list[str] = []
    if move_score >= 5.0:
        reasons.append("최근 3거래일 추세 연속성이 유지되고 있습니다.")
    if lead_bonus > 0:
        reasons.append("급등 전 선행 움직임이 포착됐습니다.")
    return score, reasons


def _risk_penalty(snapshot: StockSnapshot) -> tuple[float, list[str]]:
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
        flags.append("풍문성 뉴스 비중이 높습니다.")
    if snapshot.upper_wick_ratio >= 0.4:
        penalty -= 6.0
        flags.append("장대 윗꼬리로 차익실현 압력이 보입니다.")
    if snapshot.gap_up_pct >= 7.0:
        penalty -= 6.0
        flags.append("갭상승 폭이 커서 추격 위험이 있습니다.")
    if snapshot.intraday_range_pct >= 18.0:
        penalty -= 7.0
        flags.append("당일 변동성이 과열 구간에 가깝습니다.")

    return max(penalty, -30.0), flags


def evaluate_snapshot(snapshot: StockSnapshot, generated_at: datetime | None = None) -> CandidateEvaluation | None:
    eligible, exclusions = is_eligible(snapshot)
    if not eligible:
        return None

    liquidity_score, liquidity_reasons = _liquidity_score(snapshot)
    close_score, close_reasons = _close_strength_score(snapshot)
    catalyst_score, catalyst_reasons = _catalyst_score(snapshot)
    sector_score, sector_reasons = _sector_score(snapshot)
    continuity_score, continuity_reasons = _continuity_score(snapshot)
    penalty, risk_flags = _risk_penalty(snapshot)

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
