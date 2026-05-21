"use client";

import { AlertTriangle, ArrowLeft, CalendarDays, Loader2, TrendingDown, TrendingUp, Trophy } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type TopPick = {
  pickDate: string;
  recommendationStartDate?: string;
  recommendationEndDate?: string;
  code: string;
  name: string;
  sector: string;
  score: number;
  baseClose: number;
  latestDate: string;
  latestClose: number;
  changePct: number;
  reasons: string[];
  riskFlags: string[];
  marketRegime?: string;
  marketRegimeSource?: string;
  marketIndexName?: string | null;
  marketIndexClose?: number;
  marketIndexReturnPct?: number;
  marketIndexReturn5dPct?: number;
  marketIndexReturn20dPct?: number;
  marketIndexReturn60dPct?: number;
  marketShortTrend?: string;
  marketMidTrend?: string;
  marketLongTrend?: string;
};

const numberFormatter = new Intl.NumberFormat("ko-KR");

function formatScore(value: number) {
  return value.toFixed(2);
}

function formatPercent(value: number) {
  return `${value.toFixed(2)}%`;
}

function formatPrice(value: number) {
  return `${numberFormatter.format(Math.round(value))}원`;
}

function formatPoint(value: number | null | undefined) {
  if (value == null || Number.isNaN(value) || value <= 0) return "-";
  return `${numberFormatter.format(Number(value.toFixed(2)))}pt`;
}

function formatSector(value: string | null | undefined) {
  const normalized = (value || "").trim();
  if (!normalized || normalized === "Unclassified") return "미분류";
  return normalized;
}

function changeClassName(value: number) {
  if (value === 0) return "flat";
  return value > 0 ? "up" : "down";
}

function marketChangeClassName(value: number | null | undefined) {
  if (value == null || Number.isNaN(value) || value === 0) return "flat";
  return value > 0 ? "market-up" : "market-down";
}

function regimeLabel(value: string | null | undefined) {
  if (value === "bear") return "하락장";
  if (value === "weak") return "약세";
  if (value === "strong") return "강세";
  return "중립";
}

function trendLabel(value: string | null | undefined) {
  if (value === "up") return "상승";
  if (value === "down") return "하락";
  return "중립";
}

function recommendationDateLabel(item: TopPick) {
  const startDate = item.recommendationStartDate || item.pickDate;
  const endDate = item.recommendationEndDate || item.latestDate || item.pickDate;
  return startDate === endDate ? startDate : `${startDate} ~ ${endDate}`;
}

async function fetchTopPicks(): Promise<{ asOf: string; retentionDays: number; items: TopPick[] }> {
  const response = await fetch("/api/top-picks/daily", { cache: "no-store" });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      message = payload.detail || message;
    } catch {
      message = await response.text();
    }
    throw new Error(message);
  }
  return response.json();
}

