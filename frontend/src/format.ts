export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function qualityLabel(q: string | null | undefined): { text: string; cls: string } {
  switch (q) {
    case "good":
      return { text: "İyi", cls: "q-good" };
    case "partial":
      return { text: "Kısmi", cls: "q-partial" };
    case "conflicting":
      return { text: "Çelişkili", cls: "q-conflict" };
    case "missing":
      return { text: "Eksik", cls: "q-missing" };
    default:
      return { text: "Bilinmiyor", cls: "q-unknown" };
  }
}

export function ageLabel(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${Math.round(seconds)} sn`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m} dk`;
  return `${Math.floor(m / 60)} sa ${m % 60} dk`;
}

export function statusLabel(short: string | null | undefined): string {
  const map: Record<string, string> = {
    "1H": "1. Yarı",
    "2H": "2. Yarı",
    HT: "İlk Yarı Sonu",
    ET: "Uzatma",
    BT: "Uzatma Arası",
    P: "Penaltılar",
    SUSP: "Askıda",
    INT: "Ara",
    "NS": "Başlamadı",
    FT: "Bitti",
    AET: "Uzatma Sonu",
    PEN: "Penaltı Sonu",
  };
  return short ? map[short] ?? short : "—";
}

export function marketLabel(market: string): string {
  const map: Record<string, string> = {
    goal_next_5_min: "Önümüzdeki 5 dk gol",
    goal_next_10_min: "Önümüzdeki 10 dk gol",
    goal_next_15_min: "Önümüzdeki 15 dk gol",
    goal_rest_at_least_one: "Kalan sürede en az 1 gol",
    corner_next_5_min: "Önümüzdeki 5 dk korner",
    corner_next_10_min: "Önümüzdeki 10 dk korner",
    corner_next_15_min: "Önümüzdeki 15 dk korner",
    corner_rest_at_least_one: "Kalan sürede en az 1 korner",
  };
  return map[market] ?? market;
}

export function barWidth(p: number | null | undefined): string {
  if (p === null || p === undefined) return "0%";
  return `${Math.max(0, Math.min(100, p * 100)).toFixed(1)}%`;
}
