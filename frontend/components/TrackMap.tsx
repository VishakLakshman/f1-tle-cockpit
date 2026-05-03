"use client";
import { useMemo } from "react";
import { useF1Store } from "@/store/useF1Store";
import { TrackPoint } from "@/lib/api";

function buildSVGPath(points: TrackPoint[]): string {
  if (!points.length) return "";
  const [first, ...rest] = points;
  const d = [`M ${first.x.toFixed(1)} ${first.y.toFixed(1)}`];
  for (const p of rest) d.push(`L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`);
  d.push("Z");
  return d.join(" ");
}

function interpolatePosition(points: TrackPoint[], pct: number): { x: number; y: number } {
  if (!points.length) return { x: 0, y: 0 };
  // Find the two track points around the current pct
  let lo = 0, hi = points.length - 1;
  for (let i = 0; i < points.length - 1; i++) {
    if (points[i].distance <= pct && points[i + 1].distance >= pct) {
      lo = i; hi = i + 1; break;
    }
  }
  const a = points[lo], b = points[hi];
  const span = b.distance - a.distance;
  const t = span === 0 ? 0 : (pct - a.distance) / span;
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
}

export default function TrackMap() {
  const { ghostData, progressPct } = useF1Store();

  const d1Path = useMemo(() =>
    ghostData ? buildSVGPath(ghostData.driver1.track_path) : "", [ghostData]);

  const ghost1Pos = useMemo(() =>
    ghostData ? interpolatePosition(ghostData.driver1.track_path, progressPct) : null,
    [ghostData, progressPct]);

  const ghost2Pos = useMemo(() =>
    ghostData ? interpolatePosition(ghostData.driver2.track_path, progressPct) : null,
    [ghostData, progressPct]);

  if (!ghostData) {
    return (
      <div className="track-empty">
        <p>Select a session and drivers, then click <strong>Load Ghost</strong>.</p>
      </div>
    );
  }

  const d1 = ghostData.driver1;
  const d2 = ghostData.driver2;

  return (
    <div className="track-map-card">
      <div className="track-header">
        <div className="driver-badge" style={{ borderColor: d1.team_color }}>
          <span className="driver-code">{d1.driver}</span>
          <span className="lap-time">{d1.lap_time}</span>
        </div>
        <div className="vs-label">vs</div>
        <div className="driver-badge" style={{ borderColor: d2.team_color }}>
          <span className="driver-code">{d2.driver}</span>
          <span className="lap-time">{d2.lap_time}</span>
        </div>
      </div>

      <svg
        viewBox="0 0 1000 1000"
        className="track-svg"
        aria-label={`Track map — ${ghostData.session_name}`}
      >
        {/* Track outline (grey halo) */}
        <path d={d1Path} fill="none" stroke="var(--track-halo)" strokeWidth="18" strokeLinecap="round" strokeLinejoin="round" />
        {/* Track surface */}
        <path d={d1Path} fill="none" stroke="var(--track-surface)" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" />

        {/* Ghost dots */}
        {ghost2Pos && (
          <circle cx={ghost2Pos.x} cy={ghost2Pos.y} r={14}
            fill={d2.team_color} stroke="#000" strokeWidth={2} opacity={0.85} />
        )}
        {ghost1Pos && (
          <circle cx={ghost1Pos.x} cy={ghost1Pos.y} r={14}
            fill={d1.team_color} stroke="#fff" strokeWidth={2} />
        )}

        {/* Driver labels next to dots */}
        {ghost1Pos && (
          <text x={ghost1Pos.x + 18} y={ghost1Pos.y + 5} fill={d1.team_color}
            fontSize={22} fontWeight="700" fontFamily="monospace">{d1.driver}</text>
        )}
        {ghost2Pos && (
          <text x={ghost2Pos.x + 18} y={ghost2Pos.y + 5} fill={d2.team_color}
            fontSize={22} fontWeight="700" fontFamily="monospace">{d2.driver}</text>
        )}
      </svg>
    </div>
  );
}