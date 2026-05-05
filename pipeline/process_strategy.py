"""
Offline race strategy pipeline for F1 2025 season.

Run from the pipeline directory:
    cd pipeline
    source venv/bin/activate
    python process_strategy.py

What it does:
  - Loads the Race session for each completed 2025 GP
  - Extracts per-driver stint/compound/pit timing (Gantt data)
  - Extracts lap-by-lap positions for all drivers (position chart)
  - Extracts pit stop timing details (undercut/overcut analysis)
  - Uploads to S3:
      processed/2025/{gp_slug}/race/race_strategy.json

S3 payload shape:
  {
    "session_name": "2025 Monaco - Race",
    "year": 2025,
    "gp": "Monaco",
    "total_laps": 78,
    "drivers": [
      {
        "code": "VER",
        "name": "Max Verstappen",
        "team": "Red Bull Racing",
        "team_color": "#3671C6",
        "finish_position": 1,
        "stints": [
          {
            "stint_number": 1,
            "compound": "MEDIUM",
            "compound_color": "#FFD700",
            "start_lap": 1,
            "end_lap": 28,
            "lap_count": 28,
            "tyre_life_at_start": 1
          }
        ],
        "pit_stops": [
          {
            "lap": 28,
            "stop_number": 1,
            "pit_duration_s": 2.45,
            "from_compound": "MEDIUM",
            "to_compound": "HARD"
          }
        ],
        "positions": [
          {"lap": 1, "position": 1},
          {"lap": 2, "position": 1},
          ...
        ]
      }
    ]
  }
"""

import os
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

YEAR = 2026

COMPOUND_COLORS = {
    "SOFT":    "#FF3333",
    "MEDIUM":  "#FFD700",
    "HARD":    "#FFFFFF",
    "INTER":   "#39B54A",
    "WET":     "#0067FF",
    "UNKNOWN": "#888888",
}


# ── Schedule ──────────────────────────────────────────────────────────────────

def get_completed_gps(year: int) -> list[tuple[str, str]]:
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    now = datetime.now(timezone.utc)
    results = []
    for _, row in schedule.iterrows():
        race_date = row.get("Session5DateUtc")
        if race_date is None or pd.isna(race_date):
            continue
        if race_date.tzinfo is None:
            race_date = race_date.replace(tzinfo=timezone.utc)
        if race_date > now:
            continue
        official = row["EventName"]
        slug = official.replace(" Grand Prix", "").replace(" ", "_")
        results.append((official, slug))
    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_int(val) -> int | None:
    try:
        f = float(val)
        return None if np.isnan(f) else int(f)
    except (TypeError, ValueError):
        return None


def _safe_float(val, decimals=3) -> float | None:
    try:
        f = float(val)
        return None if np.isnan(f) else round(f, decimals)
    except (TypeError, ValueError):
        return None


# ── Core processing ───────────────────────────────────────────────────────────

