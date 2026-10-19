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
  const fixed: Record<string, string> = {
    goal_next_5_min: "Önümüzdeki 5 dk gol",
    goal_next_10_min: "Önümüzdeki 10 dk gol",
    goal_next_15_min: "Önümüzdeki 15 dk gol",
    goal_rest_at_least_one: "Kalan sürede en az 1 gol",
    goal_home_rest: "Kalan sürede ev golü",
    goal_away_rest: "Kalan sürede deplasman golü",
    goal_next_home: "Sonraki gol: Ev",
    goal_next_away: "Sonraki gol: Dep",
    goal_btts: "Karşılıklı gol (KG)",
    corner_next_5_min: "Önümüzdeki 5 dk korner",
    corner_next_10_min: "Önümüzdeki 10 dk korner",
    corner_next_15_min: "Önümüzdeki 15 dk korner",
    corner_rest_at_least_one: "Kalan sürede en az 1 korner",
    corner_next_home: "Sonraki korner: Ev",
    corner_next_away: "Sonraki korner: Dep",
    corner_home_next_10_min: "10 dk içinde ev korneri",
    corner_away_next_10_min: "10 dk içinde dep korneri",
  };
  if (fixed[market]) return fixed[market];

  const over = market.match(/^goals_total_over_(\d+)_(\d+)$/);
  if (over) return `Toplam ${over[1]}.${over[2]} Üst`;
  const homeOver = market.match(/^goals_home_over_(\d+)_(\d+)$/);
  if (homeOver) return `Ev ${homeOver[1]}.${homeOver[2]} Üst`;
  const awayOver = market.match(/^goals_away_over_(\d+)_(\d+)$/);
  if (awayOver) return `Dep ${awayOver[1]}.${awayOver[2]} Üst`;
  const cTotal = market.match(/^corners_total_over_(\d+)_(\d+)$/);
  if (cTotal) return `Korner ${cTotal[1]}.${cTotal[2]} Üst`;
  const cHome = market.match(/^corners_home_over_(\d+)_(\d+)$/);
  if (cHome) return `Ev korner ${cHome[1]}.${cHome[2]} Üst`;
  const cAway = market.match(/^corners_away_over_(\d+)_(\d+)$/);
  if (cAway) return `Dep korner ${cAway[1]}.${cAway[2]} Üst`;
  return market;
}

export function barWidth(p: number | null | undefined): string {
  if (p === null || p === undefined) return "0%";
  return `${Math.max(0, Math.min(100, p * 100)).toFixed(1)}%`;
}