export default function TopPicksPage() {
  const [items, setItems] = useState<TopPick[]>([]);
  const [asOf, setAsOf] = useState("");
  const [retentionDays, setRetentionDays] = useState(92);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTopPicks()
      .then((payload) => {
        setItems(payload.items);
        setAsOf(payload.asOf);
        setRetentionDays(payload.retentionDays);
      })
      .catch((requestError) => {
        setError(requestError instanceof Error ? requestError.message : "추적 목록을 불러오지 못했습니다.");
      })
      .finally(() => setLoading(false));
  }, []);

  const averageChange = useMemo(() => {
    if (!items.length) return 0;
    return items.reduce((sum, item) => sum + item.changePct, 0) / items.length;
  }, [items]);

  const performance = useMemo(() => {
    const executed = items.filter((item) => item.baseClose > 0);
    const winners = executed.filter((item) => item.changePct > 0);
    const losers = executed.filter((item) => item.changePct < 0);
    const totalReturnPct = executed.reduce((compound, item) => compound * (1 + item.changePct / 100), 1) - 1;
    const averageWinPct = winners.length ? winners.reduce((sum, item) => sum + item.changePct, 0) / winners.length : 0;
    const averageLossPct = losers.length ? losers.reduce((sum, item) => sum + item.changePct, 0) / losers.length : 0;
    const bestReturnPct = executed.length ? Math.max(...executed.map((item) => item.changePct)) : 0;
    const worstReturnPct = executed.length ? Math.min(...executed.map((item) => item.changePct)) : 0;
    return {
      executedCount: executed.length,
      winnerCount: winners.length,
      loserCount: losers.length,
      accuracyPct: executed.length ? (winners.length / executed.length) * 100 : 0,
      totalReturnPct: totalReturnPct * 100,
      averageWinPct,
      averageLossPct,
      bestReturnPct,
      worstReturnPct,
    };
  }, [items]);

  const bestPick = useMemo(() => {
    if (!items.length) return null;
    return [...items].sort((a, b) => b.changePct - a.changePct)[0];
  }, [items]);

  return (
    <main className="shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">Daily Top Pick</p>
          <h1>고점수 종목 추적</h1>
        </div>
        <Link className="icon-button" href="/">
          <ArrowLeft size={18} />
          <span>검색으로</span>
        </Link>
      </section>

      <section className="status-grid">
        <Metric label="보관 기간" value={`최근 ${retentionDays}일`} icon={<CalendarDays size={18} />} />
        <Metric label="추적 종목" value={`${items.length}개`} icon={<Trophy size={18} />} />
        <Metric label="평균 등락" value={formatPercent(averageChange)} icon={<TrendingUp size={18} />} />
        <Metric label="최고 상승" value={bestPick ? formatPercent(bestPick.changePct) : "-"} icon={<TrendingDown size={18} />} />
      </section>

      {error ? (
        <div className="error-banner">
          <AlertTriangle size={18} />
          {error}
        </div>
      ) : null}

      <section className="wide-panel performance-panel">
        <div className="panel-heading">
          <div>
            <h2>매수 가정 성과 확인</h2>
            <p>각 선정일 종가에 동일 금액으로 매수하고 현재가까지 보유한 단순 검증입니다.</p>
          </div>
          <TrendingUp size={20} />
        </div>
        <div className="performance-grid">
          <DataPoint label="전체 수익률" value={formatPercent(performance.totalReturnPct)} tone={changeClassName(performance.totalReturnPct)} />
          <DataPoint label="정확도" value={formatPercent(performance.accuracyPct)} />
          <DataPoint label="수익 종목" value={`${performance.winnerCount}/${performance.executedCount}개`} />
          <DataPoint label="평균 수익" value={formatPercent(averageChange)} tone={changeClassName(averageChange)} />
          <DataPoint label="평균 이익" value={formatPercent(performance.averageWinPct)} tone="up" />
          <DataPoint label="평균 손실" value={formatPercent(performance.averageLossPct)} tone="down" />
          <DataPoint label="최고 수익" value={formatPercent(performance.bestReturnPct)} tone={changeClassName(performance.bestReturnPct)} />
          <DataPoint label="최대 손실" value={formatPercent(performance.worstReturnPct)} tone={changeClassName(performance.worstReturnPct)} />
        </div>
      </section>

      <section className="wide-panel">
        <div className="panel-heading">
          <div>
            <h2>매일 최고 점수 1개</h2>
            <p>{asOf ? `${asOf} 기준, 3개월 경과 항목은 자동 제외` : "데이터 확인 중"}</p>
          </div>
          <Trophy size={20} />
        </div>

        {loading ? (
          <div className="detail-loading">
            <Loader2 className="spin" size={26} />
            추적 데이터를 불러오는 중입니다.
          </div>
        ) : items.length ? (
          <div className="tracking-list">
            {items.map((item) => (
              <article className="tracking-row" key={`${item.pickDate}-${item.code}`}>
                <div className="tracking-date">
                  <span>{recommendationDateLabel(item)}</span>
                  <strong>{formatScore(item.score)}</strong>
                </div>
                <div className="tracking-main">
                  <h2>{item.name}</h2>
                  <p>
                    {item.code} · {formatSector(item.sector)}
                  </p>
                  <div className="tracking-reason">{item.reasons[0] || "선정 근거가 없습니다."}</div>
                </div>
                <div className="tracking-price">
                  <span>기준 {formatPrice(item.baseClose)}</span>
                  <span>현재 {formatPrice(item.latestClose)}</span>
                  <strong className={changeClassName(item.changePct)}>{formatPercent(item.changePct)}</strong>
                  <small>{item.latestDate} 종가 기준</small>
                  <small>
                    {regimeLabel(item.marketRegime)} ·{" "}
                    <b className={marketChangeClassName(item.marketIndexReturnPct)}>
                      {formatPoint(item.marketIndexClose)}
                    </b>{" "}
                    · 당일{" "}
                    <b className={marketChangeClassName(item.marketIndexReturnPct)}>
                      {formatPercent(item.marketIndexReturnPct || 0)}
                    </b>
                  </small>
                </div>
                <TrendStrip
                  shortTrend={item.marketShortTrend}
                  midTrend={item.marketMidTrend}
                  longTrend={item.marketLongTrend}
                />
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">아직 추적할 고점수 종목이 없습니다.</div>
        )}
      </section>
    </main>
  );
}

function Metric({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="metric">
      <div className="metric-icon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DataPoint({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="data-point">
      <span>{label}</span>
      <strong className={tone}>{value}</strong>
    </div>
  );
}

function TrendStrip({
  shortTrend,
  midTrend,
  longTrend,
}: {
  shortTrend?: string | null;
  midTrend?: string | null;
  longTrend?: string | null;
}) {
  const items = [
    { label: "단기 추세", shortLabel: "단", value: shortTrend },
    { label: "중기 추세", shortLabel: "중", value: midTrend },
    { label: "장기 추세", shortLabel: "장", value: longTrend },
  ];
  return (
    <div className="trend-strip compact" aria-label="선정일 지수 추세">
      {items.map((item) => (
        <span className={item.value || "neutral"} key={item.label} title={`${item.label} ${trendLabel(item.value)}`}>
          <b>{item.shortLabel}</b>
          <i>{trendLabel(item.value)}</i>
        </span>
      ))}
    </div>
  );
}
