"use client";
import { useState, useMemo, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { useF1Store } from "@/store/useF1Store";
import { api, RateLimitError } from "@/lib/api";
import StrategyGantt from "@/components/StrategyGantt";
import PositionChart from "@/components/PositionChart";
import PitStopTable from "@/components/PitStopTable";

const GPS = [
  "Australian", "Japanese", "Chinese", "Miami",
  //"Emilia Romagna", "Monaco", "Canada", "Spain","Bahrain", "Saudi Arabia", 
  //"Austria", "Britain", "Hungary", "Belgium", "Netherlands",
  //"Italy", "Azerbaijan", "Singapore", "United States", "Mexico",
  //"Brazil", "Las Vegas", "Qatar", "Abu Dhabi",
];

export default function StrategyPage() {
  const {
    year, strategyData, selectedStrategyDrivers, loading, error,
    setStrategyData, setSelectedStrategyDrivers, setLoading, setError,
  } = useF1Store();

  const [gpInput, setGpInput] = useState("Australian");
  const ganttRef = useRef<HTMLDivElement>(null);
  const [ganttWidth, setGanttWidth] = useState(800);

  // Measure container width for responsive SVG
  useEffect(() => {
    const el = ganttRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setGanttWidth(entry.contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  async function loadStrategy() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.raceStrategy(year, gpInput);
      setStrategyData(data);
      // Default: show all drivers
      setSelectedStrategyDrivers(data.drivers.map((d) => d.code));
    } catch (e: any) {
      if (e instanceof RateLimitError) {
            setError(`⏱ Rate limit reached. Try again in ${e.retryAfter}s.`);
        } else {
            setError(e.message);
        }
    } finally {
      setLoading(false);
    }
  }

  function toggleDriver(code: string) {
    setSelectedStrategyDrivers(
      selectedStrategyDrivers.includes(code)
        ? selectedStrategyDrivers.filter((c) => c !== code)
        : [...selectedStrategyDrivers, code]
    );
  }

  function selectTop10() {
    if (!strategyData) return;
    const top10 = strategyData.drivers
      .filter((d) => d.finish_position <= 10)
      .map((d) => d.code);
    setSelectedStrategyDrivers(top10);
  }

  function selectAll() {
    setSelectedStrategyDrivers(strategyData?.drivers.map((d) => d.code) ?? []);
  }

  return (
    <div className="page-content">
      <motion.div className="page-header"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}>
        <h1 className="page-title">Race Strategy</h1>
        <p className="page-subtitle">
          {strategyData ? strategyData.session_name : `${year} Race — stint & pit stop analysis`}
          {strategyData?.cached && <span className="cached-badge">cached</span>}
        </p>
      </motion.div>

      {/* Controls */}
      <motion.div className="driver-selector"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
        <select value={gpInput} onChange={(e) => setGpInput(e.target.value)} className="ctrl-select">
          {GPS.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
        <button onClick={loadStrategy} disabled={loading} className="ctrl-btn ghost-btn">
          {loading ? "Loading…" : "Load Strategy"}
        </button>
      </motion.div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {/* Driver filter pills */}
      {strategyData && (
        <motion.div className="tyre-driver-filter"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }}>
          <button className="ctrl-btn" style={{ fontSize: 11 }} onClick={selectAll}>All</button>
          <button className="ctrl-btn" style={{ fontSize: 11 }} onClick={selectTop10}>Top 10</button>
          {strategyData.drivers.map((d) => (
            <button
              key={d.code}
              onClick={() => toggleDriver(d.code)}
              className="tyre-driver-pill"
              style={{
                borderColor: selectedStrategyDrivers.includes(d.code) ? d.team_color : "var(--border)",
                color: selectedStrategyDrivers.includes(d.code) ? d.team_color : "var(--text-muted)",
                background: selectedStrategyDrivers.includes(d.code) ? d.team_color + "18" : "transparent",
              }}>
              {d.code}
            </button>
          ))}
        </motion.div>
      )}

      {!strategyData && !loading && (
        <div className="track-empty">
          <p>Select a race and click <strong>Load Strategy</strong>.</p>
        </div>
      )}

      {strategyData && (
        <div className="strategy-layout">
          {/* Gantt chart — full width */}
          <motion.div
            ref={ganttRef}
            className="strategy-gantt-col"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
            <StrategyGantt width={ganttWidth} />
          </motion.div>

          {/* Bottom row: position chart + pit stop table */}
          <motion.div className="strategy-bottom-row"
            initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
            <div className="strategy-position-col">
              <PositionChart />
            </div>
            <div className="strategy-pit-col">
              <PitStopTable />
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}