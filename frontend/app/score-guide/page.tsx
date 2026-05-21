import { ArrowLeft, BarChart3, ShieldAlert, Sparkles, TrendingUp } from "lucide-react";
import Link from "next/link";

const scoreItems = [
  {
    title: "유동성",
    value: "거래대금과 거래량",
    body: "최근 평균보다 거래가 충분히 붙었는지 봅니다. 너무 약하면 관심도가 낮다고 보고, 지나치게 폭발하면 과열로 감점합니다.",
  },
  {
    title: "종가 강도",
    value: "가격 위치",
    body: "당일 종가가 고가에 가깝게 마감했는지, 장중 변동폭과 윗꼬리가 과하지 않은지 확인합니다.",
  },
  {
    title: "공시·뉴스",
    value: "재료의 질",
    body: "공급계약, 실적, 자사주, 배당, 승인처럼 확인 가능한 긍정 재료는 가점하고, 증자·CB·관리 리스크는 감점합니다.",
  },
  {
    title: "섹터",
    value: "동반 흐름",
    body: "같은 업종에서 함께 오르는 종목이 있는지 봅니다. 혼자만 튄 움직임보다 섹터 전체의 힘을 더 신뢰합니다.",
  },
  {
    title: "연속성",
    value: "3거래일 흐름",
    body: "최근 며칠간의 상승 흐름이 이어지는지 보되, 단기간 급등이 지나치면 추격 위험으로 감점합니다.",
  },
  {
    title: "리스크",
    value: "방어 장치",
    body: "시장 레짐, 투자주의, 거래정지, 관리종목, 불성실공시, 과열 캔들처럼 손실 가능성을 키우는 조건은 총점에서 뺍니다.",
  },
  {
    title: "시간 손절",
    value: "자금 회전",
    body: "선정 뒤 3거래일 안에 의미 있는 움직임이 없으면 횡보로 보고 현금화 기준을 적용합니다.",
  },
];

export default function ScoreGuidePage() {
  return (
    <main className="shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">Score Guide</p>
          <h1>점수 기준</h1>
        </div>
        <Link className="icon-button" href="/">
          <ArrowLeft size={18} />
          <span>검색으로</span>
        </Link>
      </section>

      <section className="guide-hero">
        <div>
          <span className="market-pill">0점부터 100점까지</span>
          <h2>점수는 “내일도 볼 만한가”를 빠르게 걸러내는 기준입니다.</h2>
          <p>
            높은 점수는 유동성, 가격 강도, 재료, 섹터 흐름이 함께 좋다는 뜻입니다. 다만 목표가와 손절가는
            자동 계산된 참고값이며 투자 추천이 아닙니다.
          </p>
        </div>
        <div className="guide-score">
          <span>Total</span>
          <strong>100</strong>
        </div>
      </section>

      <section className="guide-grid">
        {scoreItems.map((item) => (
          <article className="guide-card" key={item.title}>
            <div className="guide-icon">{iconForTitle(item.title)}</div>
            <span>{item.value}</span>
            <h2>{item.title}</h2>
            <p>{item.body}</p>
          </article>
        ))}
      </section>

      <section className="wide-panel guide-note">
        <div className="panel-heading">
          <div>
            <h2>읽는 방법</h2>
            <p>검색 결과의 상세 화면에서 각 항목 점수를 함께 확인할 수 있습니다.</p>
          </div>
          <BarChart3 size={20} />
        </div>
        <div className="guide-steps">
          <div>
            <strong>70점 이상</strong>
            <span>조건이 여러 개 겹친 강한 후보입니다.</span>
          </div>
          <div>
            <strong>60점대</strong>
            <span>볼 만하지만 진입 기준과 리스크 확인이 필요합니다.</span>
          </div>
          <div>
            <strong>60점 미만</strong>
            <span>우선순위를 낮추고 새 데이터가 쌓인 뒤 다시 확인합니다.</span>
          </div>
        </div>
      </section>
    </main>
  );
}

function iconForTitle(title: string) {
  if (title === "리스크") return <ShieldAlert size={20} />;
  if (title === "공시·뉴스") return <Sparkles size={20} />;
  return <TrendingUp size={20} />;
}
