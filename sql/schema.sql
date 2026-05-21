CREATE TABLE IF NOT EXISTS stock_master (
    code VARCHAR(12) PRIMARY KEY,
    name_kr VARCHAR(120) NOT NULL,
    market VARCHAR(20) NOT NULL,
    sector VARCHAR(120),
    isin VARCHAR(32),
    dart_corp_code VARCHAR(16),
    security_type VARCHAR(40),
    is_common_stock BOOLEAN NOT NULL DEFAULT TRUE,
    is_preferred BOOLEAN NOT NULL DEFAULT FALSE,
    is_etf BOOLEAN NOT NULL DEFAULT FALSE,
    is_etn BOOLEAN NOT NULL DEFAULT FALSE,
    is_spac BOOLEAN NOT NULL DEFAULT FALSE,
    listed_at DATE,
    delisted_at DATE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_prices (
    trade_date DATE NOT NULL,
    code VARCHAR(12) NOT NULL REFERENCES stock_master(code),
    open_price NUMERIC(18, 4) NOT NULL,
    high_price NUMERIC(18, 4) NOT NULL,
    low_price NUMERIC(18, 4) NOT NULL,
    close_price NUMERIC(18, 4) NOT NULL,
    volume NUMERIC(20, 2) NOT NULL,
    turnover NUMERIC(20, 2) NOT NULL,
    source VARCHAR(32) NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, code)
);

CREATE TABLE IF NOT EXISTS daily_disclosures (
    trade_date DATE NOT NULL,
    code VARCHAR(12) NOT NULL REFERENCES stock_master(code),
    receipt_no VARCHAR(32) NOT NULL,
    report_name VARCHAR(255) NOT NULL,
    report_type VARCHAR(64),
    disclosed_at TIMESTAMPTZ,
    url TEXT NOT NULL,
    is_material BOOLEAN NOT NULL DEFAULT FALSE,
    material_tag VARCHAR(64),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, code, receipt_no)
);

CREATE TABLE IF NOT EXISTS daily_news (
    trade_date DATE NOT NULL,
    code VARCHAR(12) NOT NULL REFERENCES stock_master(code),
    news_id VARCHAR(64) NOT NULL,
    title VARCHAR(500) NOT NULL,
    url TEXT NOT NULL,
    source VARCHAR(64) NOT NULL,
    published_at TIMESTAMPTZ,
    summary TEXT,
    news_type VARCHAR(64),
    trust_score NUMERIC(4, 2) NOT NULL DEFAULT 0.50,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, code, news_id)
);

CREATE TABLE IF NOT EXISTS daily_market_warnings (
    trade_date DATE NOT NULL,
    code VARCHAR(12) NOT NULL REFERENCES stock_master(code),
    warning_type VARCHAR(64),
    warning_level VARCHAR(32),
    is_halted BOOLEAN NOT NULL DEFAULT FALSE,
    is_under_management BOOLEAN NOT NULL DEFAULT FALSE,
    source_url TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trade_date, code)
);

CREATE TABLE IF NOT EXISTS daily_candidate_scores (
    score_date DATE NOT NULL,
    code VARCHAR(12) NOT NULL REFERENCES stock_master(code),
    name VARCHAR(120) NOT NULL,
    sector VARCHAR(120) NOT NULL,
    total_score NUMERIC(5, 2) NOT NULL,
    liquidity_score NUMERIC(5, 2) NOT NULL,
    close_strength_score NUMERIC(5, 2) NOT NULL,
    catalyst_score NUMERIC(5, 2) NOT NULL,
    sector_score NUMERIC(5, 2) NOT NULL,
    continuity_score NUMERIC(5, 2) NOT NULL,
    risk_penalty NUMERIC(5, 2) NOT NULL,
    reasons_json JSONB NOT NULL,
    risk_flags_json JSONB NOT NULL,
    news_links_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    disclosure_links_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_features_json JSONB NOT NULL,
    price_stats_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    liquidity_stats_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    sector_stats_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    catalyst_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (score_date, code)
);

CREATE TABLE IF NOT EXISTS backtest_summaries (
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    top10_hit_rate NUMERIC(8, 4) NOT NULL,
    median_max_return NUMERIC(8, 4) NOT NULL,
    false_positive_rate NUMERIC(8, 4) NOT NULL,
    sector_concentration NUMERIC(8, 4) NOT NULL,
    warning_hit_rate NUMERIC(8, 4) NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (start_date, end_date)
);

CREATE TABLE IF NOT EXISTS daily_top_score_picks (
    pick_date DATE PRIMARY KEY,
    code VARCHAR(12) NOT NULL REFERENCES stock_master(code),
    name VARCHAR(120) NOT NULL,
    sector VARCHAR(120) NOT NULL,
    total_score NUMERIC(5, 2) NOT NULL,
    base_close NUMERIC(18, 4) NOT NULL,
    reasons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_flags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_candidate_scores_score_date
    ON daily_candidate_scores (score_date, total_score DESC);

CREATE INDEX IF NOT EXISTS idx_daily_candidate_scores_search_name
    ON daily_candidate_scores (score_date, name);

CREATE INDEX IF NOT EXISTS idx_daily_prices_code_date
    ON daily_prices (code, trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_daily_news_code_date
    ON daily_news (code, trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_daily_top_score_picks_pick_date
    ON daily_top_score_picks (pick_date DESC);
