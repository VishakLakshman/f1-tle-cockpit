from pydantic import BaseModel
from typing import List, Optional


class TrackPoint(BaseModel):
    x: float
    y: float
    distance: float  # normalised 0-1


class TelemetryPoint(BaseModel):
    distance: float       # metres along lap
    distance_pct: float   # 0-1
    speed: float          # km/h
    throttle: float       # 0-100
    brake: bool
    rpm: int
    gear: int
    drs: int


class DriverLapData(BaseModel):
    driver: str
    team: str
    team_color: str
    lap_time: str          # e.g. "1:18.412"
    lap_time_ms: float
    telemetry: List[TelemetryPoint]
    track_path: List[TrackPoint]   # SVG-ready normalised coords


class DeltaPoint(BaseModel):
    distance: float
    distance_pct: float
    delta_ms: float        # positive = driver1 ahead, negative = driver2 ahead


class QualifyingGhostResponse(BaseModel):
    session_name: str      # e.g. "2024 Monaco GP — Q3"
    year: int
    gp: str
    session: str
    driver1: DriverLapData
    driver2: DriverLapData
    delta: List[DeltaPoint]
    track_length_m: float
    cached: bool


class SessionInfoResponse(BaseModel):
    year: int
    gp: str
    sessions: List[str]
    drivers: List[dict]    # [{code, name, team, team_color}]


# ── Module B: Tyre Degradation ────────────────────────────────────────────────

class TyreLap(BaseModel):
    lap_number: Optional[int]
    lap_time_ms: float
    lap_time_str: str
    tyre_life: Optional[int]
    compound: str
    is_valid: bool


class TyreStint(BaseModel):
    stint_number: int
    compound: str
    compound_color: str
    laps: List[TyreLap]
    deg_slope_ms_per_lap: float
    avg_lap_time_ms: float
    lap_count: int


class TyreDriver(BaseModel):
    code: str
    name: str
    team: str
    team_color: str
    stints: List[TyreStint]


class TyreDegradationResponse(BaseModel):
    session_name: str
    year: int
    gp: str
    drivers: List[TyreDriver]
    cached: bool = False

# ── Module C: Race Strategy ───────────────────────────────────────────────────

class StrategyStint(BaseModel):
    stint_number: int
    compound: str
    compound_color: str
    start_lap: int
    end_lap: int
    lap_count: int
    tyre_life_at_start: Optional[int]


class PitStop(BaseModel):
    stop_number: int
    lap: int
    pit_duration_s: Optional[float]
    from_compound: str
    to_compound: str


class PositionPoint(BaseModel):
    lap: int
    position: int


class StrategyDriver(BaseModel):
    code: str
    name: str
    team: str
    team_color: str
    finish_position: int
    stints: List[StrategyStint]
    pit_stops: List[PitStop]
    positions: List[PositionPoint]


class RaceStrategyResponse(BaseModel):
    session_name: str
    year: int
    gp: str
    total_laps: int
    drivers: List[StrategyDriver]
    cached: bool = False
