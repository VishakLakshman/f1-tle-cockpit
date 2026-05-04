"""
Offline tyre degradation pipeline for F1 2025 season.

Run after process_season.py (or standalone):
    cd pipeline
    python process_tyres.py

What it does:
  - Loads the Race session for each completed 2025 GP
  - Extracts per-driver, per-stint lap times + tyre compound
  - Filters out in-laps, out-laps, safety car laps, VSC laps
  - Computes a linear degradation slope per stint (ms/lap)
  - Uploads to S3:
      processed/2025/{gp_slug}/race/tyre_degradation.json

S3 payload shape:
  {
    "session_name": "2025 Monaco — Race",
    "year": 2025,
    "gp": "Monaco",
    "drivers": [
      {
        "code": "VER",
        "name": "Max Verstappen",
        "team": "Red Bull Racing",
        "team_color": "#3671C6",
        "stints": [
          {
            "stint_number": 1,
            "compound": "SOFT",
            "compound_color": "#FF3333",
            "laps": [
              {"lap_number": 1, "lap_time_ms": 78412, "lap_time_str": "1:18.412",
               "tyre_life": 1, "is_valid": true}
            ],
            "deg_slope_ms_per_lap": 85.4,   # positive = getting slower
            "avg_lap_time_ms": 79200
          }
        ]
      }
    ]
  }
"""

import os
import traceback
from datetime import datetime

import numpy as np
import fastf1
from dotenv import load_dotenv
from upload_to_s3 import upload_json

load_dotenv()

