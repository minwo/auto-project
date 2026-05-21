"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CandlestickChart, ExternalLink } from "lucide-react";
import type { PriceChartPoint } from "@/types";
import {
  changeClassName,
  fetchJsonWithTimeout,
  formatPercent,
  formatPrice,
  naverChartLink,
} from "@/lib/utils";

export function MiniChartLoading({ label }: { label: string }) {
  return (
    <div className="mini-chart-loading">
      <div className="loading-bar">
        <span />
      </div>
      <div className="loading-chart-lines">
        {Array.from({ length: 7 }).map((_, index) => (
          <i key={index} style={{ height: `${28 + ((index * 17) % 64)}px` }} />
        ))}
      </div>
      <strong>{label}</strong>
    </div>
  );
}

export function MiniCandlestickChart({ items }: { items: PriceChartPoint[] }) {
  const width = 360;
  const priceHeight = 150;
  const volumeHeight = 42;
  const height = priceHeight + volumeHeight + 20;
  const padding = { top: 10, right: 8, bottom: 8, left: 8 };
  const chartWidth = width - padding.left - padding.right;
  const highs = items.map((item) => item.high);
  const lows = items.map((item) => item.low);
  const maxPrice = Math.max(...highs);
  const minPrice = Math.min(...lows);
  const priceRange = Math.max(maxPrice - minPrice, 1);
  const maxVolume = Math.max(...items.map((item) => item.volume), 1);
  const slot = chartWidth / Math.max(items.length, 1);
  const candleWidth = Math.max(3, Math.min(8, slot * 0.55));
  const latest = items[items.length - 1];
  const first = items[0];
  const changePct = first.close > 0 ? ((latest.close - first.close) / first.close) * 100 : 0;

  const yPrice = (price: number) => padding.top + ((maxPrice - price) / priceRange) * (priceHeight - padding.top);
  const xFor = (index: number) => padding.left + slot * index + slot / 2;
  const volumeTop = priceHeight + 12;

  const maPath = (windowSize: number) => {
    const points: string[] = [];
    items.forEach((_, index) => {
      if (index + 1 < windowSize) return;
      const windowItems = items.slice(index + 1 - windowSize, index + 1);
      const average = windowItems.reduce((sum, item) => sum + item.close, 0) / windowItems.length;
      points.push(`${xFor(index)},${yPrice(average)}`);
    });
    return points.join(" ");
  };

  return (
    <div className="mini-chart">
      <div className="mini-chart-meta">
        <span>{latest.date}</span>
        <strong className={changeClassName(changePct)}>
          {formatPrice(latest.close)} · {formatPercent(changePct)}
        </strong>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="최근 일봉 캔들 차트">
        <line className="chart-grid-line" x1={padding.left} x2={width - padding.right} y1={yPrice(maxPrice)} y2={yPrice(maxPrice)} />
        <line className="chart-grid-line" x1={padding.left} x2={width - padding.right} y1={yPrice(minPrice)} y2={yPrice(minPrice)} />
        {items.map((item, index) => {
          const x = xFor(index);
          const openY = yPrice(item.open);
          const closeY = yPrice(item.close);
          const highY = yPrice(item.high);
          const lowY = yPrice(item.low);
          const isUp = item.close >= item.open;
          const bodyTop = Math.min(openY, closeY);
          const bodyHeight = Math.max(Math.abs(closeY - openY), 2);
          const volumeBarHeight = Math.max((item.volume / maxVolume) * volumeHeight, 1);
          return (
            <g className={isUp ? "candle up-candle" : "candle down-candle"} key={`${item.date}-${index}`}>
              <line x1={x} x2={x} y1={highY} y2={lowY} />
              <rect x={x - candleWidth / 2} y={bodyTop} width={candleWidth} height={bodyHeight} rx={1} />
              <rect
                className="volume-bar"
                x={x - candleWidth / 2}
                y={volumeTop + volumeHeight - volumeBarHeight}
                width={candleWidth}
                height={volumeBarHeight}
                rx={1}
              />
            </g>
          );
        })}
        <polyline className="ma-line ma5" points={maPath(5)} />
        <polyline className="ma-line ma20" points={maPath(20)} />
      </svg>
      <div className="mini-chart-legend">
        <span>MA5</span>
        <span>MA20</span>
      </div>
    </div>
  );
}

