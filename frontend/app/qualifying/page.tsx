"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { useF1Store } from "@/store/useF1Store";
import { api } from "@/lib/api";
import TrackMap from "@/components/TrackMap";
import DeltaChart from "@/components/DeltaChart";
import TelemetryPanel from "@/components/TelemetryPanel";

export default function QualifyingPage() {
  const {
    year, gp, session, driver1, driver2,
    sessionInfo, ghostData, loading, error,
    setSelection, setGhostData, setLoading, setError,
  } = useF1Store();

  const [d1Input, setD1Input] = useState(driver1);
  const [d2Input, setD2Input] = useState(driver2);

  async function loadGhost() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.ghostLap(year, gp, session, d1Input, d2Input);
      setSelection({ driver1: d1Input, driver2: d2Input });
      setGhostData(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const drivers = sessionInfo?.drivers ?? [];

  return (
    <div className="page-content">
      <motion.div
        className="page-header"
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <h1 className="page-title">Qualifying Ghost</h1>
        <p className="page-subtitle">
          {ghostData ? ghostData.session_name : `${year} ${gp} — ${session}`}
          {ghostData?.cached && <span className="cached-badge">cached</span>}
        </p>
      </motion.div>

      {/* Driver selector */}
      <motion.div
        className="driver-selector"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.15 }}
      >
        {drivers.length > 0 ? (
          <>
            <select value={d1Input} onChange={(e) => setD1Input(e.target.value)} className="ctrl-select">
              {drivers.map((d) => (
                <option key={d.code} value={d.code}>{d.code} — {d.name}</option>
              ))}
            </select>
            <span className="vs-label">vs</span>
            <select value={d2Input} onChange={(e) => setD2Input(e.target.value)} className="ctrl-select">
              {drivers.map((d) => (
                <option key={d.code} value={d.code}>{d.code} — {d.name}</option>
              ))}
            </select>
          </>
        ) : (
          <>
            <input value={d1Input} onChange={(e) => setD1Input(e.target.value.toUpperCase())}
              className="ctrl-select" placeholder="e.g. VER" maxLength={3} style={{ width: 80 }} />
            <span className="vs-label">vs</span>
            <input value={d2Input} onChange={(e) => setD2Input(e.target.value.toUpperCase())}
              className="ctrl-select" placeholder="e.g. LEC" maxLength={3} style={{ width: 80 }} />
          </>
        )}
        <button onClick={loadGhost} disabled={loading} className="ctrl-btn ghost-btn">
          {loading ? "Loading…" : "Load Ghost"}
        </button>
      </motion.div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {/* Bento grid */}
      <div className="bento-grid">
        <motion.div className="bento-primary"
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
        >
          <TrackMap />
        </motion.div>

        <motion.div className="bento-side"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3 }}
        >
          <TelemetryPanel />
        </motion.div>

        <motion.div className="bento-bottom"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <DeltaChart />
        </motion.div>
      </div>
    </div>
  );
}