from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import httpx


NAVER_NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"
HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class NaverNewsRecord:
    trade_date: date
    code: str
    news_id: str
    title: str
    url: str
    source: str
    published_at: datetime | None
    summary: str | None
    news_type: str | None
    trust_score: float


POSITIVE_NEWS_RULES: list[tuple[str, list[str]]] = [
    ("contract", ["contract", "supply", "purchase order", "수주", "공급계약", "판매계약", "계약 체결"]),
    ("earnings", ["earnings", "profit", "revenue", "실적", "영업이익", "매출", "흑자전환"]),
    ("approval", ["approval", "license", "clinical", "fda", "승인", "허가", "품목허가", "임상"]),
    ("buyback", ["buyback", "treasury stock", "자사주", "자기주식"]),
    ("dividend", ["dividend", "배당", "현금배당"]),
    ("capex", ["facility", "investment", "capacity", "증설", "공장", "신규시설", "시설투자"]),
    ("corporate_action", ["merger", "acquisition", "m&a", "합병", "인수", "분할"]),
    ("policy", ["policy", "정부", "정책", "지원", "보조금"]),
]

NEGATIVE_NEWS_RULES: list[tuple[str, list[str]]] = [
    ("trading_risk", ["거래정지", "상장폐지", "관리종목", "투자주의", "투자경고", "불성실공시"]),
    ("dilution", ["유상증자", "전환사채", "신주인수권", "cb", "bw", "희석"]),
    ("capital_reduction", ["감자", "자본감소"]),
    ("management_risk", ["횡령", "배임", "소송", "감사의견", "회생", "파산"]),
]

SPECULATIVE_KEYWORDS = ["급등", "상한가", "테마", "관련주", "부각"]


def clean_news_text(value: str | None) -> str:
    if not value:
        return ""
    text = HTML_TAG_RE.sub("", value)
    text = html.unescape(text)
    return " ".join(text.split())


def parse_pub_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def classify_news(title: str, summary: str | None = None) -> tuple[str, float]:
    haystack = f"{title} {summary or ''}".lower()
    for news_type, keywords in NEGATIVE_NEWS_RULES:
        if any(keyword.lower() in haystack for keyword in keywords):
            return news_type, 0.75
    for news_type, keywords in POSITIVE_NEWS_RULES:
        if any(keyword.lower() in haystack for keyword in keywords):
            return news_type, 0.65
    if any(keyword.lower() in haystack for keyword in SPECULATIVE_KEYWORDS):
        return "news", 0.35
    return "news", 0.45


def _source_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or "naver"


def _news_id(*values: str) -> str:
    hasher = hashlib.sha256()
    for value in values:
        hasher.update(value.encode("utf-8", errors="ignore"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def parse_naver_news_payload(
    payload: dict[str, Any],
    *,
    trade_date: date,
    code: str,
    strict_date: bool = True,
) -> list[NaverNewsRecord]:
    records: list[NaverNewsRecord] = []
    seen: set[str] = set()
    for item in payload.get("items") or []:
        title = clean_news_text(str(item.get("title") or ""))
        summary = clean_news_text(str(item.get("description") or ""))
        url = str(item.get("originallink") or item.get("link") or "").strip()
        published_at = parse_pub_date(str(item.get("pubDate") or ""))
        if not title or not url:
            continue
        if strict_date and published_at is not None and published_at.date() != trade_date:
            continue

        news_type, trust_score = classify_news(title, summary)
        news_id = _news_id(code, url, title)
        if news_id in seen:
            continue
        seen.add(news_id)
        records.append(
            NaverNewsRecord(
                trade_date=trade_date,
                code=code,
                news_id=news_id,
                title=title,
                url=url,
                source=_source_from_url(url),
                published_at=published_at,
                summary=summary or None,
                news_type=news_type,
                trust_score=trust_score,
            )
        )
    return records


def fetch_news_records(
    *,
    client_id: str,
    client_secret: str,
    trade_date: date,
    code: str,
    name: str | None = None,
    api_url: str = NAVER_NEWS_API_URL,
    display: int = 10,
    sort: str = "date",
    strict_date: bool = True,
    timeout: float = 15.0,
    client: httpx.Client | None = None,
) -> list[NaverNewsRecord]:
    query = f"{name} {code} 주식" if name else f"{code} 주식"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {
        "query": query,
        "display": max(1, min(display, 100)),
        "start": 1,
        "sort": sort,
    }
    request_client = client or httpx.Client(timeout=timeout)
    close_client = client is None
    try:
        response = request_client.get(api_url, params=params, headers=headers)
        response.raise_for_status()
        return parse_naver_news_payload(
            response.json(),
            trade_date=trade_date,
            code=code,
            strict_date=strict_date,
        )
    finally:
        if close_client:
            request_client.close()
