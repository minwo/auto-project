# Domestic Stock MVP Scaffold

국내증시 `내일 주목 후보 선별기` MVP의 백엔드 스캐폴드입니다.

현재 포함된 내용:

- EOD 기반 종목 스냅샷 도메인 모델
- 룰 + 가중치 기반 점수 엔진
- `Top 10`, `섹터당 최대 3종목`, `60점 미만 제외` 규칙
- 후보 검색/상세 조회용 API와 웹 대시보드
- PostgreSQL 도입을 위한 DB 스키마와 DB repository 뼈대
- 핵심 점수 규칙 테스트

## Project Layout

```text
app/
  domain.py
  main.py
  postgres_repository.py
  repository.py
  scoring.py
  settings.py
docs/
  implementation-notes.md
  실데이터-연동-상세계획.md
sql/
  schema.sql
tests/
  test_app_endpoints.py
  test_scoring.py
```

## Local Run

```bash
pip install -e .[dev]
uvicorn app.main:app --reload
pytest
```

## Next.js Frontend

FastAPI 백엔드를 `8000`번 포트에 띄운 뒤 Next.js 프론트엔드를 실행합니다.

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
cd frontend
npm install
npm run dev
```

브라우저에서 `http://127.0.0.1:3000`을 열면 반응형 후보 대시보드를 볼 수 있습니다. Next.js는 `/api/*` 요청을 기본적으로 `http://127.0.0.1:8000`으로 프록시합니다. 다른 백엔드 주소를 쓰려면 `NEXT_PUBLIC_API_BASE_URL`을 설정하세요.

## Database Modes

기본값은 `실데이터 미연결` 모드입니다.

- `DATABASE_URL`이 있으면 PostgreSQL repository 사용
- `DATABASE_URL`이 없으면 샘플 데이터는 절대 쓰지 않고 빈 저장소로 동작
- 따라서 실데이터가 적재되기 전에는 후보/검색 화면에 결과가 표시되지 않습니다

예시:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/domestic_stock_mvp
POSTGRES_ADMIN_URL=postgresql://postgres:postgres@localhost:5432/postgres
KIWOOM_BASE_URL=https://api.kiwoom.com
KIWOOM_TOKEN_PATH=/oauth2/token
KIWOOM_APP_KEY=
KIWOOM_SECRET_KEY=
KIWOOM_DAILY_CHART_API_PATH=/api/dostk/chart
KIWOOM_DAILY_CHART_API_ID=ka10081
KIWOOM_DAILY_CHART_DATE_FIELD=base_dt
KIWOOM_DAILY_CHART_QUERY_TYPE_FIELD=
KIWOOM_DAILY_CHART_QUERY_TYPE=
KIWOOM_DAILY_CHART_ADJUSTED_PRICE_FIELD=upd_stkpc_tp
KIWOOM_DAILY_CHART_ADJUSTED_PRICE=1
KIWOOM_EXCHANGE_SUFFIX=
```

테이블 생성은 [sql/schema.sql](/D:/git/auto-project/sql/schema.sql:1)을 사용하면 됩니다.

## PostgreSQL Quick Start

### Option A. Local PostgreSQL already installed

1. `.env.example`를 참고해 `.env` 생성
2. `DATABASE_URL`, `POSTGRES_ADMIN_URL` 설정
3. 아래 실행

```bash
python -m app.scripts.init_db
python -m app.scripts.check_db
```

## First Real Data Load

현재 DB는 준비만 된 상태라 테이블 건수가 `0`입니다.

첫 실데이터 경로는 `stock_master` 적재입니다.

필요한 값:

- `DATA_GO_KR_SERVICE_KEY`
- `KRX_MASTER_API_URL`

실행:

```bash
python -m app.scripts.load_krx_master
python -m app.scripts.check_db
```

## Kiwoom REST API

국내주식 일봉 시세는 키움 REST API 경로를 기준으로 연결할 수 있습니다.

실행:

```bash
python -m app.scripts.load_kiwoom_daily_prices --code 005930 --date 20260429
python -m app.scripts.check_db
```

여러 종목을 한 번에 적재하려면 다음 스크립트를 사용합니다.

```bash
python -m app.scripts.load_kiwoom_daily_prices_many --codes 005930,000660,035420 --date 20260429
python -m app.scripts.load_kiwoom_daily_prices_many --codes-file data/stock_codes.txt --date 20260429
python -m app.scripts.load_kiwoom_daily_prices_many --from-master --market KOSPI --market KOSDAQ --limit 100 --date 20260429
```

`--codes-file`은 공백, 쉼표, `#` 주석을 허용합니다. `--from-master`는 `stock_master`의 보통주 유니버스를 읽어 `daily_prices`에 순차 적재합니다.
공공데이터 마스터 승인 전에는 코드 파일의 주석을 종목명으로 동기화할 수 있습니다.

