import type {
  LiveMatch,
  MatchDetail,
  PerfSegment,
  SystemStatus,
} from "./types";

const BASE = "";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* yut */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export interface LiveFilters {
  league?: string;
  minute_min?: number;
  minute_max?: number;
  min_goal_prob?: number;
  min_corner_prob?: number;
  data_quality?: string;
}

export function fetchSystemStatus(): Promise<SystemStatus> {
  return getJson<SystemStatus>("/api/system/status");
}

export function fetchLiveMatches(filters: LiveFilters): Promise<{ count: number; matches: LiveMatch[] }> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== "" && v !== null) params.set(k, String(v));
  });
  const qs = params.toString();
  return getJson(`/api/matches/live${qs ? `?${qs}` : ""}`);
}

export function fetchDayMatches(date: string): Promise<{ count: number; matches: LiveMatch[] }> {
  return getJson(`/api/matches/day?date=${encodeURIComponent(date)}`);
}

export async function refreshDay(date: string): Promise<{ refreshed: number }> {
  const res = await fetch(`${BASE}/api/matches/refresh-day?date=${encodeURIComponent(date)}`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function fetchMatchDetail(id: string): Promise<MatchDetail> {
  return getJson<MatchDetail>(`/api/matches/${encodeURIComponent(id)}`);
}

export async function refreshLive(): Promise<{ refreshed: number }> {
  const res = await fetch(`${BASE}/api/matches/refresh-live`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function enrichWatchlist(limit = 3): Promise<unknown> {
  const res = await fetch(`${BASE}/api/matches/enrich-watchlist?limit=${limit}`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function refreshMatch(id: string): Promise<MatchDetail> {
  const res = await fetch(`${BASE}/api/matches/${encodeURIComponent(id)}/refresh`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function fetchPerformance(dimension: string): Promise<{ dimension: string; segments: PerfSegment[] }> {
  return getJson(`/api/performance?dimension=${encodeURIComponent(dimension)}`);
}
