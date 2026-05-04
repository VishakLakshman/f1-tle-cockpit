"use client";
import { useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { useF1Store } from "@/store/useF1Store";

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="tyre-tooltip">
      <div style={{ marginBottom: 4, color: "var(--text-muted)", fontSize: 10 }}>
        Lap {label}
      </div>
      {payload
        .sort((a: any, b: any) => a.value - b.value)
        .map((p: any) => (
          <div key={p.dataKey} className="tyre-tt-row">
            <span style={{ color: p.color }}>P{p.value}</span>
            <span style={{ color: p.color, fontWeight: 700 }}>{p.dataKey}</span>
          </div>
        ))}
    </div>
  );
};

export default function PositionChart() {
  const { strategyData, selectedStrategyDrivers, highlightedDriver, setHighlightedDriver } = useF1Store();

  const { chartData, drivers } = useMemo(() => {
    if (!strategyData) return { chartData: [], drivers: [] };

    const filtered = selectedStrategyDrivers.length > 0
      ? strategyData.drivers.filter((d) => selectedStrategyDrivers.includes(d.code))
      : strategyData.drivers;

    // Build a map: lap -> {driverCode: position}
    const lapMap: Record<number, Record<string, number>> = {};
    for (const driver of filtered) {
      for (const { lap, position } of driver.positions) {
        if (!lapMap[lap]) lapMap[lap] = {};
        lapMap[lap][driver.code] = position;
      }
    }

    const chartData = Object.entries(lapMap)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([lap, positions]) => ({ lap: Number(lap), ...positions }));

    return { chartData, drivers: filtered };
  }, [strategyData, selectedStrategyDrivers]);

  if (!strategyData || drivers.length === 0) return null;

  // Find pit stop laps for reference lines
  const allPitLaps = new Set<number>();
  drivers.forEach((d) => d.pit_stops.forEach((p) => allPitLaps.add(p.lap)));

  return (
    <div className="chart-card">
      <div className="chart-title">Position Over Race</div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="lap"
            tick={{ fontSize: 10, fill: "#888" }}
            label={{ value: "Lap", position: "insideBottom", offset: -2, fontSize: 10, fill: "#666" }}
          />
          <YAxis
            reversed
            domain={[1, 20]}
            tick={{ fontSize: 10, fill: "#888" }}
            tickFormatter={(v) => `P${v}`}
            width={32}
          />
          <Tooltip content={<CustomTooltip />} />

          {drivers.map((driver) => {
            const isHighlighted = highlightedDriver === driver.code;
            const isDimmed = highlightedDriver !== null && !isHighlighted;
            return (
              <Line
                key={driver.code}
                type="monotone"
                dataKey={driver.code}
                stroke={driver.team_color}
                strokeWidth={isHighlighted ? 2.5 : isDimmed ? 0.5 : 1.5}
                dot={false}
                opacity={isDimmed ? 0.2 : 1}
                activeDot={{
                  r: 4,
                  onMouseEnter: () => setHighlightedDriver(driver.code),
                  onMouseLeave: () => setHighlightedDriver(null),
                }}
              />
            );
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}