CACHE_DIR = os.getenv("FF1_CACHE_DIR", "/tmp/fastf1_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

YEAR = 2025

# Compound colours matching F1 official palette
COMPOUND_COLORS = {
    "SOFT":   "#FF3333",
    "MEDIUM": "#FFD700",
    "HARD":   "#FFFFFF",
    "INTER":  "#39B54A",
    "WET":    "#0067FF",
    "UNKNOWN": "#888888",
}


def get_completed_gps(year: int) -> list[tuple[str, str]]:
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    today = datetime.now()
    past = schedule[schedule["EventDate"] < today]
    results = []
    for _, row in past.iterrows():
        official = row["EventName"]
        slug = official.replace(" Grand Prix", "").replace(" ", "_")
        results.append((official, slug))
    return results


def _lap_time_str(ms: float) -> str:
    total_s = ms / 1000
    mins = int(total_s // 60)
    secs = total_s % 60
    return f"{mins}:{secs:06.3f}"


def _deg_slope(tyre_lives: list[int], lap_times_ms: list[float]) -> float:
    """
    Linear regression slope of lap_time vs tyre_life.
    Returns ms gained per lap (positive = degrading).
    Returns 0.0 if not enough data points.
    """
    if len(tyre_lives) < 3:
        return 0.0
    x = np.array(tyre_lives, dtype=float)
    y = np.array(lap_times_ms, dtype=float)
    coeffs = np.polyfit(x, y, 1)
    return float(coeffs[0])


def process_race_tyres(year: int, official_name: str, gp_slug: str) -> dict | None:
    print(f"  Loading Race session...")
    try:
        session = fastf1.get_session(year, official_name, "Race")
        session.load(telemetry=False, weather=True, messages=False, laps=True)
    except Exception as e:
        print(f"  Could not load Race session: {e}")
        return None

    laps = session.laps.copy()

    # Filter out laps we don't want to skew degradation analysis:
    # - out-laps (first lap on a fresh set, driver is warming tyres)
    # - in-laps (last lap of stint, driver is saving tyres / pitting)
    # - safety car / VSC laps (artificially slow)
    # - deleted laps (track limits)
    # - laps with no valid time
    laps = laps[laps["PitOutTime"].isna()]     # exclude out-laps
    laps = laps[laps["PitInTime"].isna()]      # exclude in-laps
    laps = laps[laps["Deleted"] == False] if "Deleted" in laps.columns else laps
    laps = laps[laps["LapTime"].notna()]

    # Exclude safety car laps using TrackStatus
    if "TrackStatus" in laps.columns:
        # TrackStatus "4" = Safety Car, "6" = VSC, "7" = VSC ending
        laps = laps[~laps["TrackStatus"].astype(str).str.contains("4|6|7")]

    drivers_data = []

    for driver_code in sorted(laps["Driver"].unique()):
        driver_laps = laps[laps["Driver"] == driver_code].copy()
        if driver_laps.empty:
            continue

        try:
            info = session.get_driver(driver_code)
            driver_name = info.get("FullName", driver_code)
            team_name = info.get("TeamName", "")
            team_color = "#" + info.get("TeamColor", "ffffff")
        except Exception:
            driver_name = driver_code
            team_name = ""
            team_color = "#ffffff"

        # Group into stints
        stints = []
        if "Stint" not in driver_laps.columns:
            print(f"    No Stint column for {driver_code}, skipping")
            continue

        for stint_num in sorted(driver_laps["Stint"].dropna().unique()):
            stint_laps = driver_laps[driver_laps["Stint"] == stint_num].copy()
            if stint_laps.empty:
                continue

            compound = str(stint_laps["Compound"].iloc[0]).upper()
            compound_color = COMPOUND_COLORS.get(compound, COMPOUND_COLORS["UNKNOWN"])

            lap_rows = []
            valid_tyre_lives = []
            valid_lap_times = []

            for _, lap in stint_laps.iterrows():
                lt = lap["LapTime"]
                lap_time_ms = lt.total_seconds() * 1000 if hasattr(lt, "total_seconds") else None
                tyre_life = int(lap["TyreLife"]) if "TyreLife" in lap and not np.isnan(lap["TyreLife"]) else None
                lap_number = int(lap["LapNumber"]) if not np.isnan(lap["LapNumber"]) else None

                if lap_time_ms is None or lap_time_ms <= 0:
                    continue

                # Filter obvious outliers — laps > 120% of median are likely SC/VSC that slipped through
                lap_rows.append({
                    "lap_number": lap_number,
                    "lap_time_ms": round(lap_time_ms, 1),
                    "lap_time_str": _lap_time_str(lap_time_ms),
                    "tyre_life": tyre_life,
                    "compound": compound,
                    "is_valid": True,
                })
                if tyre_life is not None:
                    valid_tyre_lives.append(tyre_life)
                    valid_lap_times.append(lap_time_ms)

            if not lap_rows:
                continue

            # Remove outliers > 120% of median lap time for this stint
            if valid_lap_times:
                median_ms = float(np.median(valid_lap_times))
                lap_rows = [
                    {**r, "is_valid": r["lap_time_ms"] <= median_ms * 1.20}
                    for r in lap_rows
                ]
                valid_pairs = [
                    (tl, lt) for r, tl, lt
                    in zip(lap_rows, valid_tyre_lives, valid_lap_times)
                    if r["is_valid"]
                ]
                clean_tl = [p[0] for p in valid_pairs]
                clean_lt = [p[1] for p in valid_pairs]
            else:
                clean_tl, clean_lt = [], []

            stints.append({
                "stint_number": int(stint_num),
                "compound": compound,
                "compound_color": compound_color,
                "laps": lap_rows,
                "deg_slope_ms_per_lap": _deg_slope(clean_tl, clean_lt),
                "avg_lap_time_ms": round(float(np.mean(clean_lt)), 1) if clean_lt else 0.0,
                "lap_count": len(lap_rows),
            })

        if stints:
            drivers_data.append({
                "code": driver_code,
                "name": driver_name,
                "team": team_name,
                "team_color": team_color,
                "stints": stints,
            })

    return {
        "session_name": f"{year} {gp_slug.replace('_', ' ')} — Race",
        "year": year,
        "gp": gp_slug,
        "drivers": drivers_data,
    }


def main():
    print("Fetching 2025 schedule...")
    gps = get_completed_gps(YEAR)

    if not gps:
        print("No completed races found for 2025.")
        return

    print(f"Found {len(gps)} completed races.")

    for official_name, gp_slug in gps:
        print(f"\n{'='*60}")
        print(f"  {YEAR} {official_name}  (slug: {gp_slug})")
        print(f"{'='*60}")

        try:
            payload = process_race_tyres(YEAR, official_name, gp_slug)
            if payload:
                key = f"processed/{YEAR}/{gp_slug}/race/tyre_degradation.json"
                upload_json(key, payload)
                driver_count = len(payload["drivers"])
                print(f"  Uploaded: {driver_count} drivers → {key}")
        except Exception as e:
            print(f"  Failed: {e}")
            traceback.print_exc()

    print("\nTyre pipeline complete.")


if __name__ == "__main__":
    main()