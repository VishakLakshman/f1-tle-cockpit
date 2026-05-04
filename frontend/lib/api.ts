const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Module A: Qualifying Ghost ────────────────────────────────────────────────

export interface TrackPoint {
  x: number;
  y: number;
  distance: number;
}

export interface TelemetryPoint {
  distance: number;
  distance_pct: number;
  speed: number;
  throttle: number;
  brake: boolean;
  rpm: number;
  gear: number;
  drs: number;
}

export interface DriverLapData {
  driver: string;
  team: string;
  team_color: string;
  lap_time: string;
  lap_time_ms: number;
  telemetry: TelemetryPoint[];
  track_path: TrackPoint[];
}

export interface DeltaPoint {
  distance: number;
  distance_pct: number;
  delta_ms: number;
}

export interface GhostResponse {
  session_name: string;
  year: number;
  gp: string;
  session: string;
  driver1: DriverLapData;
  driver2: DriverLapData;
  delta: DeltaPoint[];
  track_length_m: number;
  cached: boolean;
}

export interface SessionInfo {
  year: number;
  gp: string;
  sessions: string[];
  drivers: { code: string; name: string; team: string; team_color: string }[];
}

// ── Module B: Tyre Degradation ────────────────────────────────────────────────

export interface TyreLap {
  lap_number: number | null;
  lap_time_ms: number;
  lap_time_str: string;
  tyre_life: number | null;
  compound: string;
  is_valid: boolean;
}

export interface TyreStint {
  stint_number: number;
  compound: string;
  compound_color: string;
  laps: TyreLap[];
  deg_slope_ms_per_lap: number;
  avg_lap_time_ms: number;
  lap_count: number;
}

export interface TyreDriver {
  code: string;
  name: string;
  team: string;
  team_color: string;
  stints: TyreStint[];
}

export interface TyreDegradationResponse {
  session_name: string;
  year: number;
  gp: string;
  drivers: TyreDriver[];
  cached: boolean;
}

// ── Module C: Race Strategy ───────────────────────────────────────────────────

export interface StrategyStint {
  stint_number: number;
  compound: string;
  compound_color: string;
  start_lap: number;
  end_lap: number;
  lap_count: number;
  tyre_life_at_start: number | null;
}

export interface PitStop {
  stop_number: number;
  lap: number;
  pit_duration_s: number | null;
  from_compound: string;
  to_compound: string;
}

export interface PositionPoint {
  lap: number;
  position: number;
}

export interface StrategyDriver {
  code: string;
  name: string;
  team: string;
  team_color: string;
  finish_position: number;
  stints: StrategyStint[];
  pit_stops: PitStop[];
  positions: PositionPoint[];
}

export interface RaceStrategyResponse {
  session_name: string;
  year: number;
  gp: string;
  total_laps: number;
  drivers: StrategyDriver[];
  cached: boolean;
}

// ── API client ────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "API error");
  }
  return res.json() as Promise<T>;
}

export const api = {
  sessionInfo: (year: number, gp: string, session: string) =>
    apiFetch<SessionInfo>(
      `/api/qualifying/session-info?year=${year}&gp=${encodeURIComponent(gp)}&session=${session}`
    ),

  ghostLap: (year: number, gp: string, session: string, d1: string, d2: string) =>
    apiFetch<GhostResponse>(
      `/api/qualifying/ghost?year=${year}&gp=${encodeURIComponent(gp)}&session=${session}&driver1=${d1}&driver2=${d2}`
    ),

  tyreDegradation: (year: number, gp: string) =>
    apiFetch<TyreDegradationResponse>(
      `/api/tyres/degradation?year=${year}&gp=${encodeURIComponent(gp)}`
    ),

  raceStrategy: (year: number, gp: string) =>
    apiFetch<RaceStrategyResponse>(
      `/api/strategy/race?year=${year}&gp=${encodeURIComponent(gp)}`
    ),
};