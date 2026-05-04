"use client";
import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { useF1Store } from "@/store/useF1Store";
import { api } from "@/lib/api";
import TyreDegradationChart from "@/components/TyreDegradationChart";
import StintSummary from "@/components/StintSummary";

const GPS = [
  "Bahrain", "Saudi Arabia", "Australian", "Japan", "China",
  "Miami", "Emilia Romagna", "Monaco", "Canada", "Spain",
  "Austria", "Britain", "Hungary", "Belgium", "Netherlands",
  "Italy", "Azerbaijan", "Singapore", "United States", "Mexico",
  "Brazil", "Las Vegas", "Qatar", "Abu Dhabi",
];

export default function TyresPage() {
  const {
    year, tyreData, selectedTyreDrivers, loading, error,
    setTyreData, setSelectedTyreDrivers, setLoading, setError,
  } = useF1Store();

  const [gpInput, setGpInput] = useState("Bahrain");

  async function loadTyres() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.tyreDegradation(year, gpInput);
      setTyreData(data);
      // Default: show top 5 drivers by total laps
      const top5 = [...data.drivers]
        .sort((a, b) =>
          b.stints.reduce((s, st) => s + st.lap_count, 0) -
          a.stints.reduce((s, st) => s + st.lap_count, 0)
        )
        .slice(0, 5)
        .map((d) => d.code);
      setSelectedTyreDrivers(top5);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const displayedDrivers = useMemo(() => {
    if (!tyreData) return [];
    if (selectedTyreDrivers.length === 0) return tyreData.drivers;
    return tyreData.drivers.filter((d) => selectedTyreDrivers.includes(d.code));
  }, [tyreData, selectedTyreDrivers]);

  function toggleDriver(code: string) {
    setSelectedTyreDrivers(
      selectedTyreDrivers.includes(code)
        ? selectedTyreDrivers.filter((c) => c !== code)
        : [...selectedTyreDrivers, code]
    );
  }

  function selectAll() {
    setSelectedTyreDrivers(tyreData?.drivers.map((d) => d.code) ?? []);
  }

  return (
    <div className="page-content">
      <motion.div className="page-header"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}>
        <h1 className="page-title">Tyre Degradation</h1>
        <p className="page-subtitle">
          {tyreData ? tyreData.session_name : `${year} Race — pace & deg analysis`}
          {tyreData?.cached && <span className="cached-badge">cached</span>}
        </p>
      </motion.div>

      {/* Controls */}
      <motion.div className="driver-selector"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
        <select value={gpInput} onChange={(e) => setGpInput(e.target.value)} className="ctrl-select">
          {GPS.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
        <button onClick={loadTyres} disabled={loading} className="ctrl-btn ghost-btn">
          {loading ? "Loading…" : "Load Race Data"}
        </button>
      </motion.div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {/* Driver filter pills */}
      {tyreData && (
        <motion.div className="tyre-driver-filter"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
          <button className="ctrl-btn" style={{ fontSize: 11 }} onClick={selectAll}>
            All
          </button>
          {tyreData.drivers.map((d) => (
            <button
              key={d.code}
              onClick={() => toggleDriver(d.code)}
              className="tyre-driver-pill"
              style={{
                borderColor: selectedTyreDrivers.includes(d.code) ? d.team_color : "var(--border)",
                color: selectedTyreDrivers.includes(d.code) ? d.team_color : "var(--text-muted)",
                background: selectedTyreDrivers.includes(d.code) ? d.team_color + "18" : "transparent",
              }}>
              {d.code}
            </button>
          ))}
        </motion.div>
      )}

      {!tyreData && !loading && (
        <div className="track-empty">
          <p>Select a race and click <strong>Load Race Data</strong>.</p>
        </div>
      )}

      {tyreData && (
        <div className="tyre-layout">
          {/* Left: degradation charts (one per selected driver) */}
          <motion.div className="tyre-charts-col"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 }}>
            <div className="chart-title">Lap Time vs Tyre Age</div>
            <div className="tyre-charts-stack">
              {displayedDrivers.map((driver) => (
                <TyreDegradationChart key={driver.code} driverCode={driver.code} />
              ))}
              {displayedDrivers.length === 0 && (
                <div className="tyre-empty">Select at least one driver above.</div>
              )}
            </div>
          </motion.div>

          {/* Right: stint summary cards */}
          <motion.div className="tyre-summary-col"
            initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }}>
            <div className="chart-title">Stint Summary</div>
            <StintSummary />
          </motion.div>
        </div>
      )}
    </div>
  );
}