"use client";
import { useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, ReferenceLine,
} from "recharts";
import { useF1Store } from "@/store/useF1Store";
import { TelemetryPoint } from "@/lib/api";

function sampleTelemetry(points: TelemetryPoint[], n = 400) {
  const step = Math.max(1, Math.floor(points.length / n));
  return points.filter((_, i) => i % step === 0);
}

interface TelRow {
  dist: string;
  speed1: number;
  speed2: number;
  throttle1: number;
  throttle2: number;
}

export default function TelemetryPanel() {
  const { ghostData, progressPct } = useF1Store();

  const chartData = useMemo<TelRow[]>(() => {
    if (!ghostData) return [];
    const t1 = sampleTelemetry(ghostData.driver1.telemetry);
    const t2 = sampleTelemetry(ghostData.driver2.telemetry);
    const len = Math.min(t1.length, t2.length);
    return Array.from({ length: len }, (_, i) => ({
      dist: (t1[i].distance_pct * 100).toFixed(1),
      speed1: t1[i].speed,
      speed2: t2[i].speed,
      throttle1: t1[i].throttle,
      throttle2: t2[i].throttle,
    }));
  }, [ghostData]);

  // Live telemetry snapshot at current progress
  const liveTel1 = useMemo(() => {
    if (!ghostData) return null;
    const points = ghostData.driver1.telemetry;
    const idx = Math.min(
      Math.floor(progressPct * points.length),
      points.length - 1
    );
    return points[idx];
  }, [ghostData, progressPct]);

  const liveTel2 = useMemo(() => {
    if (!ghostData) return null;
    const points = ghostData.driver2.telemetry;
    const idx = Math.min(
      Math.floor(progressPct * points.length),
      points.length - 1
    );
    return points[idx];
  }, [ghostData, progressPct]);

  if (!ghostData || !liveTel1 || !liveTel2) return null;

  const d1 = ghostData.driver1;
  const d2 = ghostData.driver2;
  const currentDist = (progressPct * 100).toFixed(1);

  return (
    <div className="telemetry-card">
      {/* Live readouts */}
      <div className="live-readouts">
        {[
          { label: "Speed", v1: `${liveTel1.speed.toFixed(0)} km/h`, v2: `${liveTel2.speed.toFixed(0)} km/h` },
          { label: "Gear", v1: liveTel1.gear, v2: liveTel2.gear },
          { label: "Throttle", v1: `${liveTel1.throttle.toFixed(0)}%`, v2: `${liveTel2.throttle.toFixed(0)}%` },
          { label: "Brake", v1: liveTel1.brake ? "ON" : "—", v2: liveTel2.brake ? "ON" : "—" },
          { label: "DRS", v1: liveTel1.drs > 0 ? "OPEN" : "—", v2: liveTel2.drs > 0 ? "OPEN" : "—" },
        ].map(({ label, v1, v2 }) => (
          <div className="readout-row" key={label}>
            <span className="readout-label">{label}</span>
            <span className="readout-val" style={{ color: d1.team_color }}>{v1}</span>
            <span className="readout-val" style={{ color: d2.team_color }}>{v2}</span>
          </div>
        ))}
      </div>

      {/* Speed trace */}
      <div className="chart-title" style={{ marginTop: 16 }}>Speed Trace</div>
      <ResponsiveContainer width="100%" height={140}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="dist" hide />
          <YAxis tick={{ fontSize: 10, fill: "#888" }} domain={[0, 380]} />
          <Tooltip
            contentStyle={{ background: "#111", border: "1px solid #333", borderRadius: 6 }}
            labelFormatter={(l) => `${l}% of lap`}
          />
          <ReferenceLine x={currentDist} stroke="#fff" strokeWidth={1.5} strokeDasharray="4 4" />
          <Line type="monotone" dataKey="speed1" stroke={d1.team_color}
            dot={false} strokeWidth={1.5} name={d1.driver} />
          <Line type="monotone" dataKey="speed2" stroke={d2.team_color}
            dot={false} strokeWidth={1.5} name={d2.driver} strokeDasharray="4 2" />
        </LineChart>
      </ResponsiveContainer>

      {/* Throttle trace */}
      <div className="chart-title" style={{ marginTop: 8 }}>Throttle %</div>
      <ResponsiveContainer width="100%" height={100}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="dist" hide />
          <YAxis tick={{ fontSize: 10, fill: "#888" }} domain={[0, 100]} />
          <ReferenceLine x={currentDist} stroke="#fff" strokeWidth={1.5} strokeDasharray="4 4" />
          <Line type="monotone" dataKey="throttle1" stroke={d1.team_color}
            dot={false} strokeWidth={1.5} name={d1.driver} />
          <Line type="monotone" dataKey="throttle2" stroke={d2.team_color}
            dot={false} strokeWidth={1.5} name={d2.driver} strokeDasharray="4 2" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}