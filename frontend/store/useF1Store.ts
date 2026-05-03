import { create } from "zustand";
import { GhostResponse, SessionInfo } from "@/lib/api";

interface F1State {
  // Session selection
  year: number;
  gp: string;
  session: string;
  driver1: string;
  driver2: string;

  // Playback
  progressPct: number;   // 0-1, controlled by the global timeline slider
  isPlaying: boolean;

  // Data
  ghostData: GhostResponse | null;
  sessionInfo: SessionInfo | null;
  loading: boolean;
  error: string | null;

  // Actions
  setSelection: (fields: Partial<Pick<F1State, "year" | "gp" | "session" | "driver1" | "driver2">>) => void;
  setProgress: (pct: number) => void;
  togglePlay: () => void;
  setGhostData: (data: GhostResponse | null) => void;
  setSessionInfo: (info: SessionInfo | null) => void;
  setLoading: (v: boolean) => void;
  setError: (msg: string | null) => void;
}

export const useF1Store = create<F1State>((set) => ({
  year: 2024,
  gp: "Monaco",
  session: "Q3",
  driver1: "VER",
  driver2: "LEC",

  progressPct: 0,
  isPlaying: false,

  ghostData: null,
  sessionInfo: null,
  loading: false,
  error: null,

  setSelection: (fields) => set((s) => ({ ...s, ...fields })),
  setProgress: (pct) => set({ progressPct: pct }),
  togglePlay: () => set((s) => ({ isPlaying: !s.isPlaying })),
  setGhostData: (data) => set({ ghostData: data }),
  setSessionInfo: (info) => set({ sessionInfo: info }),
  setLoading: (v) => set({ loading: v }),
  setError: (msg) => set({ error: msg }),
}));