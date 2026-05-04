"use client";
import { useEffect, useRef } from "react";
import { useF1Store } from "@/store/useF1Store";
import { api } from "@/lib/api";

const GPS = ["Bahrain", "Saudi Arabia", "Australia", "Japan", "China",
  "Miami", "Emilia Romagna", "Monaco", "Canada", "Spain",
  "Austria", "Britain", "Hungary", "Belgium", "Netherlands",
  "Italy", "Azerbaijan", "Singapore", "United States", "Mexico",
  "Brazil", "Las Vegas", "Qatar", "Abu Dhabi"];

const YEARS = [2025,2024];

export default function GlobalHeader() {
  const { year, gp, session, progressPct, isPlaying,
    setSelection, setProgress, togglePlay,
    setSessionInfo, setLoading, setError, ghostData } = useF1Store();

  const rafRef = useRef<number | null>(null);
  const lastTRef = useRef<number | null>(null);

  // Auto-play animation
  useEffect(() => {
    if (!isPlaying) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      lastTRef.current = null;
      return;
    }
    const step = (t: number) => {
      if (lastTRef.current !== null) {
        const dt = t - lastTRef.current;
        setProgress(Math.min(1, progressPct + dt / 60000)); // 60s = full lap
      }
      lastTRef.current = t;
      rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [isPlaying, progressPct, setProgress]);

  // Stop at end
  useEffect(() => {
    if (progressPct >= 1) togglePlay();
  }, [progressPct]);

  async function loadSession() {
    setLoading(true);
    setError(null);
    try {
      const info = await api.sessionInfo(year, gp, session);
      setSessionInfo(info);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <header className="global-header">
      <div className="header-controls">
        <select value={year} onChange={(e) => setSelection({ year: +e.target.value })} className="ctrl-select">
          {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>

        <select value={gp} onChange={(e) => setSelection({ gp: e.target.value })} className="ctrl-select">
          {GPS.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>

        <select value={session} onChange={(e) => setSelection({ session: e.target.value })} className="ctrl-select">
          {["Q1", "Q2", "Q3"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        <button onClick={loadSession} className="ctrl-btn">Load Session</button>
      </div>

      <div className="playback-controls">
        {ghostData && (
          <>
            <button onClick={togglePlay} className="play-btn">
              {isPlaying ? "⏸" : "▶"}
            </button>
            <input
              type="range" min={0} max={1} step={0.001}
              value={progressPct}
              onChange={(e) => setProgress(+e.target.value)}
              className="timeline-slider"
            />
            <span className="lap-pct">{(progressPct * 100).toFixed(1)}%</span>
          </>
        )}
      </div>
    </header>
  );
}