def process_race_strategy(year: int, official_name: str, gp_slug: str) -> dict | None:
    print(f"  Loading Race session...")
    try:
        session = fastf1.get_session(year, official_name, "Race")
        session.load(telemetry=False, weather=False, messages=False, laps=True)
    except Exception as e:
        print(f"  Could not load Race session: {e}")
        return None

    laps = session.laps.copy()
    if laps.empty:
        print(f"  No laps data")
        return None

    total_laps = _safe_int(laps["LapNumber"].max()) or 0
    print(f"  Total laps: {total_laps}")

    # Build finish position map from last lap position
    finish_positions: dict[str, int] = {}
    for driver_code in laps["Driver"].dropna().unique():
        driver_laps = laps[laps["Driver"] == driver_code]
        last_lap = driver_laps.iloc[-1]
        pos = _safe_int(last_lap.get("Position"))
        finish_positions[driver_code] = pos or 99

    # Sort drivers by finish position
    drivers_sorted = sorted(
        laps["Driver"].dropna().unique(),
        key=lambda d: finish_positions.get(d, 99)
    )

    drivers_data = []

    for driver_code in drivers_sorted:
        driver_laps = laps[laps["Driver"] == driver_code].copy()
        if driver_laps.empty:
            continue

        try:
            info = session.get_driver(driver_code)
            driver_name  = info.get("FullName", driver_code)
            team_name    = info.get("TeamName", "")
            team_color   = "#" + info.get("TeamColor", "ffffff")
        except Exception:
            driver_name = driver_code
            team_name   = ""
            team_color  = "#ffffff"

        # ── Positions over laps ───────────────────────────────────────────────
        positions = []
        for _, lap in driver_laps.iterrows():
            lap_num = _safe_int(lap.get("LapNumber"))
            pos     = _safe_int(lap.get("Position"))
            if lap_num is not None and pos is not None:
                positions.append({"lap": lap_num, "position": pos})

        # ── Stints ───────────────────────────────────────────────────────────
        stints = []
        if "Stint" in driver_laps.columns:
            for stint_num in sorted(driver_laps["Stint"].dropna().unique()):
                stint_laps = driver_laps[driver_laps["Stint"] == stint_num]
                if stint_laps.empty:
                    continue

                compound    = str(stint_laps["Compound"].iloc[0]).upper()
                start_lap   = _safe_int(stint_laps["LapNumber"].min())
                end_lap     = _safe_int(stint_laps["LapNumber"].max())
                tyre_life   = _safe_int(stint_laps["TyreLife"].iloc[0]) if "TyreLife" in stint_laps.columns else None
                lap_count   = len(stint_laps)

                stints.append({
                    "stint_number":       int(stint_num),
                    "compound":           compound,
                    "compound_color":     COMPOUND_COLORS.get(compound, COMPOUND_COLORS["UNKNOWN"]),
                    "start_lap":          start_lap or 0,
                    "end_lap":            end_lap or 0,
                    "lap_count":          lap_count,
                    "tyre_life_at_start": tyre_life,
                })

        # ── Pit stops ─────────────────────────────────────────────────────────
        # Detect pit stops from PitInTime / PitOutTime transitions
        pit_stops = []
        pit_laps = driver_laps[driver_laps["PitInTime"].notna()].copy()

        for stop_idx, (_, pit_lap) in enumerate(pit_laps.iterrows(), start=1):
            pit_lap_num = _safe_int(pit_lap.get("LapNumber"))

            # Pit duration: from PitInTime to PitOutTime of next lap
            duration_s = None
            if "PitInTime" in pit_lap and "PitOutTime" in pit_lap:
                try:
                    pit_in  = pit_lap["PitInTime"]
                    # Find the out-lap (lap after the pit)
                    out_lap_df = driver_laps[
                        driver_laps["LapNumber"] == (pit_lap_num or 0) + 1
                    ]
                    if not out_lap_df.empty and "PitOutTime" in out_lap_df.columns:
                        pit_out = out_lap_df.iloc[0]["PitOutTime"]
                        if pd.notna(pit_in) and pd.notna(pit_out):
                            duration_s = round((pit_out - pit_in).total_seconds(), 2)
                except Exception:
                    pass

            # Find from/to compounds using stint data
            from_compound = "UNKNOWN"
            to_compound   = "UNKNOWN"
            if stints:
                for i, s in enumerate(stints):
                    if s["end_lap"] == pit_lap_num:
                        from_compound = s["compound"]
                        if i + 1 < len(stints):
                            to_compound = stints[i + 1]["compound"]
                        break

            if pit_lap_num is not None:
                pit_stops.append({
                    "stop_number":   stop_idx,
                    "lap":           pit_lap_num,
                    "pit_duration_s": duration_s,
                    "from_compound": from_compound,
                    "to_compound":   to_compound,
                })

        print(f"    {driver_code}: {len(stints)} stints, {len(pit_stops)} stops, pos {finish_positions.get(driver_code, '?')}")

        drivers_data.append({
            "code":             driver_code,
            "name":             driver_name,
            "team":             team_name,
            "team_color":       team_color,
            "finish_position":  finish_positions.get(driver_code, 99),
            "stints":           stints,
            "pit_stops":        pit_stops,
            "positions":        positions,
        })

    if not drivers_data:
        print(f"  WARNING: no driver data produced")
        return None

    return {
        "session_name": f"{year} {gp_slug.replace('_', ' ')} — Race",
        "year":         year,
        "gp":           gp_slug,
        "total_laps":   total_laps,
        "drivers":      drivers_data,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Fetching 2025 schedule...")
    gps = get_completed_gps(YEAR)

    if not gps:
        print("No completed races found for 2025.")
        return

    print(f"Found {len(gps)} completed races:")
    for official, slug in gps:
        print(f"  {official} -> {slug}")

    for official_name, gp_slug in gps:
        print(f"\n{'='*60}")
        print(f"  {YEAR} {official_name}  (slug: {gp_slug})")
        print(f"{'='*60}")

        try:
            payload = process_race_strategy(YEAR, official_name, gp_slug)
            if payload:
                key = f"processed/{YEAR}/{gp_slug}/race/race_strategy.json"
                upload_json(key, payload)
                print(f"  Uploaded {len(payload['drivers'])} drivers -> s3://.../{key}")
            else:
                print(f"  Skipped (no data)")
        except Exception as e:
            print(f"  FAILED: {e}")
            traceback.print_exc()

    print("\nStrategy pipeline complete.")


if __name__ == "__main__":
    main()