export const numberFormatter = new Intl.NumberFormat("ko-KR");
export const compactFormatter = new Intl.NumberFormat("ko-KR", {
  notation: "compact",
  maximumFractionDigits: 1,
});

export const scoreMaxValues = {
  liquidityScore: 25,
  closeStrengthScore: 20,
  catalystScore: 20,
  sectorScore: 15,
  continuityScore: 10,
  riskPenalty: 35,
  totalScore: 100,
};

export function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export function parseIsoDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function formatIsoDate(value: Date) {
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, "0");
  const day = `${value.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function formatMonthLabel(value: string) {
  const date = parseIsoDate(`${value}-01`);
  return `${date.getFullYear()}.${`${date.getMonth() + 1}`.padStart(2, "0")}`;
}

export function shiftMonth(value: string, amount: number) {
  const date = parseIsoDate(`${value}-01`);
  date.setMonth(date.getMonth() + amount);
  return formatIsoDate(date).slice(0, 7);
}

export function buildCalendarCells(monthValue: string) {
  const first = parseIsoDate(`${monthValue}-01`);
  const startDay = first.getDay();
  const daysInMonth = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
  const cells: Array<{ iso: string; day: number } | null> = [];
  for (let index = 0; index < startDay; index += 1) {
    cells.push(null);
  }
  for (let day = 1; day <= daysInMonth; day += 1) {
    const date = new Date(first.getFullYear(), first.getMonth(), day);
    cells.push({ iso: formatIsoDate(date), day });
  }
  return cells;
}

export function formatScore(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "-";
  return value.toFixed(2);
}

export function formatScoreWithMax(value: number | null | undefined, maxValue: number, options?: { penalty?: boolean }) {
  if (value == null || Number.isNaN(value)) return `- / ${maxValue}`;
  const displayValue = options?.penalty ? Math.abs(value) : value;
  return `${displayValue.toFixed(2)} / ${maxValue}`;
}

export function formatRatio(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "-";
  return `x${value.toFixed(2)}`;
}

export function formatPercent(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "-";
  return `${value.toFixed(2)}%`;
}

export function formatMoney(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "-";
  return `${compactFormatter.format(value)}원`;
}

export function formatPrice(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "-";
  return `${numberFormatter.format(Math.round(value))}원`;
}

export function formatPoint(value: number | null | undefined) {
  if (value == null || Number.isNaN(value) || value <= 0) return "-";
  return `${numberFormatter.format(Number(value.toFixed(2)))}pt`;
}

export function formatSector(value: string | null | undefined) {
  const normalized = (value || "").trim();
  if (!normalized || normalized === "Unclassified") return "미분류";
  return normalized;
}

export function profileLabel(value: string | null | undefined) {
  if (value === "surge") return "급등형";
  if (value === "pullback") return "눌림형";
  if (value === "trend") return "추세형";
  return "안정형";
}

export function changeClassName(value: number | null | undefined) {
  if (value == null || Number.isNaN(value) || value === 0) return "flat";
  return value > 0 ? "up" : "down";
}

export function marketChangeClassName(value: number | null | undefined) {
  if (value == null || Number.isNaN(value) || value === 0) return "flat";
  return value > 0 ? "market-up" : "market-down";
}

export function regimeLabel(value: string | null | undefined) {
  if (value === "bear") return "하락장";
  if (value === "weak") return "약세";
  if (value === "strong") return "강세";
  return "중립";
}

export function trendLabel(value: string | null | undefined) {
  if (value === "up") return "상승";
  if (value === "down") return "하락";
  return "중립";
}

export function trendSymbol(value: string | null | undefined) {
  if (value === "up") return "상승";
  if (value === "down") return "하락";
  return "중립";
}

export function naverChartLink(code: string) {
  return `https://finance.naver.com/item/main.naver?code=${encodeURIComponent(code)}`;
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      message = payload.detail || message;
    } catch {
      message = await response.text();
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function fetchJsonWithTimeout<T>(path: string, timeoutMs = 8000): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, { cache: "no-store", signal: controller.signal });
    if (!response.ok) {
      let message = `${response.status} ${response.statusText}`;
      try {
        const payload = (await response.json()) as { detail?: string };
        message = payload.detail || message;
      } catch {
        message = await response.text();
      }
      throw new Error(message);
    }
    return response.json() as Promise<T>;
  } catch (requestError) {
    if (requestError instanceof DOMException && requestError.name === "AbortError") {
      throw new Error("차트 요청 시간이 초과되었습니다.");
    }
    throw requestError;
  } finally {
    window.clearTimeout(timeout);
  }
}
