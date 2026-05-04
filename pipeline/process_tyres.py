"""
Offline tyre degradation pipeline for F1 2025 season.

Run from the pipeline directory:
    cd pipeline
    source venv/bin/activate
    python process_tyres.py

Fixes vs v1:
  - Uses Session5DateUtc (actual race date) not EventDate (weekend start)
    so future races are correctly excluded
  - Simplified lap filtering — removes the over-aggressive PitOutTime/PitInTime
    filter that was silently dropping entire drivers
  - Added verbose per-driver output so failures are visible
  - Guards against empty drivers_data before uploading
  - Handles NaN in TyreLife and LapNumber more robustly
"""

import os
import traceback
from datetime import datetime, timezone

import numpy as np
import fastf1
import pandas as pd
from dotenv import load_dotenv
from upload_to_s3 import upload_json

load_dotenv()

CACHE_DIR = os.getenv("FF1_CACHE_DIR", "/tmp/fastf1_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

YEAR = 2025

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
    """
    Returns (official_name, slug) for GPs where the RACE has already happened.
    Uses Session5DateUtc (the actual race session datetime) not EventDate
    (which is the start of the race weekend — Thu/Fri).
    """
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    now = datetime.now(timezone.utc)
    results = []

    for _, row in schedule.iterrows():
        # Session5 is always the Race
        race_date = row.get("Session5DateUtc")
        if race_date is None or pd.isna(race_date):
            continue
        # Make timezone-aware if needed
        if race_date.tzinfo is None:
            race_date = race_date.replace(tzinfo=timezone.utc)
        if race_date > now:
            continue  # race hasn't happened yet

        official = row["EventName"]
        slug = official.replace(" Grand Prix", "").replace(" ", "_")
        results.append((official, slug))

    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _lap_time_str(ms: float) -> str:
    total_s = ms / 1000
    mins = int(total_s // 60)
    secs = total_s % 60
    return f"{mins}:{secs:06.3f}"


def _deg_slope(tyre_lives: list, lap_times_ms: list) -> float:
    if len(tyre_lives) < 3:
        return 0.0
    x = np.array(tyre_lives, dtype=float)
    y = np.array(lap_times_ms, dtype=float)
    coeffs = np.polyfit(x, y, 1)
    return float(coeffs[0])


def _safe_int(val) -> int | None:
    try:
        f = float(val)
        if np.isnan(f):
            return None
        return int(f)
    except (TypeError, ValueError):
        return None


# ── Core processing ───────────────────────────────────────────────────────────

def process_race_tyres(year: int, official_name: str, gp_slug: str) -> dict | None:
    print(f"  Loading Race session...")
    try:
        session = fastf1.get_session(year, official_name, "Race")
        session.load(telemetry=False, weather=False, messages=False, laps=True)
    except Exception as e:
        print(f"  Could not load Race session: {e}")
        return None

    all_laps = session.laps.copy()
    print(f"  Total laps loaded: {len(all_laps)}")

    # Only keep laps with a valid recorded lap time
    all_laps = all_laps[all_laps["LapTime"].notna()]

    # Exclude safety car / VSC laps (TrackStatus 4=SC, 6=VSC, 7=VSC ending)
    if "TrackStatus" in all_laps.columns:
        sc_mask = all_laps["TrackStatus"].astype(str).str.contains("4|6|7", regex=True)
        removed = sc_mask.sum()
        if removed:
            print(f"  Removed {removed} SC/VSC laps")
        all_laps = all_laps[~sc_mask]

    # Exclude deleted laps (track limits)
    if "Deleted" in all_laps.columns:
        all_laps = all_laps[all_laps["Deleted"] != True]

    drivers_data = []

    for driver_code in sorted(all_laps["Driver"].dropna().unique()):
        driver_laps = all_laps[all_laps["Driver"] == driver_code].copy()

        try:
            info = session.get_driver(driver_code)
            driver_name = info.get("FullName", driver_code)
            team_name   = info.get("TeamName", "")
            team_color  = "#" + info.get("TeamColor", "ffffff")
        except Exception:
            driver_name = driver_code
            team_name   = ""
            team_color  = "#ffffff"

        if "Stint" not in driver_laps.columns:
            print(f"    {driver_code}: no Stint column, skipping")
            continue

        stints = []

        for stint_num in sorted(driver_laps["Stint"].dropna().unique()):
            stint_laps = driver_laps[driver_laps["Stint"] == stint_num].copy()
            if stint_laps.empty:
                continue

            # Exclude out-lap (first lap of stint — tyre warm-up)
            # and in-lap (last lap of stint — driver backing off to pit)
            if len(stint_laps) > 2:
                stint_laps = stint_laps.iloc[1:-1]   # drop first and last row
            elif len(stint_laps) == 2:
                stint_laps = stint_laps.iloc[1:]     # drop just the out-lap
            # If only 1 lap in stint, keep it (e.g. safety car period)

            if stint_laps.empty:
                continue

            compound = str(stint_laps["Compound"].iloc[0]).upper()
            compound_color = COMPOUND_COLORS.get(compound, COMPOUND_COLORS["UNKNOWN"])

            lap_rows = []
            tyre_lives = []
            lap_times  = []

            for _, lap in stint_laps.iterrows():
                lt = lap["LapTime"]
                if not hasattr(lt, "total_seconds"):
                    continue
                lap_time_ms = lt.total_seconds() * 1000
                if lap_time_ms <= 0:
                    continue

                tyre_life  = _safe_int(lap.get("TyreLife"))
                lap_number = _safe_int(lap.get("LapNumber"))

                lap_rows.append({
                    "lap_number":   lap_number,
                    "lap_time_ms":  round(lap_time_ms, 1),
                    "lap_time_str": _lap_time_str(lap_time_ms),
                    "tyre_life":    tyre_life,
                    "compound":     compound,
                    "is_valid":     True,
                })
                if tyre_life is not None:
                    tyre_lives.append(tyre_life)
                    lap_times.append(lap_time_ms)

            if not lap_rows:
                continue

            # Mark outliers (> 120% of stint median) as invalid
            if lap_times:
                median_ms = float(np.median(lap_times))
                threshold = median_ms * 1.20
                lap_rows = [
                    {**r, "is_valid": r["lap_time_ms"] <= threshold}
                    for r in lap_rows
                ]
                clean_tl = [tl for r, tl in zip(lap_rows, tyre_lives) if r["is_valid"]]
                clean_lt = [lt for r, lt in zip(lap_rows, lap_times)  if r["is_valid"]]
            else:
                clean_tl, clean_lt = [], []

            stints.append({
                "stint_number":        int(stint_num),
                "compound":            compound,
                "compound_color":      compound_color,
                "laps":                lap_rows,
                "deg_slope_ms_per_lap": _deg_slope(clean_tl, clean_lt),
                "avg_lap_time_ms":     round(float(np.mean(clean_lt)), 1) if clean_lt else 0.0,
                "lap_count":           len(lap_rows),
            })

        if stints:
            drivers_data.append({
                "code":       driver_code,
                "name":       driver_name,
                "team":       team_name,
                "team_color": team_color,
                "stints":     stints,
            })
            print(f"    {driver_code}: {len(stints)} stints OK")
        else:
            print(f"    {driver_code}: no valid stints after filtering")

    if not drivers_data:
        print(f"  WARNING: no driver data produced — not uploading")
        return None

    return {
        "session_name": f"{year} {gp_slug.replace('_', ' ')} — Race",
        "year":         year,
        "gp":           gp_slug,
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
            payload = process_race_tyres(YEAR, official_name, gp_slug)
            if payload:
                key = f"processed/{YEAR}/{gp_slug}/race/tyre_degradation.json"
                upload_json(key, payload)
                print(f"  Uploaded {len(payload['drivers'])} drivers -> s3://.../{key}")
            else:
                print(f"  Skipped (no data)")
        except Exception as e:
            print(f"  FAILED: {e}")
            traceback.print_exc()

    print("\nTyre pipeline complete.")


if __name__ == "__main__":
    main()