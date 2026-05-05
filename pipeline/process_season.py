"""
Offline pre-processing pipeline for F1 qualifying sessions.

Usage:
    python process_season.py              # defaults to current year
    python process_season.py 2025         # specific year
    python process_season.py 2026         # works for any year

FastF1 session name reference:
  ✓ "Qualifying"    — full qualifying session (Q1+Q2+Q3 segments inside)
  ✗ "Q1"/"Q2"/"Q3" — NOT valid FastF1 session types

We load "Qualifying" once per GP, then split laps by the
"Session" or "QualifyingPart" column to get Q1/Q2/Q3 separately.

S3 key structure:
  processed/{year}/{gp_slug}/{segment}/session_info.json
  processed/{year}/{gp_slug}/{segment}/{driver1}_{driver2}.json
"""

import os
import sys
import itertools
import traceback
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import fastf1
from dotenv import load_dotenv
from upload_to_s3 import upload_json

load_dotenv()

CACHE_DIR = os.getenv("FF1_CACHE_DIR", "/tmp/fastf1_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

SEGMENTS = ["Q1", "Q2", "Q3"]


# ── Schedule helpers ──────────────────────────────────────────────────────────

def get_completed_gps(year: int) -> list[tuple[str, str]]:
    """
    Returns list of (official_name, slug) for GPs where qualifying
    has already happened.

    Uses Session4DateUtc (the qualifying session datetime) not EventDate
    (which is the start of the race weekend — Thu/Fri). This ensures:
      - Future qualifying sessions are correctly excluded
      - Past qualifying sessions are correctly included even if the
        race hasn't happened yet (e.g. sprint weekends)
    """
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    now = datetime.now(timezone.utc)
    results = []

    for _, row in schedule.iterrows():
        # Session4 is Qualifying on a standard weekend.
        # On sprint weekends Session4 may be Sprint Qualifying —
        # we fall back to Session5 (Race) date as a safe upper bound.
        quali_date = row.get("Session4DateUtc")

        if quali_date is None or (isinstance(quali_date, float) and pd.isna(quali_date)):
            # Try Session5 as fallback
            quali_date = row.get("Session5DateUtc")

        if quali_date is None or (isinstance(quali_date, float) and pd.isna(quali_date)):
            continue

        # Make timezone-aware if needed
        if hasattr(quali_date, "tzinfo") and quali_date.tzinfo is None:
            quali_date = quali_date.replace(tzinfo=timezone.utc)

        if quali_date > now:
            continue  # qualifying hasn't happened yet

        official = row["EventName"]   # e.g. "Bahrain Grand Prix"
        slug = official.replace(" Grand Prix", "").replace(" ", "_")
        results.append((official, slug))

    return results


# ── Processing helpers ────────────────────────────────────────────────────────

def _ms(td) -> float:
    return td.total_seconds() * 1000


def _lap_time_str(td) -> str:
    total_s = td.total_seconds()
    mins = int(total_s // 60)
    secs = total_s % 60
    return f"{mins}:{secs:06.3f}"


def _normalise_track(x_arr, y_arr):
    x = np.array(x_arr, dtype=float)
    y = np.array(y_arr, dtype=float)
    x_min, x_max = x.min(), x.max()
    y_min, y_max = y.min(), y.max()
    view = 900.0
    scale = view / max(x_max - x_min or 1.0, y_max - y_min or 1.0)
    return (50 + (x - x_min) * scale).tolist(), (50 + (y - y_min) * scale).tolist()


def _resample(arr, distances, target):
    return np.interp(target, distances, arr)


def process_driver(segment_laps, code: str):
    """Extract fastest lap telemetry for one driver in one Q segment."""
    driver_laps = segment_laps[segment_laps["Driver"] == code]
    if driver_laps.empty:
        raise ValueError(f"No laps found for driver {code} in this segment")

    lap = driver_laps.pick_fastest()

    # get_telemetry() requires pos_data to be loaded (car position stream).
    # For some sessions (especially newer years) this may not be available
    # even when telemetry=True was passed to session.load(). We validate
    # the telemetry result before proceeding rather than crashing.
    try:
        tel = lap.get_telemetry().add_distance()
    except Exception as e:
        raise ValueError(f"Telemetry not available for {code}: {e}")

    tel = tel.dropna(subset=["Distance"])

    if tel.empty or len(tel) < 10:
        raise ValueError(f"Telemetry for {code} is empty or too short after dropna")

    # Validate required columns exist
    required = ["Speed", "Throttle", "Brake", "RPM", "nGear", "DRS", "X", "Y"]
    missing = [c for c in required if c not in tel.columns]
    if missing:
        raise ValueError(f"Telemetry for {code} missing columns: {missing}")

    dist = tel["Distance"].values
    track_length = float(dist[-1])
    dist_pct = (dist / track_length).tolist()

    x_norm, y_norm = _normalise_track(
        tel["X"].ffill().values,
        tel["Y"].ffill().values,
    )

    track_path = [{"x": x, "y": y, "distance": d}
                  for x, y, d in zip(x_norm, y_norm, dist_pct)]

    telemetry = [
        {
            "distance":     float(dist[i]),
            "distance_pct": float(dist_pct[i]),
            "speed":        float(tel["Speed"].iloc[i]),
            "throttle":     float(tel["Throttle"].iloc[i]),
            "brake":        bool(tel["Brake"].iloc[i]),
            "rpm":          int(tel["RPM"].iloc[i]),
            "gear":         int(tel["nGear"].iloc[i]),
            "drs":          int(tel["DRS"].iloc[i]),
        }
        for i in range(len(dist))
    ]

    return (
        {
            "driver":      code,
            "team":        lap["Team"] if "Team" in lap.index else "",
            "team_color":  "",   # filled by enrich_driver_color()
            "lap_time":    _lap_time_str(lap["LapTime"]),
            "lap_time_ms": _ms(lap["LapTime"]),
            "telemetry":   telemetry,
            "track_path":  track_path,
        },
        dist,
        tel["Time"].values,
    )


def enrich_driver_color(session, driver_data: dict) -> dict:
    try:
        info = session.get_driver(driver_data["driver"])
        driver_data["team"]       = info["TeamName"]
        driver_data["team_color"] = "#" + info.get("TeamColor", "ffffff")
    except Exception:
        driver_data["team_color"] = "#ffffff"
    return driver_data


def build_ghost_payload(year, gp_slug, segment, session, segment_laps, d1_code, d2_code) -> dict:
    d1_data, d1_dist, d1_time = process_driver(segment_laps, d1_code)
    d2_data, d2_dist, d2_time = process_driver(segment_laps, d2_code)

    d1_data = enrich_driver_color(session, d1_data)
    d2_data = enrich_driver_color(session, d2_data)

    common_dist = np.linspace(0, min(d1_dist[-1], d2_dist[-1]), num=500)

    def to_s(t): return t.astype("float64") / 1e9

    delta_ms = (
        _resample(to_s(d1_time), d1_dist, common_dist) -
        _resample(to_s(d2_time), d2_dist, common_dist)
    ) * 1000

    delta = [
        {
            "distance":     float(common_dist[i]),
            "distance_pct": float(common_dist[i] / max(d1_dist[-1], d2_dist[-1])),
            "delta_ms":     float(delta_ms[i]),
        }
        for i in range(len(common_dist))
    ]

    return {
        "session_name":  f"{year} {gp_slug.replace('_', ' ')} — {segment}",
        "year":          year,
        "gp":            gp_slug,
        "session":       segment,
        "driver1":       d1_data,
        "driver2":       d2_data,
        "delta":         delta,
        "track_length_m": float(max(d1_dist[-1], d2_dist[-1])),
        "cached":        False,
    }


def build_session_info(year, gp_slug, segment, session, drivers_in_segment) -> dict:
    drivers = []
    for abbr in drivers_in_segment:
        try:
            info = session.get_driver(abbr)
            drivers.append({
                "code":       abbr,
                "name":       info["FullName"],
                "team":       info["TeamName"],
                "team_color": "#" + info.get("TeamColor", "ffffff"),
            })
        except Exception:
            drivers.append({"code": abbr, "name": abbr, "team": "", "team_color": "#ffffff"})
    return {"year": year, "gp": gp_slug, "sessions": SEGMENTS, "drivers": drivers}


# ── Per-GP processing ─────────────────────────────────────────────────────────

def process_gp(year: int, official_name: str, gp_slug: str):
    print(f"\n{'='*60}")
    print(f"  {year} {official_name}  (slug: {gp_slug})")
    print(f"{'='*60}")

    try:
        session = fastf1.get_session(year, official_name, "Qualifying")
        # laps=True loads lap data and timing
        # telemetry=True loads car data (speed/throttle/brake) AND pos_data
        # (X/Y position stream) — both are required for get_telemetry()
        session.load(laps=True, telemetry=True, weather=False, messages=False)
    except Exception as e:
        print(f"  ✗ Could not load Qualifying session: {e}")
        return

    # Validate that positional data actually loaded — for some sessions
    # (especially recent years) FastF1 may silently return empty pos_data
    if not session.pos_data:
        print(f"  ✗ No positional data available for this session — cannot compute telemetry")
        return

    if not session.car_data:
        print(f"  ✗ No car data available for this session")
        return

    all_laps = session.laps

    # Detect which column holds the Q1/Q2/Q3 segment identifier
    segment_col = None
    for col in ["Session", "QualifyingPart"]:
        if col in all_laps.columns:
            segment_col = col
            break

    if segment_col is None:
        print(f"  ⚠ No segment column found — treating all laps as Q3")
        segments_to_process = {"Q3": all_laps}
    else:
        segments_to_process = {}
        for seg in SEGMENTS:
            seg_laps = all_laps[all_laps[segment_col] == seg]
            if not seg_laps.empty:
                segments_to_process[seg] = seg_laps
            else:
                print(f"  ⚠ No laps found for {seg} — skipping")

    for segment, segment_laps in segments_to_process.items():
        print(f"\n  ── {segment} ──")

        drivers_in_segment = sorted(segment_laps["Driver"].dropna().unique().tolist())
        print(f"     Drivers: {drivers_in_segment}")

        try:
            info = build_session_info(year, gp_slug, segment, session, drivers_in_segment)
            upload_json(f"processed/{year}/{gp_slug}/{segment}/session_info.json", info)
            print(f"     ✓ session_info uploaded ({len(drivers_in_segment)} drivers)")
        except Exception as e:
            print(f"     ✗ session_info failed: {e}")

        pairs = list(itertools.combinations(drivers_in_segment, 2))
        print(f"     Processing {len(pairs)} driver pairs...")

        for d1, d2 in pairs:
            pair_key = "_".join(sorted([d1, d2]))
            s3_key = f"processed/{year}/{gp_slug}/{segment}/{pair_key}.json"
            try:
                payload = build_ghost_payload(
                    year, gp_slug, segment, session, segment_laps, d1, d2
                )
                upload_json(s3_key, payload)
                print(f"     ✓ {d1} vs {d2}")
            except Exception as e:
                print(f"     ✗ {d1} vs {d2}: {e}")
                traceback.print_exc()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    # Accept year as optional CLI argument: python process_season.py 2026
    #year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.now().year
    year = 2025
    print(f"Fetching {year} schedule...")

    gps = get_completed_gps(year)

    if not gps:
        print(f"No completed qualifying sessions found for {year} yet.")
        return

    print(f"Found {len(gps)} completed events:")
    for official, slug in gps:
        print(f"  {official} → slug: {slug}")

    for official_name, gp_slug in gps:
        process_gp(year, official_name, gp_slug)

    print(f"\n✅ Pipeline complete for {year}.")


if __name__ == "__main__":
    main()