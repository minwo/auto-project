"use client";

import {
  AlertTriangle,
  BarChart3,
  BookOpenText,
  CalendarDays,
  Database,
  ExternalLink,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  CandlestickChart,
  TrendingUp,
  Trophy,
} from "lucide-react";
import { MarketRegimeBanner } from "@/components/MarketRegimeBanner";
import { Metric } from "@/components/Metric";
import { SignalDetail } from "@/components/SignalDetail";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  SystemStatus,
  TradingDatesPayload,
  SearchResult,
  Candidate,
  SignalSummary,
  MarketRegime,
} from "@/types";
import {
  numberFormatter,
  compactFormatter,
  scoreMaxValues,
  todayIso,
  parseIsoDate,
  formatIsoDate,
  formatMonthLabel,
  shiftMonth,
  buildCalendarCells,
  formatScore,
  formatScoreWithMax,
  formatRatio,
  formatPercent,
  formatMoney,
  formatPrice,
  formatPoint,
  formatSector,
  profileLabel,
  changeClassName,
  marketChangeClassName,
  regimeLabel,
  trendLabel,
  trendSymbol,
  naverChartLink,
  fetchJson,
  fetchJsonWithTimeout,
} from "@/lib/utils";

export default function DashboardPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [selectedDate, setSelectedDate] = useState("");
  const [query, setQuery] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selectedCode, setSelectedCode] = useState("");
  const [summary, setSummary] = useState<SignalSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [emptyReason, setEmptyReason] = useState<string | null>(null);
  const [marketRegime, setMarketRegime] = useState<MarketRegime | null>(null);
  const [availableTradeDates, setAvailableTradeDates] = useState<string[]>([]);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [calendarMonth, setCalendarMonth] = useState(todayIso().slice(0, 7));
  const boardRequestIdRef = useRef(0);
  const initialLoadDoneRef = useRef(false);

  const availableTradeDateSet = useMemo(() => new Set(availableTradeDates), [availableTradeDates]);
  const topCandidateCodes = useMemo(() => new Set(candidates.map((item) => item.code)), [candidates]);
  const topScore = useMemo(() => {
    if (!results.length) return null;
    return Math.max(...results.map((item) => item.score));
  }, [results]);

  const loadStatus = useCallback(async () => {
    const payload = await fetchJson<SystemStatus>("/api/system/status");
    setStatus(payload);
    return payload;
  }, []);

  const loadTradingDates = useCallback(async () => {
    const payload = await fetchJson<TradingDatesPayload>("/api/market/trading-dates");
    setAvailableTradeDates(payload.dates);
    if (payload.latestDate) {
      setCalendarMonth(payload.latestDate.slice(0, 7));
      setSelectedDate((current) => current || payload.latestDate || "");
    }
    return payload;
  }, []);

  const loadDetail = useCallback(async (code: string, dateValue: string) => {
    if (!code) return;
    setDetailLoading(true);
    try {
      const payload = await fetchJson<SignalSummary>(
        `/api/stocks/${encodeURIComponent(code)}/signal-summary?date=${encodeURIComponent(dateValue)}`,
      );
      setSelectedCode(code);
      setSummary(payload);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const loadBoard = useCallback(
    async (dateValue: string, searchValue: string) => {
      const requestId = boardRequestIdRef.current + 1;
      boardRequestIdRef.current = requestId;
      setLoading(true);
      setError(null);
      setNotice(null);
      setEmptyReason(null);
      try {
        const candidateRequest: Promise<{ candidates: Candidate[]; emptyReason?: string | null }> =
          fetchJson<{ candidates: Candidate[]; emptyReason?: string | null }>(
            `/api/candidates/daily?date=${encodeURIComponent(dateValue)}`,
          ).catch(() => ({ candidates: [], emptyReason: null }));

        const shouldAutoLoad = searchValue.trim().length > 0;
        const searchRequest = fetchJson<{
          loaded?: boolean;
          loadError?: string | null;
          marketRegime?: MarketRegime | null;
          results: SearchResult[];
        }>(
          `/api/stocks/search?date=${encodeURIComponent(dateValue)}&q=${encodeURIComponent(searchValue)}&limit=50&autoLoad=${shouldAutoLoad ? "true" : "false"}`,
        );

        const [candidatePayload, searchPayload] = await Promise.all([candidateRequest, searchRequest]);
        if (requestId !== boardRequestIdRef.current) return;
        const orderedCandidates = [...candidatePayload.candidates].sort((a, b) => b.score - a.score || a.code.localeCompare(b.code));
        const orderedResults = [...searchPayload.results].sort((a, b) => b.score - a.score || a.code.localeCompare(b.code));
        setCandidates(orderedCandidates);
        setResults(orderedResults);
        setMarketRegime(searchPayload.marketRegime || null);
        setEmptyReason(candidatePayload.emptyReason || (!orderedResults.length ? "적정 점수 이상 종목이 없습니다." : null));

        if (searchPayload.loadError) {
          setNotice(searchPayload.loadError);
        } else if (searchPayload.loaded) {
          setNotice("새 종목 데이터를 적재하고 점수를 계산했습니다.");
        } else if (!orderedResults.length) {
          setNotice(`${dateValue} 기준 적정 점수 이상 종목이 없습니다.`);
        }

        const nextCode =
          selectedCode && orderedResults.some((item) => item.code === selectedCode)
            ? selectedCode
            : orderedResults[0]?.code || "";

        if (nextCode) {
          await loadDetail(nextCode, dateValue);
        } else {
          setSelectedCode("");
          setSummary(null);
        }
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "데이터를 불러오지 못했습니다.");
        setResults([]);
        setCandidates([]);
        setSummary(null);
        setMarketRegime(null);
      } finally {
        if (requestId === boardRequestIdRef.current) {
          setLoading(false);
        }
      }
    },
    [loadDetail, selectedCode],
  );

  useEffect(() => {
    if (initialLoadDoneRef.current) return;
    initialLoadDoneRef.current = true;
    let mounted = true;
    Promise.all([loadStatus(), loadTradingDates()])
      .then(([payload, tradingDates]) => {
        if (!mounted) return;
        const dateValue = tradingDates.latestDate || payload.latestTradeDate || payload.latestScoreDate || todayIso();
        setSelectedDate(dateValue);
        setCalendarMonth(dateValue.slice(0, 7));
        return loadBoard(dateValue, "");
      })
      .catch((requestError) => {
        if (!mounted) return;
        setError(requestError instanceof Error ? requestError.message : "시스템 상태를 확인하지 못했습니다.");
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [loadBoard, loadStatus, loadTradingDates]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      if (selectedDate) {
        void loadBoard(selectedDate, query);
      }
    }, 300);
    return () => window.clearTimeout(handle);
  }, [loadBoard, query, selectedDate]);

  const refresh = async () => {
    const [payload, tradingDates] = await Promise.all([loadStatus(), loadTradingDates()]);
    const dateValue = selectedDate || tradingDates.latestDate || payload.latestTradeDate || payload.latestScoreDate || todayIso();
    setSelectedDate(dateValue);
    setCalendarMonth(dateValue.slice(0, 7));
    await loadBoard(dateValue, query);
  };

  const counts = status?.tableCounts || {};

  return (
    <main className="shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">Signal Dashboard</p>
          <h1>국내주식 후보 분석</h1>
        </div>
        <div className="top-actions">
          <Link className="icon-button" href="/top-picks">
            <Trophy size={18} />
            <span>고점수 추적</span>
          </Link>
          <Link className="icon-button" href="/score-guide">
            <BookOpenText size={18} />
            <span>점수 기준</span>
          </Link>
          <button className="icon-button" type="button" onClick={refresh} title="새로고침">
            <RefreshCw size={18} />
            <span>새로고침</span>
          </button>
        </div>
      </section>

      <section className="status-grid">
        <Metric label="DB 상태" value={status?.databaseConnected ? "정상" : "확인 필요"} icon={<ShieldCheck size={18} />} />
        <Metric label="기준일" value={selectedDate || status?.latestTradeDate || status?.latestScoreDate || "-"} icon={<CalendarDays size={18} />} />
        <Metric label="종목" value={numberFormatter.format(counts.stock_master || 0)} icon={<Database size={18} />} />
        <Metric label="최고 점수" value={formatScore(topScore)} icon={<TrendingUp size={18} />} />
      </section>

      {marketRegime ? <MarketRegimeBanner regime={marketRegime} /> : null}

      <section className="toolbar">
        <label className="field date-field">
          <span>기준일</span>
          <button className="date-trigger" type="button" onClick={() => setCalendarOpen((current) => !current)}>
            <CalendarDays size={16} />
            <strong>{selectedDate || "거래일 선택"}</strong>
          </button>
          {calendarOpen ? (
            <div className="trade-calendar">
              <div className="calendar-head">
                <button type="button" onClick={() => setCalendarMonth((current) => shiftMonth(current, -1))}>
                  이전
                </button>
                <strong>{formatMonthLabel(calendarMonth)}</strong>
                <button type="button" onClick={() => setCalendarMonth((current) => shiftMonth(current, 1))}>
                  다음
                </button>
              </div>
              <div className="calendar-weekdays">
                {["일", "월", "화", "수", "목", "금", "토"].map((day) => (
                  <span key={day}>{day}</span>
                ))}
              </div>
              <div className="calendar-grid">
                {buildCalendarCells(calendarMonth).map((cell, index) =>
                  cell ? (
                    <button
                      className={cell.iso === selectedDate ? "active" : ""}
                      disabled={!availableTradeDateSet.has(cell.iso)}
                      key={cell.iso}
                      type="button"
                      onClick={() => {
                        setSelectedDate(cell.iso);
                        setCalendarOpen(false);
                      }}
                    >
                      {cell.day}
                    </button>
                  ) : (
                    <span key={`blank-${index}`} />
                  ),
                )}
              </div>
            </div>
          ) : null}
        </label>
        <label className="field search-field">
          <span>종목 검색</span>
          <div className="input-with-icon">
            <Search size={18} />
            <input
              type="search"
              value={query}
              placeholder="예: 에코프로비엠, 247540"
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </label>
      </section>

      {notice ? (
        <div className="notice">
          <Sparkles size={18} />
          {notice}
        </div>
      ) : null}

      {error ? (
        <div className="error-banner">
          <AlertTriangle size={18} />
          {error}
        </div>
      ) : null}

      <section className="content-grid">
        <section className="list-panel">
          <div className="panel-heading">
            <div>
              <h2>검색 결과</h2>
              <p>{results.length}개 종목</p>
            </div>
            <BarChart3 size={20} />
          </div>
          <div className="result-list">
            {loading ? (
              Array.from({ length: 5 }).map((_, index) => <div className="skeleton-row" key={index} />)
            ) : results.length ? (
              results.map((item, index) => (
                <button
                  className={`stock-row ${item.code === selectedCode ? "active" : ""}`}
                  key={item.code}
                  type="button"
                  onClick={() => loadDetail(item.code, selectedDate)}
                >
                  <span className="rank">{index + 1}</span>
                  <span className="stock-main">
                    <strong>
                      {item.name}
                      <span className={`profile-pill ${item.candidateProfile || "stable"}`}>
                        {profileLabel(item.candidateProfile)}
                      </span>
                    </strong>
                    <small>
                      {item.code} · {formatSector(item.sector)} · {formatPrice(item.close)}
                    </small>
                    <span className="target-line">
                      목표 {formatPrice(item.targetPrice)} · 여력 {formatPercent(item.targetUpsidePct)}
                    </span>
                    <span className="reason-line">{item.reasons[0] || "분석 근거가 없습니다."}</span>
                  </span>
                  <span className="stock-side">
                    <strong>{formatScore(item.score)}</strong>
                    <small className={changeClassName(item.dayChangePct)}>{formatPercent(item.dayChangePct)}</small>
                    <small>{formatRatio(item.turnoverRatio20d)}</small>
                    {topCandidateCodes.has(item.code) ? <em>후보</em> : null}
                  </span>
                </button>
              ))
            ) : (
              <div className="empty-state">{emptyReason || "검색 결과가 없습니다."}</div>
            )}
          </div>
        </section>

        <section className="detail-panel">
          {detailLoading ? (
            <div className="detail-loading">
              <Loader2 className="spin" size={26} />
              상세 데이터를 불러오는 중입니다.
            </div>
          ) : summary ? (
            <SignalDetail summary={summary} />
          ) : (
            <div className="empty-state">종목을 선택하면 상세 분석이 표시됩니다.</div>
          )}
        </section>
      </section>
    </main>
  );
}

