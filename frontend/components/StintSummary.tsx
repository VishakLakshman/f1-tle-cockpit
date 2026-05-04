"use client";
import { useMemo } from "react";
import { useF1Store } from "@/store/useF1Store";

export default function StintSummary() {
  const { tyreData, selectedTyreDrivers } = useF1Store();

  const drivers = useMemo(() => {
    if (!tyreData) return [];
    if (selectedTyreDrivers.length === 0) return tyreData.drivers;
    return tyreData.drivers.filter((d) => selectedTyreDrivers.includes(d.code));
  }, [tyreData, selectedTyreDrivers]);

  if (!tyreData) return null;

  return (
    <div className="stint-summary-grid">
      {drivers.map((driver) => (
        <div key={driver.code} className="stint-driver-card">
          <div className="stint-driver-header">
            <span className="driver-code" style={{ color: driver.team_color }}>
              {driver.code}
            </span>
            <span className="stint-driver-name">{driver.name}</span>
          </div>

          <div className="stint-list">
            {driver.stints.map((stint) => {
              const bestMs = Math.min(...stint.laps.filter((l) => l.is_valid).map((l) => l.lap_time_ms));
              const bestStr = stint.laps.find((l) => l.lap_time_ms === bestMs)?.lap_time_str ?? "—";

              return (
                <div key={stint.stint_number} className="stint-row">
                  <div className="stint-compound-badge"
                    style={{ background: stint.compound_color + "22", borderColor: stint.compound_color }}>
                    <span style={{ color: stint.compound_color }}>{stint.compound[0]}</span>
                  </div>
                  <div className="stint-details">
                    <div className="stint-meta">
                      Stint {stint.stint_number} · {stint.lap_count} laps
                    </div>
                    <div className="stint-times">
                      <span className="stint-avg">avg {((stint.avg_lap_time_ms) / 1000).toFixed(3)}s</span>
                      <span className="stint-best">best {bestStr}</span>
                    </div>
                  </div>
                  <div className="stint-deg"
                    style={{ color: stint.deg_slope_ms_per_lap > 100 ? "#ff6b6b" : stint.deg_slope_ms_per_lap > 0 ? "#fbbf24" : "#22c55e" }}>
                    {stint.deg_slope_ms_per_lap > 0 ? "+" : ""}
                    {stint.deg_slope_ms_per_lap.toFixed(0)}
                    <span className="stint-deg-unit">ms/lap</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}