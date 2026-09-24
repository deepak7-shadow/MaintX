// ─── Mock & Baseline Data Layer ──────────────────────────────────────────────
// Re-exports live baseline data and types from simulationStore.
// All pages use the reactive `useSimulation()` hook to receive instant cross-tab
// updates from the standalone simulator tab.

export {
  useSimulation,
  resetSimulation,
  handleSimulatorEvent,
  BASELINE_MACHINES as MACHINES,
  BASELINE_PLC_RESULTS as PLC_RESULTS,
  INITIAL_AUDIT_LOG as AUDIT_LOG
} from './simulationStore';

export const SESSIONS = [];
export const CHANGES = [];
export const NOTIFICATIONS = [];

export const DASHBOARD_STATS = {
  total_machines: 4,
  operational_machines: 4,
  machines_in_maintenance: 0,
  active_sessions: 0,
  changes_today: 0,
  high_risk_changes: 0,
  critical_changes: 0,
  unresolved_changes: 0,
  plc_violations: 0,
  verified_machines: 3,
  audit_log_integrity: 'INTACT' as const,
  chain_length: 1,
};

export const RISK_TREND_DATA = [
  { date: 'Day -6', critical: 0, high: 0, medium: 1, low: 2 },
  { date: 'Day -5', critical: 0, high: 1, medium: 0, low: 3 },
  { date: 'Day -4', critical: 0, high: 0, medium: 2, low: 1 },
  { date: 'Day -3', critical: 0, high: 0, medium: 1, low: 4 },
  { date: 'Day -2', critical: 0, high: 1, medium: 1, low: 2 },
  { date: 'Yesterday', critical: 0, high: 0, medium: 2, low: 3 },
  { date: 'Today (Live)', critical: 0, high: 0, medium: 0, low: 1 },
];

export const CATEGORY_DISTRIBUTION = [
  { name: 'Parameters', value: 1, color: '#06b6d4' },
  { name: 'Firmware', value: 1, color: '#f59e0b' },
  { name: 'Network', value: 1, color: '#a855f7' },
  { name: 'Safety Logic', value: 1, color: '#f43f5e' },
];

export const MACHINE_RISK_DATA = [
  { machine: 'CNC-01', score: 10 },
  { machine: 'CNC-02', score: 10 },
  { machine: 'ROBOT-01', score: 10 },
  { machine: 'CONV-01', score: 10 },
];

export const VERIFICATION_HISTORY = [
  { month: 'Jun', verified: 12, review: 1, failed: 0 },
  { month: 'Jul', verified: 15, review: 2, failed: 0 },
  { month: 'Aug', verified: 18, review: 1, failed: 0 },
  { month: 'Sep (Live)', verified: 3, review: 0, failed: 0 },
];
