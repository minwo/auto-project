export type TableCounts = {
  stock_master?: number;
  daily_prices?: number;
  daily_disclosures?: number;
  daily_news?: number;
  daily_market_warnings?: number;
  daily_candidate_scores?: number;
  backtest_summaries?: number;
};

export type SystemStatus = {
  mode: string;
  databaseConfigured: boolean;
  latestScoreDate: string | null;
  latestTradeDate?: string | null;
  databaseConnected?: boolean;
  tableCounts?: TableCounts;
  error?: string;
};

export type TradingDatesPayload = {
  latestDate: string | null;
  dates: string[];
};

export type LinkItem = {
  title: string;
  url: string;
};

export type SearchResult = {
  code: string;
  name: string;
  score: number;
  candidateProfile?: string;
  profileScores?: ProfileScores;
  sector: string;
  close: number;
  prevClose: number;
  dayChangePct: number;
  targetPrice: number;
  targetUpsidePct: number;
  turnoverRatio20d: number;
  volumeRatio20d: number;
  return3dPct: number;
  reasons: string[];
  riskFlags: string[];
  marketRegime?: string;
  marketRegimeSource?: string;
  marketIndexName?: string | null;
  marketIndexReturnPct?: number;
  marketIndexReturn5dPct?: number;
  marketIndexReturn20dPct?: number;
  marketIndexReturn60dPct?: number;
  marketShortTrend?: string;
  marketMidTrend?: string;
  marketLongTrend?: string;
};

export type ProfileScores = {
  scoreMode: string;
  trendScore?: number | null;
  entryScore: number;
  riskScore: number;
  entrySignal: string;
  entrySignalLabel: string;
};

export type Candidate = SearchResult & {
  rank: number;
  newsLinks: LinkItem[];
  disclosureLinks: LinkItem[];
};

export type CatalystItem = LinkItem & {
  kind: string;
  trust_score: number;
};

export type TradePlan = {
  closeSignal: string;
  closeSignalLabel: string;
  entryMode: string;
  nextSessionPlan: string;
  entry: {
    maxOpenGapPct: number;
    maxEntryPrice: number;
    breakoutTrigger: number;
    pullbackEntry: number;
    openGapRule?: string;
    invalidateRule?: string;
    rules: string[];
  };
  exit: {
    firstTarget: number;
    baseTarget: number;
    aggressiveTarget: number;
    stopLoss: number;
    maxHoldingDays: number;
    timeStopRule: string;
    rules: string[];
  };
};

export type SignalSummary = {
  componentScores: {
    liquidityScore: number;
    closeStrengthScore: number;
    catalystScore: number;
    sectorScore: number;
    continuityScore: number;
    riskPenalty: number;
    totalScore: number;
  };
  profileScores?: ProfileScores;
  rawFeatures: {
    date: string;
    code: string;
    name: string;
    market: string;
    sector: string;
    candidate_profile?: string;
    close: number;
    high: number;
    low: number;
    prev_close: number;
    volume: number;
    turnover: number;
    news_links?: LinkItem[];
    disclosure_links?: LinkItem[];
  };
  priceStats: {
    close: number;
    high: number;
    low: number;
    prevClose: number;
    dayChangePct?: number;
    closePosition: number;
    upperWickRatio: number;
    gapUpPct: number;
    intradayRangePct: number;
  };
  targetPrice: {
    conservativeTarget: number;
    baseTarget: number;
    aggressiveTarget: number;
    stopLoss: number;
    baseUpsidePct: number;
  };
  tradePlan?: TradePlan;
  liquidityStats: {
    turnover: number;
    avgTurnover20d: number;
    turnoverRatio20d: number;
    volume: number;
    avgVolume20d: number;
    volumeRatio20d: number;
  };
  sectorStats: {
    sector: string;
    risingPeers: number;
    sectorTurnoverRatio: number;
  };
  catalystSummary: {
    count: number;
    items: CatalystItem[];
  };
  reasons: string[];
  riskFlags: string[];
};

export type PriceChartPoint = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type MarketRegime = {
  regime: string;
  source: string;
  indexName?: string | null;
  indexClose?: number;
  indexReturnPct: number;
  indexReturn5dPct: number;
  indexReturn20dPct: number;
  indexReturn60dPct: number;
  shortTrend: string;
  midTrend: string;
  longTrend: string;
  breadthPct: number;
  avgReturnPct: number;
};