export function ChartPopup({ code, name }: { code: string; name: string }) {
  const [items, setItems] = useState<PriceChartPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [visible, setVisible] = useState(false);
  const loadedRef = useRef(false);
  const requestIdRef = useRef(0);
  const retryTimerRef = useRef<number | null>(null);
  const hideTimerRef = useRef<number | null>(null);
  const url = naverChartLink(code);

  const clearRetryTimer = useCallback(() => {
    if (retryTimerRef.current != null) {
      window.clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  }, []);

  const clearHideTimer = useCallback(() => {
    if (hideTimerRef.current != null) {
      window.clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    clearRetryTimer();
    clearHideTimer();
    requestIdRef.current += 1;
    loadedRef.current = false;
    setItems([]);
    setError(null);
    setLoading(false);
    setReady(false);
    setAttempt(0);
    setVisible(false);
  }, [clearRetryTimer, clearHideTimer, code]);

  useEffect(() => {
    return () => {
      clearRetryTimer();
      clearHideTimer();
      requestIdRef.current += 1;
      loadedRef.current = false;
    };
  }, [clearRetryTimer, clearHideTimer]);

  const loadChart = useCallback(
    async (nextAttempt = 1) => {
      if (loadedRef.current) return;
      clearRetryTimer();
      const requestId = requestIdRef.current + 1;
      requestIdRef.current = requestId;
      loadedRef.current = true;
      setLoading(true);
      setError(null);
      setAttempt(nextAttempt);
      try {
        const payload = await fetchJsonWithTimeout<{ items: PriceChartPoint[] }>(
          `/api/stocks/${encodeURIComponent(code)}/price-chart?limit=60`,
        );
        if (requestId !== requestIdRef.current) return;
        setItems(payload.items);
        setError(null);
        setReady(true);
      } catch (requestError) {
        if (requestId !== requestIdRef.current) return;
        const message =
          requestError instanceof Error ? requestError.message : "차트 데이터를 불러오지 못했습니다.";
        setError(message);
        setReady(true);
        if (nextAttempt < 3) {
          retryTimerRef.current = window.setTimeout(() => {
            retryTimerRef.current = null;
            if (requestId !== requestIdRef.current) return;
            loadedRef.current = false;
            setLoading(false);
            void loadChart(nextAttempt + 1);
          }, 900 * nextAttempt);
          return;
        }
      } finally {
        if (requestId !== requestIdRef.current) return;
        setLoading(false);
      }
    },
    [clearRetryTimer, code],
  );

  const showPopup = useCallback(() => {
    clearHideTimer();
    setVisible(true);
    if (!loadedRef.current) {
      void loadChart(1);
    }
  }, [clearHideTimer, loadChart]);

  const hidePopup = useCallback(() => {
    clearHideTimer();
    hideTimerRef.current = window.setTimeout(() => {
      hideTimerRef.current = null;
      setVisible(false);
    }, 200);
  }, [clearHideTimer]);

  const keepPopup = useCallback(() => {
    clearHideTimer();
  }, [clearHideTimer]);

  const panelReady = visible && (ready || loading);

  return (
    <div
      className="chart-popover"
      onMouseEnter={showPopup}
      onMouseLeave={hidePopup}
      onFocus={showPopup}
      onBlur={hidePopup}
    >
      <button
        className="mini-icon-button"
        type="button"
        title={`${name} 차트 보기`}
        onClick={() => {
          showPopup();
          void loadChart(1);
        }}
      >
        <CandlestickChart size={18} />
      </button>
      {panelReady ? (
        <div
          className="chart-popover-panel"
          role="dialog"
          aria-label={`${name} 미니 차트`}
          onMouseEnter={keepPopup}
          onMouseLeave={hidePopup}
        >
          <div className="chart-panel-header">
            <div>
              <strong>{name}</strong>
              <span>{code} · 최근 60일</span>
            </div>
            <a href={url} rel="noreferrer" target="_blank" title="네이버에서 크게 보기">
              <ExternalLink size={15} />
            </a>
          </div>
          {loading ? <MiniChartLoading label="차트 로딩 중" /> : null}
          {!loading && error ? (
            <div className="mini-chart-state error">
              <span>{error}</span>
              {attempt < 3 ? (
                <small>자동 재시도 중입니다. {attempt}/3</small>
              ) : (
                <small>잠시 후 다시 열어주세요.</small>
              )}
            </div>
          ) : null}
          {!loading && !error && items.length ? <MiniCandlestickChart items={items} /> : null}
          {!loading && !error && ready && !items.length ? (
            <div className="mini-chart-state">표시할 가격 데이터가 없습니다.</div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
