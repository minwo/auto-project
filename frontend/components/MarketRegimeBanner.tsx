import type { MarketRegime } from "@/types";
import {
  formatPoint,
  formatPercent,
  marketChangeClassName,
  regimeLabel,
  trendLabel,
  trendSymbol,
} from "@/lib/utils";

export function TrendStrip({
  shortTrend,
  midTrend,
  longTrend,
}: {
  shortTrend?: string | null;
  midTrend?: string | null;
  longTrend?: string | null;
}) {
  const items = [
    { label: "단기 추세", value: shortTrend },
    { label: "중기 추세", value: midTrend },
    { label: "장기 추세", value: longTrend },
  ];
  return (
    <div className="trend-strip" aria-label="지수 추세">
      {items.map((item) => (
        <span className={item.value || "neutral"} key={item.label} title={`${item.label} ${trendLabel(item.value)}`}>
          <b>{item.label}</b>
          <i>{trendSymbol(item.value)}</i>
        </span>
      ))}
    </div>
  );
}

export function MarketRegimeBanner({ regime }: { regime: MarketRegime }) {
  const dayReturn =
    regime.source === "index" ? regime.indexReturnPct : regime.avgReturnPct;
  const sourceLabel = regime.source === "index" ? regime.indexName || "지수" : "시장 폭";
  const marketTone = marketChangeClassName(dayReturn);
  return (
    <section className={`market-regime-banner ${regime.regime}`}>
      <div>
        <span>지수 추세</span>
        <strong>{regimeLabel(regime.regime)}</strong>
        <small>
          {sourceLabel} <b className={marketTone}>{formatPoint(regime.indexClose)}</b> · 당일{" "}
          <b className={marketTone}>{formatPercent(dayReturn)}</b>
        </small>
      </div>
      <TrendStrip shortTrend={regime.shortTrend} midTrend={regime.midTrend} longTrend={regime.longTrend} />
    </section>
  );
}
