from __future__ import annotations

from html import escape


def render_dashboard_html(initial_date: str) -> str:
    safe_date = escape(initial_date)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>국내증시 주목 후보 대시보드</title>
  <style>
    :root {{
      --bg: #f6efe6;
      --bg-strong: #f0e2d2;
      --surface: rgba(255, 252, 247, 0.88);
      --surface-strong: #fffaf3;
      --text: #1d2733;
      --muted: #6c7785;
      --line: rgba(29, 39, 51, 0.12);
      --accent: #e06a3f;
      --accent-deep: #b64921;
      --accent-soft: #ffe1d3;
      --good: #147a5b;
      --warn: #b45309;
      --danger: #b42318;
      --shadow: 0 18px 60px rgba(79, 50, 27, 0.12);
      --radius-xl: 28px;
      --radius-lg: 20px;
      --radius-md: 16px;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      color: var(--text);
      font-family: "Pretendard Variable", "Noto Sans KR", "Segoe UI Variable Text", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(224, 106, 63, 0.16), transparent 28%),
        radial-gradient(circle at top right, rgba(20, 122, 91, 0.14), transparent 24%),
        linear-gradient(180deg, #fffaf4 0%, var(--bg) 60%, #efe4d7 100%);
      min-height: 100vh;
    }}

    a {{
      color: inherit;
    }}

    .page {{
      width: min(1280px, calc(100% - 24px));
      margin: 0 auto;
      padding: 24px 0 48px;
    }}

    .hero {{
      position: relative;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.45);
      border-radius: 32px;
      background:
        linear-gradient(135deg, rgba(255, 250, 243, 0.94), rgba(247, 237, 224, 0.9)),
        linear-gradient(120deg, rgba(224, 106, 63, 0.12), rgba(20, 122, 91, 0.1));
      box-shadow: var(--shadow);
      padding: 28px;
    }}

    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -60px -70px auto;
      width: 220px;
      height: 220px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(224, 106, 63, 0.24), rgba(224, 106, 63, 0));
      pointer-events: none;
    }}

    .eyebrow {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.7);
      color: var(--accent-deep);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}

    .hero h1 {{
      margin: 16px 0 12px;
      font-size: clamp(32px, 5vw, 58px);
      line-height: 0.96;
      letter-spacing: -0.04em;
      max-width: 820px;
    }}

    .hero p {{
      margin: 0;
      max-width: 760px;
      font-size: 16px;
      line-height: 1.65;
      color: var(--muted);
    }}

    .hero-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.95fr);
      gap: 24px;
      align-items: end;
    }}

    .hero-panel {{
      border-radius: 24px;
      padding: 20px;
      background: rgba(255, 255, 255, 0.62);
      border: 1px solid rgba(255, 255, 255, 0.48);
      backdrop-filter: blur(10px);
    }}

    .notice {{
      display: grid;
      gap: 10px;
    }}

    .notice strong {{
      font-size: 14px;
    }}

    .notice span {{
      color: var(--muted);
      font-size: 14px;
      line-height: 1.5;
    }}

    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }}

    .stat {{
      background: var(--surface);
      border: 1px solid rgba(255, 255, 255, 0.55);
      border-radius: var(--radius-lg);
      padding: 18px;
      box-shadow: 0 10px 30px rgba(69, 41, 21, 0.08);
    }}

    .stat-label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 10px;
    }}

    .stat-value {{
      font-size: clamp(22px, 3vw, 34px);
      font-weight: 800;
      letter-spacing: -0.04em;
    }}

    .stat-sub {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
    }}

    .controls {{
      display: grid;
      grid-template-columns: 180px minmax(0, 1fr) auto;
      gap: 12px;
      margin: 24px 0 18px;
      padding: 14px;
      background: rgba(255, 250, 243, 0.78);
      border: 1px solid rgba(255, 255, 255, 0.55);
      border-radius: 24px;
      box-shadow: 0 10px 30px rgba(69, 41, 21, 0.08);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 14px;
      z-index: 10;
    }}

    .input-wrap {{
      display: grid;
      gap: 8px;
    }}

    .input-wrap label {{
      font-size: 12px;
      color: var(--muted);
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}

    .field {{
      width: 100%;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.82);
      color: var(--text);
      border-radius: 16px;
      padding: 14px 16px;
      font-size: 15px;
      outline: none;
      transition: border-color 120ms ease, transform 120ms ease, box-shadow 120ms ease;
    }}

    .field:focus {{
      border-color: rgba(224, 106, 63, 0.48);
      box-shadow: 0 0 0 4px rgba(224, 106, 63, 0.12);
      transform: translateY(-1px);
    }}

    .button {{
      border: none;
      border-radius: 16px;
      padding: 0 18px;
      background: linear-gradient(135deg, var(--accent), var(--accent-deep));
      color: white;
      font-weight: 800;
      font-size: 15px;
      cursor: pointer;
      min-height: 54px;
      box-shadow: 0 14px 28px rgba(180, 73, 33, 0.24);
    }}

    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
      gap: 18px;
      align-items: start;
    }}

    .panel {{
      background: var(--surface);
      border: 1px solid rgba(255, 255, 255, 0.55);
      border-radius: 28px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}

    .panel-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 18px 22px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.46);
    }}

    .panel-title {{
      font-size: 18px;
      font-weight: 800;
      letter-spacing: -0.03em;
    }}

    .panel-subtitle {{
      color: var(--muted);
      font-size: 13px;
    }}

    .result-list {{
      display: grid;
      gap: 14px;
      padding: 18px;
      max-height: 920px;
      overflow: auto;
    }}

    .card {{
      position: relative;
      border: 1px solid rgba(29, 39, 51, 0.08);
      background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(255,250,244,0.88));
      border-radius: 22px;
      padding: 18px;
      cursor: pointer;
      transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
    }}

    .card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 18px 28px rgba(69, 41, 21, 0.08);
      border-color: rgba(224, 106, 63, 0.28);
    }}

    .card.active {{
      border-color: rgba(224, 106, 63, 0.44);
      box-shadow: 0 18px 40px rgba(180, 73, 33, 0.14);
    }}

    .card-top {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 14px;
    }}

    .stock-name {{
      font-size: 20px;
      font-weight: 800;
      letter-spacing: -0.03em;
    }}

    .stock-code {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }}

    .score-pill {{
      min-width: 72px;
      padding: 10px 12px;
      border-radius: 18px;
      background: linear-gradient(135deg, rgba(224, 106, 63, 0.12), rgba(224, 106, 63, 0.22));
      color: var(--accent-deep);
      text-align: center;
      font-weight: 800;
    }}

    .score-pill small {{
      display: block;
      font-size: 11px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}

    .meta-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }}

    .tag {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 11px;
      border-radius: 999px;
      background: rgba(29, 39, 51, 0.05);
      color: var(--text);
      font-size: 12px;
      font-weight: 700;
    }}

    .tag.risk {{
      background: rgba(180, 35, 24, 0.1);
      color: var(--danger);
    }}

    .tag.good {{
      background: rgba(20, 122, 91, 0.1);
      color: var(--good);
    }}

    .reason-list,
    .flag-list,
    .link-list,
    .metric-list {{
      display: grid;
      gap: 10px;
      padding: 0;
      list-style: none;
      margin: 0;
    }}

    .reason-list li,
    .flag-list li,
    .link-list a,
    .metric-card {{
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.76);
      border: 1px solid rgba(29, 39, 51, 0.08);
      padding: 12px 14px;
    }}

    .flag-list li {{
      border-color: rgba(180, 35, 24, 0.14);
      background: rgba(180, 35, 24, 0.05);
      color: var(--danger);
    }}

    .detail {{
      position: sticky;
      top: 108px;
    }}

    .detail-body {{
      padding: 22px;
      display: grid;
      gap: 18px;
    }}

    .detail-hero {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: start;
    }}

    .detail-name {{
      font-size: clamp(24px, 4vw, 38px);
      font-weight: 800;
      letter-spacing: -0.04em;
      margin: 0 0 6px;
    }}

    .detail-code {{
      color: var(--muted);
      font-size: 14px;
    }}

    .score-ring {{
      width: 110px;
      aspect-ratio: 1;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background:
        radial-gradient(circle at center, var(--surface-strong) 55%, transparent 56%),
        conic-gradient(var(--accent) calc(var(--score) * 1%), rgba(29, 39, 51, 0.08) 0);
      box-shadow: inset 0 0 0 8px rgba(255, 255, 255, 0.38);
    }}

    .score-ring strong {{
      display: block;
      text-align: center;
      font-size: 28px;
      line-height: 1;
      letter-spacing: -0.05em;
    }}

    .score-ring span {{
      display: block;
      margin-top: 2px;
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    .section {{
      display: grid;
      gap: 12px;
    }}

    .section h3 {{
      margin: 0;
      font-size: 14px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--muted);
    }}

    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}

    .metric-card strong {{
      display: block;
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 8px;
    }}

    .metric-card span {{
      font-size: 26px;
      font-weight: 800;
      letter-spacing: -0.04em;
    }}

    .link-list a {{
      text-decoration: none;
      color: var(--text);
      display: flex;
      justify-content: space-between;
      gap: 12px;
    }}

    .link-list a::after {{
      content: "↗";
      color: var(--accent-deep);
      font-weight: 800;
    }}

    .empty {{
      padding: 36px 18px;
      text-align: center;
      color: var(--muted);
      font-size: 15px;
    }}

    .status {{
      color: var(--muted);
      font-size: 13px;
    }}

    .skeleton {{
      height: 96px;
      border-radius: 22px;
      background: linear-gradient(90deg, rgba(29,39,51,0.05), rgba(29,39,51,0.08), rgba(29,39,51,0.05));
      background-size: 200% 100%;
      animation: shimmer 1.2s infinite linear;
    }}

    @keyframes shimmer {{
      from {{ background-position: 200% 0; }}
      to {{ background-position: -200% 0; }}
    }}

    @media (max-width: 1080px) {{
      .hero-grid,
      .layout {{
        grid-template-columns: 1fr;
      }}

      .detail {{
        position: static;
      }}
    }}

    @media (max-width: 760px) {{
      .page {{
        width: min(100% - 16px, 100%);
        padding-top: 16px;
      }}

      .hero {{
        padding: 20px;
        border-radius: 24px;
      }}

      .controls {{
        grid-template-columns: 1fr;
        top: 8px;
      }}

      .stats {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}

      .panel,
      .card {{
        border-radius: 22px;
      }}

      .detail-hero {{
        flex-direction: column;
      }}

      .metric-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="hero-grid">
        <div>
          <div class="eyebrow">Domestic Stock MVP · 내일 주목 후보</div>
          <h1>종목을 검색하고, 선정 이유와 위험 신호를 한 화면에서 확인하세요.</h1>
          <p>
            이 화면은 매수 추천이 아니라 내일 관심 있게 볼 후보를 설명 가능한 형태로 좁혀주는 대시보드입니다.
            검색창에서 종목명, 코드, 섹터를 입력하면 후보 목록을 찾고 세부 점수를 바로 확인할 수 있습니다.
          </p>
        </div>
        <div class="hero-panel notice">
          <div>
            <strong>투자 판단 책임 고지</strong>
            <span>이 서비스는 참고용 후보 선별 화면이며 수익을 보장하지 않습니다. 최종 투자 판단과 책임은 사용자에게 있습니다.</span>
          </div>
          <div>
            <strong>지연 시세 여부</strong>
            <span>실데이터가 적재된 경우에만 후보가 표시됩니다. 실시간 체결이나 자동매매 기능은 포함하지 않습니다.</span>
          </div>
          <div>
            <strong>마지막 배치 기준일</strong>
            <span id="latest-batch-text">{safe_date}</span>
          </div>
        </div>
      </div>

      <div class="stats">
        <div class="stat">
          <span class="stat-label">기준일</span>
          <div class="stat-value" id="stat-date">{safe_date}</div>
          <div class="stat-sub">가장 최근 배치된 후보 일자</div>
        </div>
        <div class="stat">
          <span class="stat-label">검색 결과</span>
          <div class="stat-value" id="stat-results">-</div>
          <div class="stat-sub">현재 조건으로 보이는 종목 수</div>
        </div>
        <div class="stat">
          <span class="stat-label">상위 점수</span>
          <div class="stat-value" id="stat-top-score">-</div>
          <div class="stat-sub">현재 결과 중 최고 점수</div>
        </div>
        <div class="stat">
          <span class="stat-label">마지막 갱신</span>
          <div class="stat-value" id="stat-generated">-</div>
          <div class="stat-sub">EOD 배치 생성 시각</div>
        </div>
      </div>
    </section>

    <section class="controls">
      <div class="input-wrap">
        <label for="date-input">기준일</label>
        <input id="date-input" class="field" type="date" value="{safe_date}">
      </div>
      <div class="input-wrap">
        <label for="search-input">종목 검색</label>
        <input id="search-input" class="field" type="search" placeholder="종목명, 코드, 섹터, 이유 키워드">
      </div>
      <div class="input-wrap">
        <label>&nbsp;</label>
        <button id="refresh-button" class="button" type="button">화면 새로 조회</button>
      </div>
    </section>

    <section class="layout">
      <article class="panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">검색 결과</div>
            <div class="panel-subtitle">후보 카드에서 종목을 선택하면 오른쪽에 상세가 열립니다.</div>
          </div>
          <div id="result-status" class="status">불러오는 중</div>
        </div>
        <div id="result-list" class="result-list">
          <div class="skeleton"></div>
          <div class="skeleton"></div>
          <div class="skeleton"></div>
        </div>
      </article>

      <aside class="panel detail">
        <div class="panel-header">
          <div>
            <div class="panel-title">종목 상세</div>
            <div class="panel-subtitle">선정 이유, 리스크, 세부 점수</div>
          </div>
          <div id="detail-status" class="status">대기 중</div>
        </div>
        <div id="detail-body" class="detail-body">
          <div class="empty">왼쪽에서 종목을 선택하면 상세 정보가 여기에 표시됩니다.</div>
        </div>
      </aside>
    </section>
  </div>

  <script>
    const state = {{
      initialDate: "{safe_date}",
      generatedAt: "",
      selectedCode: "",
      query: "",
      results: [],
      topCandidates: [],
    }};

    const els = {{
      dateInput: document.getElementById("date-input"),
      searchInput: document.getElementById("search-input"),
      refreshButton: document.getElementById("refresh-button"),
      resultList: document.getElementById("result-list"),
      detailBody: document.getElementById("detail-body"),
      resultStatus: document.getElementById("result-status"),
      detailStatus: document.getElementById("detail-status"),
      statDate: document.getElementById("stat-date"),
      statResults: document.getElementById("stat-results"),
      statTopScore: document.getElementById("stat-top-score"),
      statGenerated: document.getElementById("stat-generated"),
      latestBatchText: document.getElementById("latest-batch-text"),
    }};

    function formatShortDate(value) {{
      if (!value) return "-";
      return value;
    }}

    function formatGeneratedAt(value) {{
      if (!value) return "-";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return date.toLocaleString("ko-KR", {{
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }});
    }}

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }}

    function updateStats() {{
      const topScore = state.results.length ? Math.max(...state.results.map((item) => item.score)) : null;
      els.statDate.textContent = formatShortDate(els.dateInput.value);
      els.statResults.textContent = String(state.results.length);
      els.statTopScore.textContent = topScore == null ? "-" : topScore.toFixed(2);
      els.statGenerated.textContent = formatGeneratedAt(state.generatedAt);
      els.latestBatchText.textContent = formatShortDate(els.dateInput.value);
    }}

    function renderResults() {{
      if (!state.results.length) {{
        els.resultList.innerHTML = '<div class="empty">검색 결과가 없습니다. 코드나 종목명, 섹터 키워드를 바꿔보세요.</div>';
        updateStats();
        return;
      }}

      const topCodes = new Set(state.topCandidates.map((item) => item.code));
      els.resultList.innerHTML = state.results.map((item) => {{
        const reasons = (item.reasons || []).map((reason) => `<li>${{escapeHtml(reason)}}</li>`).join("");
        const riskFlags = (item.riskFlags || []).map((flag) => `<span class="tag risk">${{escapeHtml(flag)}}</span>`).join("");
        return `
          <article class="card ${{state.selectedCode === item.code ? "active" : ""}}" data-code="${{escapeHtml(item.code)}}">
            <div class="card-top">
              <div>
                <div class="stock-name">${{escapeHtml(item.name)}}</div>
                <div class="stock-code">${{escapeHtml(item.code)}}</div>
              </div>
              <div class="score-pill">
                <small>Score</small>
                <div>${{Number(item.score).toFixed(2)}}</div>
              </div>
            </div>
            <div class="meta-row">
              <span class="tag">${{escapeHtml(item.sector)}}</span>
              <span class="tag good">거래대금 x${{Number(item.turnoverRatio20d).toFixed(1)}}</span>
              <span class="tag">3일 수익률 ${{Number(item.return3dPct).toFixed(1)}}%</span>
              ${{topCodes.has(item.code) ? '<span class="tag">Top 10 포함</span>' : ''}}
              ${{riskFlags}}
            </div>
            <ul class="reason-list">${{reasons || '<li>선정 이유가 아직 없습니다.</li>'}}</ul>
          </article>
        `;
      }}).join("");

      document.querySelectorAll(".card").forEach((card) => {{
        card.addEventListener("click", () => {{
          const code = card.getAttribute("data-code");
          if (code) {{
            loadSignalSummary(code);
          }}
        }});
      }});

      updateStats();
    }}

    function renderDetail(summary, code) {{
      const score = Number(summary.componentScores.totalScore || 0);
      const reasons = (summary.reasons || []).map((item) => `<li>${{escapeHtml(item)}}</li>`).join("");
      const riskFlags = (summary.riskFlags || []).length
        ? (summary.riskFlags || []).map((item) => `<li>${{escapeHtml(item)}}</li>`).join("")
        : "<li>현재 별도 위험 신호는 없습니다.</li>";
      const catalysts = (summary.catalystSummary.items || []).length
        ? (summary.catalystSummary.items || []).map((item) => `<a href="${{escapeHtml(item.url)}}" target="_blank" rel="noreferrer">${{escapeHtml(item.title)}}</a>`).join("")
        : '<div class="empty">촉매 항목이 없습니다.</div>';
      const newsLinks = ((summary.rawFeatures.news_links || [])).map((item) => `<a href="${{escapeHtml(item.url)}}" target="_blank" rel="noreferrer">${{escapeHtml(item.title)}}</a>`).join("");
      const disclosureLinks = ((summary.rawFeatures.disclosure_links || [])).map((item) => `<a href="${{escapeHtml(item.url)}}" target="_blank" rel="noreferrer">${{escapeHtml(item.title)}}</a>`).join("");
      const componentScores = summary.componentScores;
      const priceStats = summary.priceStats;
      const liquidityStats = summary.liquidityStats;
      const sectorStats = summary.sectorStats;
      const stock = state.results.find((item) => item.code === code);

      els.detailBody.innerHTML = `
        <div class="detail-hero">
          <div>
            <h2 class="detail-name">${{escapeHtml(stock?.name || code)}}</h2>
            <div class="detail-code">${{escapeHtml(code)}} · ${{escapeHtml(stock?.sector || sectorStats.sector || "-")}}</div>
            <div class="meta-row" style="margin-top:14px;">
              <span class="tag">1~3거래일 관찰용</span>
              <span class="tag">종가 위치 ${{(Number(priceStats.closePosition) * 100).toFixed(0)}}%</span>
              <span class="tag">섹터 동반 ${{escapeHtml(String(sectorStats.risingPeers))}}종목</span>
            </div>
          </div>
          <div class="score-ring" style="--score:${{Math.max(0, Math.min(score, 100))}};">
            <div>
              <strong>${{score.toFixed(1)}}</strong>
              <span>Total Score</span>
            </div>
          </div>
        </div>

        <section class="section">
          <h3>선정 이유</h3>
          <ul class="reason-list">${{reasons}}</ul>
        </section>

        <section class="section">
          <h3>위험 신호</h3>
          <ul class="flag-list">${{riskFlags}}</ul>
        </section>

        <section class="section">
          <h3>세부 점수</h3>
          <div class="metric-grid">
            <div class="metric-card"><strong>유동성</strong><span>${{Number(componentScores.liquidityScore).toFixed(2)}}</span></div>
            <div class="metric-card"><strong>종가 강도</strong><span>${{Number(componentScores.closeStrengthScore).toFixed(2)}}</span></div>
            <div class="metric-card"><strong>촉매</strong><span>${{Number(componentScores.catalystScore).toFixed(2)}}</span></div>
            <div class="metric-card"><strong>섹터</strong><span>${{Number(componentScores.sectorScore).toFixed(2)}}</span></div>
            <div class="metric-card"><strong>연속성</strong><span>${{Number(componentScores.continuityScore).toFixed(2)}}</span></div>
            <div class="metric-card"><strong>리스크 패널티</strong><span>${{Number(componentScores.riskPenalty).toFixed(2)}}</span></div>
          </div>
        </section>

        <section class="section">
          <h3>거래/가격 상태</h3>
          <div class="metric-grid">
            <div class="metric-card"><strong>거래대금 배수</strong><span>x${{Number(liquidityStats.turnoverRatio20d).toFixed(2)}}</span></div>
            <div class="metric-card"><strong>거래량 배수</strong><span>x${{Number(liquidityStats.volumeRatio20d).toFixed(2)}}</span></div>
            <div class="metric-card"><strong>갭상승률</strong><span>${{Number(priceStats.gapUpPct).toFixed(2)}}%</span></div>
            <div class="metric-card"><strong>장중 변동성</strong><span>${{Number(priceStats.intradayRangePct).toFixed(2)}}%</span></div>
          </div>
        </section>

        <section class="section">
          <h3>관련 촉매</h3>
          <div class="link-list">${{catalysts}}</div>
        </section>

        <section class="section">
          <h3>뉴스 링크</h3>
          <div class="link-list">${{newsLinks || '<div class="empty">뉴스 링크가 없습니다.</div>'}}</div>
        </section>

        <section class="section">
          <h3>공시 링크</h3>
          <div class="link-list">${{disclosureLinks || '<div class="empty">공시 링크가 없습니다.</div>'}}</div>
        </section>
      `;
    }}

    async function fetchJson(path) {{
      const response = await fetch(path);
      if (!response.ok) {{
        const message = await response.text();
        throw new Error(message || "요청 실패");
      }}
      return response.json();
    }}

    async function loadCandidates() {{
      const date = els.dateInput.value || state.initialDate;
      els.resultStatus.textContent = "목록 불러오는 중";
      const data = await fetchJson(`/api/candidates/daily?date=${{encodeURIComponent(date)}}`);
      state.topCandidates = data.candidates || [];
      state.generatedAt = data.generatedAt || "";
    }}

    async function loadSearch() {{
      const date = els.dateInput.value || state.initialDate;
      const query = els.searchInput.value.trim();
      state.query = query;
      els.resultStatus.textContent = "검색 중";
      const url = `/api/stocks/search?date=${{encodeURIComponent(date)}}&q=${{encodeURIComponent(query)}}`;
      const data = await fetchJson(url);
      state.results = data.results || [];
      els.resultStatus.textContent = `총 ${{state.results.length}}건`;
      renderResults();

      const shouldReplaceSelection = !state.selectedCode || !state.results.some((item) => item.code === state.selectedCode);
      if (shouldReplaceSelection && state.results.length) {{
        await loadSignalSummary(state.results[0].code);
      }}
      if (!state.results.length) {{
        state.selectedCode = "";
        els.detailStatus.textContent = "결과 없음";
        els.detailBody.innerHTML = '<div class="empty">이 조건에 맞는 종목이 없습니다.</div>';
      }}
    }}

    async function loadSignalSummary(code) {{
      const date = els.dateInput.value || state.initialDate;
      state.selectedCode = code;
      renderResults();
      els.detailStatus.textContent = "상세 불러오는 중";
      const data = await fetchJson(`/api/stocks/${{encodeURIComponent(code)}}/signal-summary?date=${{encodeURIComponent(date)}}`);
      els.detailStatus.textContent = "상세 준비됨";
      renderDetail(data, code);
    }}

    async function refreshAll() {{
      try {{
        els.resultList.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
        els.detailBody.innerHTML = '<div class="empty">상세 정보를 불러오는 중입니다.</div>';
        await loadCandidates();
        await loadSearch();
      }} catch (error) {{
        const message = error instanceof Error ? error.message : "알 수 없는 오류";
        els.resultStatus.textContent = "조회 실패";
        els.detailStatus.textContent = "조회 실패";
        els.resultList.innerHTML = `<div class="empty">${{escapeHtml(message)}}</div>`;
        els.detailBody.innerHTML = `<div class="empty">${{escapeHtml(message)}}</div>`;
      }}
    }}

    let debounceHandle = null;
    els.searchInput.addEventListener("input", () => {{
      window.clearTimeout(debounceHandle);
      debounceHandle = window.setTimeout(() => {{
        refreshAll();
      }}, 180);
    }});

    els.refreshButton.addEventListener("click", refreshAll);
    els.dateInput.addEventListener("change", refreshAll);

    refreshAll();
  </script>
</body>
</html>
"""