```bash
python -m app.scripts.sync_stock_names_from_codes --file data/stock_codes.txt
```

필요한 환경변수:

- `KIWOOM_APP_KEY`
- `KIWOOM_SECRET_KEY`
- `KIWOOM_BASE_URL`
- `KIWOOM_TOKEN_PATH`
- `KIWOOM_DAILY_CHART_API_PATH`
- `KIWOOM_DAILY_CHART_API_ID`

공식 참고:

- 키움 REST API 포털: https://openapi.kiwoom.com/
- 키움 API 가이드: https://openapi.kiwoom.com/guide/apiguide
- 키움 모바일 가이드: https://openapi.kiwoom.com/m/guide/apiguide

참고:

- 현재 스크립트는 일봉 시세 적재에 집중한 최소 구현입니다.
- 키움 차트 API는 `POST /api/dostk/chart`, 토큰 API는 `POST /oauth2/token`을 사용합니다.
- `KIWOOM_DAILY_CHART_*` 필드는 계정 환경에 맞게 `.env`에서 조정할 수 있게 열어뒀습니다.

## Daily Batch

`daily_prices`에 실데이터가 적재된 뒤에는 점수 배치를 별도로 실행할 수 있습니다.

```bash
python -m app.scripts.run_daily_batch --date 2026-04-24
python -m app.scripts.run_daily_batch --date 2026-04-24 --min-score 30 --limit 10
python -m app.scripts.check_db
```

동작:

- `daily_prices` 최근 이력으로 20일 평균 거래대금/거래량 계산
- 3거래일 수익률, 종가 강도, 섹터 동조성 계산
- 같은 날짜의 `daily_disclosures`, `daily_market_warnings`가 있으면 촉매/리스크 반영
- 결과를 `daily_candidate_scores`에 저장

## Open DART Disclosures

공시 촉매 점수를 반영하려면 먼저 DART 고유번호를 종목 마스터에 매핑한 뒤 날짜별 공시를 적재합니다.

```bash
python -m app.scripts.load_dart_corp_codes
python -m app.scripts.load_dart_disclosures --date 2026-04-29
python -m app.scripts.run_daily_batch --date 2026-04-29 --min-score 30
```

필요한 환경변수:

- `DART_API_KEY`

`load_dart_corp_codes`는 Open DART `corpCode.xml`을 받아 `stock_master.dart_corp_code`를 업데이트합니다. `load_dart_disclosures`는 해당 날짜의 공시 목록을 받아 현재 `stock_master`에 존재하는 종목만 `daily_disclosures`에 저장합니다.

관련 공식 참고:

- 공공데이터포털 `금융위원회_KRX상장종목정보`
  - https://www.data.go.kr/data/15094775/openapi.do

주의:

- 이 데이터는 공식 설명상 기준일 다음 영업일 오후 1시 이후 반영될 수 있습니다.
- 따라서 `상장종목 마스터`와 `보조 검증`에는 적합하지만, `당일 장마감 직후 시세` 소스로는 쓰지 않습니다.

### Option B. Docker 사용 가능할 때

```bash
docker compose -f docker-compose.postgres.yml up -d
python -m app.scripts.init_db
python -m app.scripts.check_db
```

`docker`가 설치되어 있지 않다면 Option A로 진행하면 됩니다.

## Available Endpoints

- `GET /`
- `GET /health`
- `GET /api/system/status`
- `GET /api/candidates/daily?date=YYYY-MM-DD`
- `GET /api/stocks/search?date=YYYY-MM-DD&q=keyword`
- `GET /api/stocks/{code}/signal-summary?date=YYYY-MM-DD`
- `GET /api/backtests/summary?from=YYYY-MM-DD&to=YYYY-MM-DD`

## Current Status

현재는 `DB가 있으면 PostgreSQL`, `DB가 없으면 빈 상태` 구조로 연결되어 있습니다.

아직 남아 있는 주요 작업:

1. `stock_master`, `daily_prices`에 실제 데이터 적재
2. 시세 수집기 구현
3. DART 공시 수집기 구현
4. 배치에서 `daily_candidate_scores` 생성
5. UI를 실데이터 기반으로 전환
