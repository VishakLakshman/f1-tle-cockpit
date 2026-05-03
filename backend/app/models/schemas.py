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