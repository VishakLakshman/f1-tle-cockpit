"use client";
import { useMemo } from "react";
import { useF1Store } from "@/store/useF1Store";

export default function PitStopTable() {
  const { strategyData, selectedStrategyDrivers, highlightedDriver, setHighlightedDriver } = useF1Store();

  const rows = useMemo(() => {
    if (!strategyData) return [];
    const drivers = selectedStrategyDrivers.length > 0
      ? strategyData.drivers.filter((d) => selectedStrategyDrivers.includes(d.code))
      : strategyData.drivers;

    // Flatten all pit stops across drivers, sorted by lap
    return drivers
      .flatMap((d) =>
        d.pit_stops.map((stop) => ({
          driver:          d.code,
          team_color:      d.team_color,
          finish_position: d.finish_position,
          ...stop,
        }))
      )
      .sort((a, b) => a.lap - b.lap);
  }, [strategyData, selectedStrategyDrivers]);

  if (!strategyData || rows.length === 0) return null;

  return (
    <div className="pit-table-card">
      <div className="chart-title">Pit Stop Log</div>
      <div className="pit-table-scroll">
        <table className="pit-table">
          <thead>
            <tr>
              <th>Driver</th>
              <th>Stop</th>
              <th>Lap</th>
              <th>Duration</th>
              <th>From</th>
              <th>→</th>
              <th>To</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const isHighlighted = highlightedDriver === row.driver;
              const isDimmed = highlightedDriver !== null && !isHighlighted;
              return (
                <tr
                  key={i}
                  className={`pit-row ${isHighlighted ? "highlighted" : ""} ${isDimmed ? "dimmed" : ""}`}
                  onMouseEnter={() => setHighlightedDriver(row.driver)}
                  onMouseLeave={() => setHighlightedDriver(null)}
                >
                  <td>
                    <span style={{ color: row.team_color, fontWeight: 700, fontFamily: "var(--mono)" }}>
                      {row.driver}
                    </span>
                  </td>
                  <td style={{ color: "var(--text-muted)" }}>#{row.stop_number}</td>
                  <td style={{ fontFamily: "var(--mono)" }}>{row.lap}</td>
                  <td style={{ fontFamily: "var(--mono)" }}>
                    {row.pit_duration_s != null
                      ? <span className={row.pit_duration_s < 3 ? "fast-stop" : row.pit_duration_s > 5 ? "slow-stop" : ""}>
                          {row.pit_duration_s.toFixed(2)}s
                        </span>
                      : <span style={{ color: "var(--text-muted)" }}>—</span>
                    }
                  </td>
                  <td>
                    <CompoundBadge compound={row.from_compound} />
                  </td>
                  <td style={{ color: "var(--text-muted)", fontSize: 10 }}>→</td>
                  <td>
                    <CompoundBadge compound={row.to_compound} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const COMPOUND_COLORS: Record<string, string> = {
  SOFT:    "#FF3333",
  MEDIUM:  "#FFD700",
  HARD:    "#FFFFFF",
  INTER:   "#39B54A",
  WET:     "#0067FF",
  UNKNOWN: "#888888",
};

function CompoundBadge({ compound }: { compound: string }) {
  const color = COMPOUND_COLORS[compound] ?? "#888";
  return (
    <span className="compound-pill"
      style={{ background: color + "22", border: `1px solid ${color}`, color }}>
      {compound[0]}
    </span>
  );
}