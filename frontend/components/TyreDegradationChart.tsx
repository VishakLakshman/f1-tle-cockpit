"use client";
import { useMemo } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Line, ComposedChart,
  ReferenceLine, Legend,
} from "recharts";
import { useF1Store } from "@/store/useF1Store";
import { TyreStint } from "@/lib/api";

// Build a linear regression line for a stint's scatter points
function buildRegressionLine(
  laps: { tyre_life: number | null; lap_time_ms: number; is_valid: boolean }[],
  color: string
) {
  const valid = laps.filter((l) => l.is_valid && l.tyre_life !== null);
  if (valid.length < 3) return [];

  const xs = valid.map((l) => l.tyre_life as number);
  const ys = valid.map((l) => l.lap_time_ms);

  const n = xs.length;
  const sumX = xs.reduce((a, b) => a + b, 0);
  const sumY = ys.reduce((a, b) => a + b, 0);
  const sumXY = xs.reduce((a, x, i) => a + x * ys[i], 0);
  const sumX2 = xs.reduce((a, x) => a + x * x, 0);
  const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;

  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  return [
    { tyre_life: minX, reg_ms: slope * minX + intercept },
    { tyre_life: maxX, reg_ms: slope * maxX + intercept },
  ];
}

// Custom dot — renders valid laps normally, invalid ones faded
const CustomDot = (props: any) => {
  const { cx, cy, payload, fill } = props;
  if (!payload?.is_valid) {
    return <circle cx={cx} cy={cy} r={3} fill={fill} opacity={0.2} />;
  }
  return <circle cx={cx} cy={cy} r={5} fill={fill} opacity={0.85}
    stroke="rgba(0,0,0,0.4)" strokeWidth={1} />;
};

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div className="tyre-tooltip">
      <div className="tyre-tt-row">
        <span>Lap</span><span>{d.lap_number ?? "—"}</span>
      </div>
      <div className="tyre-tt-row">
        <span>Tyre life</span><span>{d.tyre_life ?? "—"} laps</span>
      </div>
      <div className="tyre-tt-row">
        <span>Lap time</span><span>{d.lap_time_str}</span>
      </div>
      {!d.is_valid && (
        <div className="tyre-tt-invalid">outlier / excluded</div>
      )}
    </div>
  );
};

// Format milliseconds as M:SS.mmm for Y axis ticks
function fmtMs(ms: number) {
  const s = ms / 1000;
  const m = Math.floor(s / 60);
  const rem = (s % 60).toFixed(1);
  return `${m}:${rem.padStart(4, "0")}`;
}

interface Props {
  driverCode: string;
}

export default function TyreDegradationChart({ driverCode }: Props) {
  const { tyreData } = useF1Store();

  const driver = useMemo(
    () => tyreData?.drivers.find((d) => d.code === driverCode),
    [tyreData, driverCode]
  );

  const chartData = useMemo(() => {
    if (!driver) return { scatters: [], regressions: [] };

    const scatters = driver.stints.map((stint) => ({
      stint,
      data: stint.laps
        .filter((l) => l.tyre_life !== null)
        .map((l) => ({ ...l })),
      regLine: buildRegressionLine(stint.laps, stint.compound_color),
    }));

    return { scatters };
  }, [driver]);

  if (!tyreData) return null;
  if (!driver) return (
    <div className="tyre-empty">No data for {driverCode}</div>
  );

  // Y-axis domain: min/max across all valid laps ± 1s
  const allMs = driver.stints
    .flatMap((s) => s.laps.filter((l) => l.is_valid).map((l) => l.lap_time_ms));
  const yMin = allMs.length ? Math.floor((Math.min(...allMs) - 1000) / 1000) * 1000 : 70000;
  const yMax = allMs.length ? Math.ceil((Math.max(...allMs) + 1000) / 1000) * 1000 : 100000;

  return (
    <div className="tyre-chart-card">
      <div className="tyre-chart-header">
        <span className="driver-code" style={{ color: driver.team_color }}>
          {driver.code}
        </span>
        <span className="tyre-team">{driver.team}</span>
        <div className="tyre-compound-pills">
          {driver.stints.map((s) => (
            <span key={s.stint_number} className="compound-pill"
              style={{ background: s.compound_color + "22", border: `1px solid ${s.compound_color}`, color: s.compound_color }}>
              {s.compound[0]} ×{s.lap_count}
            </span>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="tyre_life"
            type="number"
            name="Tyre Life"
            domain={["auto", "auto"]}
            tick={{ fontSize: 10, fill: "#888" }}
            label={{ value: "Tyre age (laps)", position: "insideBottom", offset: -2, fontSize: 10, fill: "#666" }}
          />
          <YAxis
            dataKey="lap_time_ms"
            type="number"
            domain={[yMin, yMax]}
            tick={{ fontSize: 10, fill: "#888" }}
            tickFormatter={fmtMs}
            width={52}
          />
          <Tooltip content={<CustomTooltip />} />

          {chartData.scatters?.map(({ stint, data, regLine }) => (
            <>
              {/* Scatter points */}
              <Scatter
                key={`scatter-${stint.stint_number}`}
                name={`${stint.compound} stint ${stint.stint_number}`}
                data={data}
                fill={stint.compound_color}
                shape={<CustomDot />}
              />
              {/* Regression line */}
              {regLine.length === 2 && (
                <Line
                  key={`reg-${stint.stint_number}`}
                  data={regLine}
                  dataKey="reg_ms"
                  dot={false}
                  stroke={stint.compound_color}
                  strokeWidth={1.5}
                  strokeDasharray="5 3"
                  opacity={0.7}
                  legendType="none"
                />
              )}
            </>
          ))}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Deg slope summary */}
      <div className="deg-slope-row">
        {driver.stints.map((s) => (
          <div key={s.stint_number} className="deg-slope-item">
            <span className="compound-dot" style={{ background: s.compound_color }} />
            <span className="deg-label">{s.compound}</span>
            <span className="deg-value" style={{ color: s.deg_slope_ms_per_lap > 0 ? "#ff6b6b" : "#22c55e" }}>
              {s.deg_slope_ms_per_lap > 0 ? "+" : ""}{s.deg_slope_ms_per_lap.toFixed(0)}ms/lap
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}