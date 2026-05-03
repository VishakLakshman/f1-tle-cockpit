"""
Offline pre-processing pipeline for F1 2025 season.

Run this ONCE on your local machine or in a GitHub Actions job:
    python pipeline/process_season.py

FastF1 session name reference:
  ✓ "Qualifying"    — full qualifying session (Q1+Q2+Q3 segments inside)
  ✗ "Q1"/"Q2"/"Q3" — NOT valid FastF1 session types

We load "Qualifying" once, then split laps by the "Session" column
to get Q1 / Q2 / Q3 segments separately.

S3 key structure:
  processed/2025/{gp_slug}/{segment}/session_info.json
  processed/2025/{gp_slug}/{segment}/{driver1}_{driver2}.json
"""

import os
import itertools
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
SEGMENTS = ["Q1", "Q2", "Q3"]


# ──────────────────────────────────────────────────────────────────────────────
# Schedule helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_completed_gps(year: int) -> list[tuple[str, str]]:
    """
    Returns list of (official_name, slug) for completed races.
    official_name → passed to fastf1.get_session()
    slug          → used in S3 keys (URL-friendly)
    """
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    today = datetime.now()
    past = schedule[schedule["EventDate"] < today]
    results = []
    for _, row in past.iterrows():
        official = row["EventName"]  # e.g. "Bahrain Grand Prix"
        slug = official.replace(" Grand Prix", "").replace(" ", "_")
        results.append((official, slug))
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Processing helpers
# ──────────────────────────────────────────────────────────────────────────────

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
    """
    Extract the fastest lap for a driver from a pre-filtered segment lap set.
    segment_laps is already filtered to Q1, Q2, or Q3 laps only.
    """
    driver_laps = segment_laps[segment_laps["Driver"] == code]
    if driver_laps.empty:
        raise ValueError(f"No laps found for driver {code} in this segment")

    lap = driver_laps.pick_fastest()
    tel = lap.get_telemetry().add_distance().dropna(subset=["Distance"])
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
            "distance": float(dist[i]),
            "distance_pct": float(dist_pct[i]),
            "speed": float(tel["Speed"].iloc[i]),
            "throttle": float(tel["Throttle"].iloc[i]),
            "brake": bool(tel["Brake"].iloc[i]),
            "rpm": int(tel["RPM"].iloc[i]),
            "gear": int(tel["nGear"].iloc[i]),
            "drs": int(tel["DRS"].iloc[i]),
        }
        for i in range(len(dist))
    ]

    return (
        {
            "driver": code,
            "team": lap["Team"] if "Team" in lap.index else "",
            "team_color": "",  # filled below from session.get_driver()
            "lap_time": _lap_time_str(lap["LapTime"]),
            "lap_time_ms": _ms(lap["LapTime"]),
            "telemetry": telemetry,
            "track_path": track_path,
        },
        dist,
        tel["Time"].values,
    )


def enrich_driver_color(session, driver_data: dict) -> dict:
    """Add team color from session driver info."""
    try:
        info = session.get_driver(driver_data["driver"])
        driver_data["team"] = info["TeamName"]
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

    delta_ms = (_resample(to_s(d1_time), d1_dist, common_dist) -
                _resample(to_s(d2_time), d2_dist, common_dist)) * 1000

    delta = [
        {"distance": float(common_dist[i]),
         "distance_pct": float(common_dist[i] / max(d1_dist[-1], d2_dist[-1])),
         "delta_ms": float(delta_ms[i])}
        for i in range(len(common_dist))
    ]

    return {
        "session_name": f"{year} {gp_slug.replace('_', ' ')} — {segment}",
        "year": year,
        "gp": gp_slug,
        "session": segment,
        "driver1": d1_data,
        "driver2": d2_data,
        "delta": delta,
        "track_length_m": float(max(d1_dist[-1], d2_dist[-1])),
        "cached": False,
    }


def build_session_info(year, gp_slug, segment, session, drivers_in_segment) -> dict:
    drivers = []
    for abbr in drivers_in_segment:
        try:
            info = session.get_driver(abbr)
            drivers.append({
                "code": abbr,
                "name": info["FullName"],
                "team": info["TeamName"],
                "team_color": "#" + info.get("TeamColor", "ffffff"),
            })
        except Exception:
            drivers.append({"code": abbr, "name": abbr, "team": "", "team_color": "#ffffff"})
    return {"year": year, "gp": gp_slug, "sessions": SEGMENTS, "drivers": drivers}


# ──────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────────────────────────

def process_gp(year: int, official_name: str, gp_slug: str):
    print(f"\n{'='*60}")
    print(f"  {year} {official_name}  (slug: {gp_slug})")
    print(f"{'='*60}")

    # Load the full Qualifying session ONCE — contains Q1+Q2+Q3 laps
    try:
        session = fastf1.get_session(year, official_name, "Qualifying")
        session.load(telemetry=True, weather=False, messages=False, laps=True)
    except Exception as e:
        print(f"  ✗ Could not load Qualifying session: {e}")
        return

    all_laps = session.laps

    # FastF1 stores segment in a column — try both known column names
    segment_col = None
    for col in ["Session", "QualifyingPart"]:
        if col in all_laps.columns:
            segment_col = col
            break

    if segment_col is None:
        # Fallback: if no segment column, treat the whole session as Q3
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

        # Drivers who set a timed lap in this segment
        drivers_in_segment = sorted(segment_laps["Driver"].dropna().unique().tolist())
        print(f"     Drivers: {drivers_in_segment}")

        # Upload session_info
        try:
            info = build_session_info(year, gp_slug, segment, session, drivers_in_segment)
            upload_json(f"processed/{year}/{gp_slug}/{segment}/session_info.json", info)
            print(f"     ✓ session_info uploaded ({len(drivers_in_segment)} drivers)")
        except Exception as e:
            print(f"     ✗ session_info failed: {e}")

        # All driver pairs
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


def main():
    print(f"Fetching 2026 schedule...")
    gps = get_completed_gps(YEAR)

    if not gps:
        print("No completed races found for 2025 yet.")
        return

    print(f"Found {len(gps)} completed races:")
    for official, slug in gps:
        print(f"  {official} → slug: {slug}")

    for official_name, gp_slug in gps:
        process_gp(YEAR, official_name, gp_slug)

    print("\n✅ Pipeline complete.")


if __name__ == "__main__":
    main()