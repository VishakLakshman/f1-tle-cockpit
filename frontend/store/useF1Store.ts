import { create } from "zustand";
import { GhostResponse, SessionInfo, TyreDegradationResponse } from "@/lib/api";

interface F1State {
  // Session selection (shared across modules)
  year: number;
  gp: string;
  session: string;
  driver1: string;
  driver2: string;

  // Playback (Module A)
  progressPct: number;
  isPlaying: boolean;

  // Module A data
  ghostData: GhostResponse | null;
  sessionInfo: SessionInfo | null;

  // Module B data
  tyreData: TyreDegradationResponse | null;
  selectedTyreDrivers: string[];

  // UI state
  loading: boolean;
  error: string | null;

  // Actions
  setSelection: (fields: Partial<Pick<F1State, "year" | "gp" | "session" | "driver1" | "driver2">>) => void;
  setProgress: (pct: number) => void;
  togglePlay: () => void;
  setGhostData: (data: GhostResponse | null) => void;
  setSessionInfo: (info: SessionInfo | null) => void;
  setTyreData: (data: TyreDegradationResponse | null) => void;
  setSelectedTyreDrivers: (drivers: string[]) => void;
  setLoading: (v: boolean) => void;
  setError: (msg: string | null) => void;
}

export const useF1Store = create<F1State>((set) => ({
  year: 2025,
  gp: "Bahrain",
  session: "Q3",
  driver1: "VER",
  driver2: "LEC",

  progressPct: 0,
  isPlaying: false,

  ghostData: null,
  sessionInfo: null,
  tyreData: null,
  selectedTyreDrivers: [],

  loading: false,
  error: null,

  setSelection: (fields) => set((s) => ({ ...s, ...fields })),
  setProgress: (pct) => set({ progressPct: pct }),
  togglePlay: () => set((s) => ({ isPlaying: !s.isPlaying })),
  setGhostData: (data) => set({ ghostData: data }),
  setSessionInfo: (info) => set({ sessionInfo: info }),
  setTyreData: (data) => set({ tyreData: data }),
  setSelectedTyreDrivers: (drivers) => set({ selectedTyreDrivers: drivers }),
  setLoading: (v) => set({ loading: v }),
  setError: (msg) => set({ error: msg }),
}));