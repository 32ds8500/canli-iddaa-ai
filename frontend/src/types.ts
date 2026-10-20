export interface LeagueInfo {
  id: string;
  name: string | null;
  country: string | null;
  kind: string | null;
  cov_live_stats: boolean | null;
  cov_corners: boolean | null;
  cov_dangerous_attacks: boolean | null;
  cov_xg: boolean | null;
}

export interface TeamSide {
  id: string;
  name: string | null;
}

export interface SideStats {
  shots_total: number | null;
  shots_on: number | null;
  shots_off: number | null;
  shots_blocked: number | null;
  corners: number | null;
  dangerous_attacks: number | null;
  possession: number | null;
  yellow_cards: number | null;
  red_cards: number | null;
  xg: number | null;
  source: string | null;
  updated_at: string | null;
}

export interface LivePredictions {
  goal_sufficient: boolean;
  corner_sufficient: boolean;
  goal_insufficient_reason: string | null;
  corner_insufficient_reason: string | null;
  goal_confidence: number;
  corner_confidence: number;
  goal: Record<string, number>;
  corner: Record<string, number>;
  baseline: {
    goal_source: string;
    corner_source: string;
    sample_matches: number;
    note: string | null;
  };
  source?: "live" | "history" | "none";
  as_of_minute?: number | null;
}

export interface LiveMatch {
  id: string;
  league: LeagueInfo;
  home: TeamSide;
  away: TeamSide;
  kickoff_at: string | null;
  status: { short: string; long: string | null };
  minute: number | null;
  score: { home: number | null; away: number | null };
  data_quality: string;
  data_age_seconds: number | null;
  last_updated_at: string | null;
  stats: { home: SideStats | null; away: SideStats | null };
  predictions: LivePredictions;
}

export interface PredItem {
  market: string;
  probability: number;
  horizon_minutes: number | null;
  threshold: number | null;
  rationale: string;
}

export interface EngineView {
  target: string;
  model: { name: string; version: string };
  sufficient: boolean;
  insufficient_reason: string | null;
  confidence: number;
  factors: string[];
  expected: Record<string, number>;
  predictions: PredItem[];
}

export interface OddsItem {
  bookmaker: string | null;
  market: string;
  selection: string;
  price: number;
  implied_probability: number | null;
  fetched_at: string | null;
}

export interface MatchDetail {
  id: string;
  league: LeagueInfo;
  home: TeamSide;
  away: TeamSide;
  minute: number | null;
  score: { home: number | null; away: number | null };
  status: { short: string; long: string | null };
  data_quality: string;
  data_age_seconds: number | null;
  last_updated_at: string | null;
  stats: { home: SideStats | null; away: SideStats | null };
  events: Array<{
    minute: number | null;
    extra: number | null;
    type: string | null;
    detail: string | null;
    side: string | null;
    player: string | null;
    assist: string | null;
  }>;
  timeline: Array<{
    minute: number;
    side: string;
    shots: number | null;
    shots_on: number | null;
    corners: number | null;
    dangerous_attacks: number | null;
    xg: number | null;
  }>;
  current_predictions: {
    baseline: { source: string; sample_matches: number; note: string | null };
    goal: EngineView;
    corner: EngineView;
  };
  odds?: OddsItem[];
  prediction_history: Array<{
    id: number;
    created_at: string;
    minute: number | null;
    score: { home: number | null; away: number | null };
    target: string;
    market: string;
    probability: number;
    confidence: number | null;
    data_quality: string;
    rationale: string | null;
    outcome: {
      actual: number | null;
      status: string;
      detail: string | null;
    } | null;
  }>;
}

export interface SystemStatus {
  server_time: string;
  provider: { name: string; configured: boolean; mode: string; config_hint: string | null };
  quota: {
    daily_limit: number;
    daily_used: number;
    daily_remaining: number;
    reserve: number;
    per_minute_limit: number;
    note: string;
  } | null;
  target_competitions: Array<{ key: string; name: string; api_football_id: string }>;
  counts: {
    leagues: number;
    matches: number;
    predictions: number;
    settled_predictions: number;
  };
  last_successful_refresh: string | null;
}

export interface PerfSegment {
  key: string;
  label: string;
  count: number;
  note: string | null;
  metrics: {
    brier: number;
    log_loss: number;
    base_rate: number;
    baseline_brier: number;
    baseline_log_loss: number;
    calibration: Array<{
      low: number;
      high: number;
      count: number;
      avg_predicted: number;
      actual_rate: number;
    }>;
  } | null;
}

export interface RecentFormItem {
  date: string;
  home: boolean;
  opponent: string | null;
  score: string;
  competition: string | null;
}

export interface PrematchTeamForm {
  team_id: string;
  name: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  gf: number;
  ga: number;
  avg_gf: number | null;
  avg_ga: number | null;
  over25_rate: number | null;
  btts_rate: number | null;
  form: string[];
  recent: RecentFormItem[];
  basis: string;
}

export interface H2HItem {
  date: string;
  home: string | null;
  away: string | null;
  score: string;
  competition: string | null;
}

export interface PrematchPreview {
  home: PrematchTeamForm;
  away: PrematchTeamForm;
  h2h: { played: number; wins: number; draws: number; losses: number; matches: H2HItem[] };
  prediction: {
    lambda_home: number;
    lambda_away: number;
    markets: Record<string, number>;
    note: string;
  } | null;
}
