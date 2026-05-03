const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface TrackPoint {
  x: number;
  y: number;
  distance: number; // 0-1
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
};