"use client";
import { useMemo } from "react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ReferenceLine, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { useF1Store } from "@/store/useF1Store";

export default function DeltaChart() {
  const { ghostData, progressPct } = useF1Store();

  const chartData = useMemo(() => {
    if (!ghostData) return [];
    return ghostData.delta.map((d) => ({
      dist: (d.distance_pct * 100).toFixed(1),
      delta: +(d.delta_ms / 1000).toFixed(3), // convert to seconds
    }));
  }, [ghostData]);

  const currentDist = progressPct * 100;

  if (!ghostData) return null;

  const d1 = ghostData.driver1;
  const d2 = ghostData.driver2;
  const finalDelta = ((d1.lap_time_ms - d2.lap_time_ms) / 1000).toFixed(3);

  return (
    <div className="chart-card">
      <div className="chart-title">
        Delta Time — {d1.driver} vs {d2.driver}
        <span className="delta-final" style={{ color: +finalDelta > 0 ? d2.team_color : d1.team_color }}>
          {+finalDelta > 0 ? `+${finalDelta}s` : `${finalDelta}s`} final gap
        </span>
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={chartData} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="dPos" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={d2.team_color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={d2.team_color} stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="dNeg" x1="0" y1="1" x2="0" y2="0">
              <stop offset="5%" stopColor={d1.team_color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={d1.team_color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="dist" tick={{ fontSize: 10, fill: "#888" }}
            tickFormatter={(v) => `${v}%`} interval={49} />
          <YAxis tick={{ fontSize: 10, fill: "#888" }}
            tickFormatter={(v) => `${v > 0 ? "+" : ""}${v}s`} />
          <Tooltip
            contentStyle={{ background: "#111", border: "1px solid #333", borderRadius: 6 }}
            formatter={(v: number) => [`${v > 0 ? "+" : ""}${v}s`, "Δ"]}
            labelFormatter={(l) => `${l}% of lap`}
          />
          <ReferenceLine y={0} stroke="#555" strokeWidth={1} />
          <ReferenceLine x={currentDist.toFixed(1)} stroke="#fff" strokeWidth={1.5}
            strokeDasharray="4 4" />
          <Area type="monotone" dataKey="delta" stroke={d1.team_color}
            strokeWidth={2} fill="url(#dPos)" />
        </AreaChart>
      </ResponsiveContainer>

      <div className="delta-legend">
        <span style={{ color: d1.team_color }}>▲ {d1.driver} faster</span>
        <span style={{ color: d2.team_color }}>▼ {d2.driver} faster</span>
      </div>
    </div>
  );
}