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
  ui.py
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

## Database Modes

기본값은 `실데이터 미연결` 모드입니다.

- `DATABASE_URL`이 있으면 PostgreSQL repository 사용
- `DATABASE_URL`이 없으면 샘플 데이터는 절대 쓰지 않고 빈 저장소로 동작
- 따라서 실데이터가 적재되기 전에는 후보/검색 화면에 결과가 표시되지 않습니다

예시:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/domestic_stock_mvp
POSTGRES_ADMIN_URL=postgresql://postgres:postgres@localhost:5432/postgres
KIS_BASE_URL=https://openapi.koreainvestment.com:9443
KIS_TOKEN_PATH=/oauth2/tokenP
KIS_APP_KEY=
KIS_APP_SECRET=
KIS_DAILY_PRICE_API_PATH=/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice
KIS_DAILY_PRICE_TR_ID=FHKST03010100
KIS_CUSTOMER_TYPE=P
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

## Korea Investment Open API

국내주식 일봉 시세는 한국투자 Open API 경로를 기준으로 연결할 수 있습니다.

실행:

```bash
python -m app.scripts.load_kis_daily_prices --code 005930 --from-date 20260401 --to-date 20260424
python -m app.scripts.check_db
```

필요한 환경변수:

- `KIS_APP_KEY`
- `KIS_APP_SECRET`
- `KIS_BASE_URL`
- `KIS_TOKEN_PATH`
- `KIS_DAILY_PRICE_API_PATH`
- `KIS_DAILY_PRICE_TR_ID`

공식 참고:

- 한국투자 Open API 포털: https://apiportal.koreainvestment.com/
- 공식 예제 저장소: https://github.com/koreainvestment/open-trading-api

참고:

- 현재 스크립트는 일봉 시세 적재에 집중한 최소 구현입니다.
- `KIS_DAILY_PRICE_TR_ID`와 요청 파라미터는 한국투자 공식 예제 기준으로 맞췄고, 계정 유형에 따라 조정이 필요하면 `.env`에서 바꿀 수 있게 열어뒀습니다.

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
