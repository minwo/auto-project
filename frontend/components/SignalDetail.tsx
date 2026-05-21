import { ExternalLink } from "lucide-react";
import type { SignalSummary } from "@/types";
import {
  formatMoney,
  formatPercent,
  formatPrice,
  formatRatio,
  formatScore,
  formatScoreWithMax,
  formatSector,
  profileLabel,
  scoreMaxValues,
} from "@/lib/utils";
import { ChartPopup } from "./ChartPopup";
import React from "react";

export function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="detail-section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

export function ScoreItem({
  label,
  value,
  maxValue,
  penalty = false,
}: {
  label: string;
  value: number;
  maxValue: number;
  penalty?: boolean;
}) {
  return (
    <div className="score-item">
      <span>{label}</span>
      <strong>{formatScoreWithMax(value, maxValue, { penalty })}</strong>
    </div>
  );
}

export function DataPoint({ label, value }: { label: string; value: string }) {
  return (
    <div className="data-point">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function scoreMaxForProfile(profile: string | undefined) {
  if (profile === "surge") {
    return {
      liquidityScore: 30,
      closeStrengthScore: 20,
      catalystScore: 20,
      sectorScore: 20,
      continuityScore: 10,
      riskPenalty: 35,
      totalScore: 100,
    };
  }
  if (profile === "trend") {
    return {
      liquidityScore: 20,
      closeStrengthScore: 30,
      catalystScore: 5,
      sectorScore: 10,
      continuityScore: 20,
      riskPenalty: 35,
      totalScore: 100,
    };
  }
  return scoreMaxValues;
}

function scoreLabelsForProfile(profile: string | undefined) {
  if (profile === "surge") {
    return {
      liquidity: "거래 급증",
      close: "가격 패턴",
      catalyst: "이벤트",
      sector: "기술 신호",
      continuity: "수급 확산",
    };
  }
  if (profile === "trend") {
    return {
      liquidity: "추세 유동성",
      close: "가격 추세",
      catalyst: "중장기 촉매",
      sector: "시장/섹터",
      continuity: "추세 지속성",
    };
  }
  return {
    liquidity: "유동성",
    close: "종가 강도",
    catalyst: "공시/뉴스",
    sector: "섹터",
    continuity: "연속성",
  };
}

export function SignalDetail({ summary }: { summary: SignalSummary }) {
  const score = summary.componentScores.totalScore;
  const stock = summary.rawFeatures;
  const profile = stock.candidate_profile || "stable";
  const scoreMax = scoreMaxForProfile(profile);
  const scoreLabels = scoreLabelsForProfile(profile);
  const profileScores = summary.profileScores;
  const links = [
    ...(stock.disclosure_links || []).map((item) => ({ ...item, type: "공시" })),
    ...(stock.news_links || []).map((item) => ({ ...item, type: "뉴스" })),
  ];

  return (
    <div className="detail-content">
      <div className="detail-top">
        <div>
          <span className="market-pill">{stock.market}</span>
          <span className={`profile-pill ${profile}`}>{profileLabel(profile)}</span>
          <div className="stock-title-row">
            <h2>{stock.name}</h2>
            <ChartPopup code={stock.code} name={stock.name} />
          </div>
          <p>
            {stock.code} · {formatSector(stock.sector)}
          </p>
        </div>
        <div className="score-card">
          <span>Score</span>
          <strong>{formatScore(score)}</strong>
          <small>/ {scoreMax.totalScore}</small>
        </div>
      </div>

      <div className="score-grid">
        <ScoreItem label={scoreLabels.liquidity} value={summary.componentScores.liquidityScore} maxValue={scoreMax.liquidityScore} />
        <ScoreItem label={scoreLabels.close} value={summary.componentScores.closeStrengthScore} maxValue={scoreMax.closeStrengthScore} />
        <ScoreItem label={scoreLabels.catalyst} value={summary.componentScores.catalystScore} maxValue={scoreMax.catalystScore} />
        <ScoreItem label={scoreLabels.sector} value={summary.componentScores.sectorScore} maxValue={scoreMax.sectorScore} />
        <ScoreItem label={scoreLabels.continuity} value={summary.componentScores.continuityScore} maxValue={scoreMax.continuityScore} />
        <ScoreItem label="리스크 감점" value={summary.componentScores.riskPenalty} maxValue={scoreMax.riskPenalty} penalty />
      </div>

      <div className="data-grid highlight-grid">
        <DataPoint label="현재가" value={formatPrice(stock.close)} />
        <DataPoint label="신호" value={summary.tradePlan?.closeSignalLabel || "관찰 후보"} />
        <DataPoint label="손절 참고" value={formatPrice(summary.targetPrice.stopLoss)} />
        <DataPoint label="목표 여력" value={formatPercent(summary.targetPrice.baseUpsidePct)} />
      </div>

      {profile === "trend" && profileScores ? (
        <div className="data-grid highlight-grid">
          <DataPoint label="추세 품질" value={formatScore(profileScores.trendScore)} />
          <DataPoint label="진입 타이밍" value={formatScore(profileScores.entryScore)} />
          <DataPoint label="리스크 여유" value={formatScore(profileScores.riskScore)} />
          <DataPoint label="오늘 판단" value={profileScores.entrySignalLabel} />
        </div>
      ) : null}

      {summary.tradePlan ? (
        <DetailSection title={profile === "trend" ? "장기 추세 진입 계획" : "익일 조건부 진입"}>
          <div className="entry-plan-note">
            <strong>{summary.tradePlan.closeSignalLabel}</strong>
            <span>{summary.tradePlan.nextSessionPlan}</span>
          </div>
          <div className="trade-plan">
            <DataPoint label="추격 상한" value={formatPrice(summary.tradePlan.entry.maxEntryPrice)} />
            <DataPoint label="돌파 기준" value={formatPrice(summary.tradePlan.entry.breakoutTrigger)} />
            <DataPoint label="눌림 기준" value={formatPrice(summary.tradePlan.entry.pullbackEntry)} />
          </div>
          <ul className="bullet-list compact">
            <li>{summary.tradePlan.entry.openGapRule || "시초가 과열 시 진입 보류"}</li>
            <li>{summary.tradePlan.entry.invalidateRule || "전일 저가 이탈 시 후보 제외"}</li>
          </ul>
        </DetailSection>
      ) : null}

      {summary.tradePlan ? (
        <DetailSection title="청산 기준">
          <div className="trade-plan">
            <DataPoint label="손절 참고" value={formatPrice(summary.tradePlan.exit.stopLoss)} />
            <DataPoint label="보유 제한" value={`${summary.tradePlan.exit.maxHoldingDays}거래일`} />
            <DataPoint label="시간 손절" value={summary.tradePlan.exit.timeStopRule} />
          </div>
        </DetailSection>
      ) : null}

      <DetailSection title="선정 근거">
        <ul className="bullet-list">
          {summary.reasons.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </DetailSection>

      <DetailSection title="리스크">
        {summary.riskFlags.length ? (
          <ul className="risk-list">
            {summary.riskFlags.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">표시할 리스크가 없습니다.</p>
        )}
      </DetailSection>

      <div className="data-grid">
        <DataPoint label="거래대금" value={formatMoney(summary.liquidityStats.turnover)} />
        <DataPoint label="거래대금 배수" value={formatRatio(summary.liquidityStats.turnoverRatio20d)} />
        <DataPoint label="거래량 배수" value={formatRatio(summary.liquidityStats.volumeRatio20d)} />
        <DataPoint label="종가 위치" value={formatPercent(summary.priceStats.closePosition * 100)} />
        <DataPoint label="일중 변동" value={formatPercent(summary.priceStats.intradayRangePct)} />
        <DataPoint label="동반 상승" value={`${summary.sectorStats.risingPeers}개`} />
      </div>

      <DetailSection title="공시·뉴스">
        {links.length ? (
          <div className="link-list">
            {links.map((item) => (
              <a href={item.url} key={`${item.type}-${item.url}`} rel="noreferrer" target="_blank">
                <span>{item.type}</span>
                <strong>{item.title}</strong>
                <ExternalLink size={16} />
              </a>
            ))}
          </div>
        ) : (
          <p className="muted">연결된 공시나 뉴스가 없습니다.</p>
        )}
      </DetailSection>
    </div>
  );
}
