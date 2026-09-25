import { useSyncExternalStore } from 'react';
import type {
  Machine,
  MaintenanceSession,
  ConfigurationChange,
  AuditLogEntry,
  PLCIntegrityResult,
  DashboardStats,
  Notification,
  RiskLevel,
  ChangeCategory,
  ChangeClassification
} from './types';
import { insertSupabaseMachine, fetchSupabaseMachines } from './supabase';

// ─── Initial Baseline Data (No random noise — matching simulator baseline) ───

const GENESIS_HASH = '0'.repeat(64);

export const BASELINE_MACHINES: Machine[] = [
  {
    id: 'm-001',
    machine_code: 'CNC-01',
    name: '5-Axis High-Precision Milling Centre',
    location: 'Shop Floor - Bay 3',
    sector: 'Aerospace & Precision Tooling',
    machine_type: '5_AXIS_CNC',
    status: 'OPERATIONAL',
    plc_version: 'v17',
    motor_speed_rpm: 3000,
    temperature_limit_c: 80,
    pressure_limit_bar: 6.2,
    ip_address: '192.168.10.20',
    firmware_version: 'FW-4.9.2',
    last_maintenance: '2026-09-24T10:00:00Z',
    created_at: '2026-01-15T08:00:00Z'
  },
  {
    id: 'm-002',
    machine_code: 'CNC-02',
    name: 'High-Speed Vertical Milling Centre',
    location: 'Shop Floor - Bay 4',
    sector: 'Automotive Components',
    machine_type: 'VERTICAL_MILL',
    status: 'OPERATIONAL',
    plc_version: 'v16',
    motor_speed_rpm: 2800,
    temperature_limit_c: 75,
    pressure_limit_bar: 5.8,
    ip_address: '192.168.10.21',
    firmware_version: 'FW-4.8.1',
    last_maintenance: '2026-09-20T14:30:00Z',
    created_at: '2026-02-10T08:00:00Z'
  },
  {
    id: 'm-003',
    machine_code: 'ROBOT-01',
    name: '6-Axis Articulated Welding Arm',
    location: 'Cell B - Assembly Line',
    sector: 'Heavy Robotics & Joining',
    machine_type: 'WELDING_ROBOT',
    status: 'OPERATIONAL',
    plc_version: 'v18',
    motor_speed_rpm: 1500,
    temperature_limit_c: 85,
    pressure_limit_bar: 7.0,
    ip_address: '192.168.20.15',
    firmware_version: 'FW-5.1.0',
    last_maintenance: '2026-09-21T09:15:00Z',
    created_at: '2026-03-01T08:00:00Z'
  },
  {
    id: 'm-004',
    machine_code: 'CONV-01',
    name: 'Heavy-Duty Automated Pallet Conveyor',
    location: 'Logistics Tunnel Alpha',
    sector: 'Material Handling',
    machine_type: 'CONVEYOR',
    status: 'OPERATIONAL',
    plc_version: 'v17',
    motor_speed_rpm: 950,
    temperature_limit_c: 65,
    pressure_limit_bar: 4.5,
    ip_address: '192.168.20.16',
    firmware_version: 'FW-4.6.0',
    last_maintenance: '2026-09-18T16:00:00Z',
    created_at: '2026-01-20T08:00:00Z'
  }
];

export const BASELINE_PLC_RESULTS: PLCIntegrityResult[] = [
  {
    machine_code: 'CNC-01',
    baseline_version: 'v17',
    current_version: 'v17',
    baseline_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    current_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    hash_match: true,
    integrity_status: 'VERIFIED',
    integrity_message: 'All ladder rungs and safety interlocks match certified baseline.',
    safety_violations: [],
    total_changes: 0,
    analysed_at: new Date().toISOString()
  },
  {
    machine_code: 'CNC-02',
    baseline_version: 'v16',
    current_version: 'v16',
    baseline_hash: '7d5a99f603f231d53947d8340350815922384f769f24511129f1877ff6ad5066',
    current_hash: '7d5a99f603f231d53947d8340350815922384f769f24511129f1877ff6ad5066',
    hash_match: true,
    integrity_status: 'VERIFIED',
    integrity_message: 'Baseline hash intact. Zero safety violations.',
    safety_violations: [],
    total_changes: 0,
    analysed_at: new Date().toISOString()
  },
  {
    machine_code: 'ROBOT-01',
    baseline_version: 'v18',
    current_version: 'v18',
    baseline_hash: '3a427f30137a0c9b66d6227282b53a39f532683000feedc42f06d1dd32f4da1b',
    current_hash: '3a427f30137a0c9b66d6227282b53a39f532683000feedc42f06d1dd32f4da1b',
    hash_match: true,
    integrity_status: 'VERIFIED',
    integrity_message: 'Motion limits and e-stop chain certified.',
    safety_violations: [],
    total_changes: 0,
    analysed_at: new Date().toISOString()
  }
];

export const INITIAL_AUDIT_LOG: AuditLogEntry[] = [
  {
    id: 'block-genesis',
    event_type: 'GENESIS_BLOCK',
    user_id: 'SYSTEM',
    machine_id: 'CNC-01',
    session_id: 'SYSTEM_BOOT',
    event_data: { note: 'MaintX Immutable Ledger Initialized with SHA-256 Chaining' },
    previous_hash: GENESIS_HASH,
    current_hash: '6a09e667f3bcc908a8a0429f55e094f31c2104523d4e785b88f9189196b66e34',
    created_at: '2026-09-24T00:00:00Z'
  }
];

// ─── Simulation State Type ────────────────────────────────────────────────────

export interface SimulationState {
  machines: Machine[];
  sessions: MaintenanceSession[];
  changes: ConfigurationChange[];
  auditLog: AuditLogEntry[];
  plcResults: PLCIntegrityResult[];
  notifications: Notification[];
  stats: DashboardStats;
  activeSimSession: {
    active: boolean;
    job: string;
    machine: string;
    engineer: string;
    riskScore: number | null;
    integrityValid: boolean | null;
    changes: number;
    unauthorized: number;
    lastEventTs: string | null;
  };
  isChainTampered: boolean;
  tamperedEntrySeq: number | null;
}

// ─── State Calculation Helpers ────────────────────────────────────────────────

function computeStats(
  machines: Machine[],
  sessions: MaintenanceSession[],
  changes: ConfigurationChange[],
  plcResults: PLCIntegrityResult[],
  auditLog: AuditLogEntry[],
  isChainTampered: boolean
): DashboardStats {
  const activeSessions = sessions.filter(s => s.session_status === 'IN_PROGRESS').length;
  const inMaintenance = machines.filter(m => m.status === 'MAINTENANCE').length;
  const operational = machines.filter(m => m.status === 'OPERATIONAL').length;

  const criticalChanges = changes.filter(c => c.risk_level === 'CRITICAL').length;
  const highRiskChanges = changes.filter(c => c.risk_level === 'HIGH').length;
  const unauthorizedChanges = changes.filter(c => !c.is_authorized).length;

  const plcViolations = plcResults.filter(p => p.integrity_status !== 'VERIFIED').length;
  const verifiedMachines = plcResults.filter(p => p.integrity_status === 'VERIFIED').length;

  return {
    total_machines: machines.length,
    operational_machines: operational,
    machines_in_maintenance: inMaintenance,
    active_sessions: activeSessions,
    changes_today: changes.length,
    high_risk_changes: highRiskChanges,
    critical_changes: criticalChanges,
    unresolved_changes: unauthorizedChanges,
    plc_violations: plcViolations,
    verified_machines: verifiedMachines,
    audit_log_integrity: isChainTampered ? 'COMPROMISED' : 'INTACT',
    chain_length: auditLog.length,
  };
}

function getInitialState(): SimulationState {
  const machines = JSON.parse(JSON.stringify(BASELINE_MACHINES));
  const sessions: MaintenanceSession[] = [];
  const changes: ConfigurationChange[] = [];
  const plcResults = JSON.parse(JSON.stringify(BASELINE_PLC_RESULTS));
  const auditLog = JSON.parse(JSON.stringify(INITIAL_AUDIT_LOG));
  const notifications: Notification[] = [
    {
      id: 'notif-init',
      type: 'INFO',
      title: 'MaintX SOC Ready for Simulation',
      message: 'Zero-Trust Maintenance Gate online. Open simulator in separate tab to begin live simulation.',
      machine_code: 'CNC-01',
      timestamp: new Date().toISOString(),
      read: false
    }
  ];

  const stats = computeStats(machines, sessions, changes, plcResults, auditLog, false);

  return {
    machines,
    sessions,
    changes,
    auditLog,
    plcResults,
    notifications,
    stats,
    activeSimSession: {
      active: false,
      job: 'MNT-2031',
      machine: 'CNC-01',
      engineer: 'Rahul Sharma',
      riskScore: null,
      integrityValid: null,
      changes: 0,
      unauthorized: 0,
      lastEventTs: null,
    },
    isChainTampered: false,
    tamperedEntrySeq: null,
  };
}

// ─── Store Instance ───────────────────────────────────────────────────────────

const STORAGE_KEY = 'maintx_simulation_state';
const BROADCAST_BUS = 'maintx_sim_bus';

let currentState: SimulationState = loadFromStorage();
const subscribers = new Set<() => void>();

function notify() {
  saveToStorage(currentState);
  subscribers.forEach(cb => cb());
}

function loadFromStorage(): SimulationState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      // Validate structure
      if (parsed.machines && parsed.stats) {
        return parsed;
      }
    }
  } catch {
    // ignore
  }
  return getInitialState();
}

function saveToStorage(state: SimulationState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore
  }
}

// ─── Cross-Tab Sync via BroadcastChannel & Storage Event ─────────────────────

let broadcastChannel: BroadcastChannel | null = null;
if (typeof window !== 'undefined' && 'BroadcastChannel' in window) {
  try {
    broadcastChannel = new BroadcastChannel(BROADCAST_BUS);
    broadcastChannel.onmessage = (e) => {
      if (e.data?.source === 'maintx-simulator') {
        handleSimulatorEvent(e.data.type, e.data.payload, e.data.state);
      }
    };
  } catch {
    // BroadcastChannel unsupported or blocked
  }
}

if (typeof window !== 'undefined') {
  // Listen for storage events from other tabs
  window.addEventListener('storage', (e) => {
    if (e.key === 'maintx_sim_event' && e.newValue) {
      try {
        const data = JSON.parse(e.newValue);
        if (data?.source === 'maintx-simulator') {
          handleSimulatorEvent(data.type, data.payload, data.state);
        }
      } catch {
        // ignore
      }
    }
  });

  // Listen for postMessage from iframes
  window.addEventListener('message', (e) => {
    if (e.data?.source === 'maintx-simulator') {
      handleSimulatorEvent(e.data.type, e.data.payload, e.data.state);
    }
  });
}

// ─── Simulator Event Handler (The Core Bridge!) ──────────────────────────────

export function handleSimulatorEvent(
  type: string,
  payload: Record<string, unknown>,
  _simState?: Record<string, unknown>
) {
  const ts = (payload.ts as string) || new Date().toISOString();
  const machineCode = (payload.machine as string) || 'CNC-01';
  const job = (payload.job as string) || 'MNT-2031';
  const engineer = (payload.engineer as string) || 'Rahul Sharma';

  // Copy state for mutation
  const nextMachines = [...currentState.machines];
  const nextSessions = [...currentState.sessions];
  const nextChanges = [...currentState.changes];
  const nextAuditLog = [...currentState.auditLog];
  const nextPlcResults = [...currentState.plcResults];
  const nextNotifications = [...currentState.notifications];
  const nextActive = { ...currentState.activeSimSession };
  let isChainTampered = currentState.isChainTampered;
  let tamperedEntrySeq = currentState.tamperedEntrySeq;

  // Find CNC-01 machine index
  const mIndex = nextMachines.findIndex(m => m.machine_code === machineCode);

  // 1. Session Started
  if (type === 'session_start') {
    nextActive.active = true;
    nextActive.job = job;
    nextActive.machine = machineCode;
    nextActive.engineer = engineer;
    nextActive.riskScore = 0;
    nextActive.integrityValid = null;
    nextActive.changes = 0;
    nextActive.unauthorized = 0;
    nextActive.lastEventTs = ts;
    isChainTampered = false;
    tamperedEntrySeq = null;

    // Update machine status to MAINTENANCE
    if (mIndex !== -1) {
      nextMachines[mIndex] = {
        ...nextMachines[mIndex],
        status: 'MAINTENANCE',
        last_maintenance: ts,
      };
    }

    // Add or update active session
    const existingSessionIdx = nextSessions.findIndex(s => s.session_code === job);
    const newSession: MaintenanceSession = {
      id: `sess-${job}`,
      session_code: job,
      machine_id: nextMachines[mIndex]?.id || 'm-001',
      machine_code: machineCode,
      machine_name: nextMachines[mIndex]?.name || '5-Axis High-Precision Milling Centre',
      engineer_id: 'eng-sim',
      engineer_name: engineer,
      session_status: 'IN_PROGRESS',
      verification_status: 'PENDING',
      started_at: ts,
      completed_at: null,
      created_at: ts,
      risk_level: 'LOW',
      notes: 'Active Work Order: Spindle Motor Optimization & PLC Verification',
    };

    if (existingSessionIdx !== -1) {
      nextSessions[existingSessionIdx] = newSession;
    } else {
      nextSessions.unshift(newSession);
    }

    // Audit log
    const prevBlock = nextAuditLog[nextAuditLog.length - 1];
    nextAuditLog.push({
      id: `block-${Date.now()}`,
      event_type: 'MAINTENANCE_SESSION_STARTED',
      user_id: engineer,
      machine_id: machineCode,
      session_id: job,
      event_data: { job, machine: machineCode, engineer, timestamp: ts },
      previous_hash: prevBlock ? prevBlock.current_hash : GENESIS_HASH,
      current_hash: (payload.hash as string) || pseudoHash(`${job}-start-${ts}`),
      created_at: ts,
    });

    // Notification
    nextNotifications.unshift({
      id: `notif-${Date.now()}`,
      type: 'INFO',
      title: `Maintenance Session ${job} Started`,
      message: `${engineer} opened maintenance mode on machine ${machineCode}. Zero-Trust Gateway monitoring live parameters.`,
      machine_code: machineCode,
      timestamp: ts,
      read: false,
    });
  }

  // 2. Control Change
  else if (type === 'change') {
    nextActive.changes += 1;
    nextActive.lastEventTs = ts;

    const controlId = payload.control as string;
    const newVal = payload.value;
    const status = payload.status as string; // 'authorized' | 'unauthorized' | 'reverted'
    const severity = payload.severity as string; // 'good' | 'warning' | 'critical' | 'info'
    const message = (payload.message as string) || '';

    const isAuthorized = status === 'authorized' || status === 'reverted';
    if (!isAuthorized) {
      nextActive.unauthorized += 1;
    }

    let category: ChangeCategory = 'PARAMETERS';
    let paramName = controlId;
    let oldVal = '';
    let riskLevel: RiskLevel = 'LOW';
    let riskScore = 10;
    let classification: ChangeClassification = isAuthorized ? 'EXPECTED' : 'UNAUTHORIZED';

    // Map control specifics
    if (controlId === 'motorSpeed') {
      category = 'PARAMETERS';
      paramName = 'Spindle Motor Speed (RPM)';
      oldVal = `${nextMachines[mIndex]?.motor_speed_rpm || 3000} RPM`;
      if (mIndex !== -1) {
        nextMachines[mIndex] = {
          ...nextMachines[mIndex],
          motor_speed_rpm: Number(newVal) || 3200,
        };
      }
      riskLevel = 'LOW';
      riskScore = 15;
    } else if (controlId === 'plcVersion') {
      category = 'FIRMWARE';
      paramName = 'PLC Firmware Logic Version';
      oldVal = nextMachines[mIndex]?.plc_version || 'v17';
      if (mIndex !== -1) {
        nextMachines[mIndex] = {
          ...nextMachines[mIndex],
          plc_version: String(newVal),
        };
      }
      riskLevel = 'LOW';
      riskScore = 20;

      // Update PLC integrity results current version
      const plcIdx = nextPlcResults.findIndex(p => p.machine_code === machineCode);
      if (plcIdx !== -1) {
        nextPlcResults[plcIdx] = {
          ...nextPlcResults[plcIdx],
          current_version: String(newVal),
          total_changes: nextPlcResults[plcIdx].total_changes + 1,
          analysed_at: ts,
        };
      }
    } else if (controlId === 'tempLimit') {
      category = 'PARAMETERS';
      paramName = 'Operating Temperature Limit';
      oldVal = `${nextMachines[mIndex]?.temperature_limit_c || 80}°C`;
      if (mIndex !== -1) {
        nextMachines[mIndex] = {
          ...nextMachines[mIndex],
          temperature_limit_c: Number(newVal),
        };
      }
      riskLevel = severity === 'critical' ? 'CRITICAL' : 'MEDIUM';
      riskScore = severity === 'critical' ? 85 : 45;
    } else if (controlId === 'ipAddress') {
      category = 'NETWORK';
      paramName = 'Industrial Ethernet IP Address';
      oldVal = nextMachines[mIndex]?.ip_address || '192.168.10.20';
      if (mIndex !== -1) {
        nextMachines[mIndex] = {
          ...nextMachines[mIndex],
          ip_address: String(newVal),
        };
      }
      riskLevel = isAuthorized ? 'LOW' : 'HIGH';
      riskScore = isAuthorized ? 15 : 65;
    } else if (controlId === 'safetyInterlock') {
      category = 'SAFETY_CONFIG';
      paramName = 'Hardware Safety Interlock Circuit (N7)';
      oldVal = newVal === 'ON' ? 'OFF' : 'ON';

      if (newVal === 'OFF') {
        riskLevel = 'CRITICAL';
        riskScore = 95;
        classification = 'UNAUTHORIZED';
        if (mIndex !== -1) {
          nextMachines[mIndex] = {
            ...nextMachines[mIndex],
            status: 'CRITICAL',
          };
        }

        // Flag PLC integrity violation
        const plcIdx = nextPlcResults.findIndex(p => p.machine_code === machineCode);
        if (plcIdx !== -1) {
          nextPlcResults[plcIdx] = {
            ...nextPlcResults[plcIdx],
            hash_match: false,
            current_hash: 'c8f74a9193bde10874e0d9982421312384918231293812938192381293812938',
            integrity_status: 'SAFETY_INTERLOCK_COMPROMISED',
            integrity_message: 'CRITICAL: Hardware safety interlock circuit N7 bypassed without LOTO bypass authorization token!',
            safety_violations: [
              'Hardware safety interlock circuit N7 bypassed',
              'Unapproved e-stop ladder logic state override',
            ],
            total_changes: nextPlcResults[plcIdx].total_changes + 1,
            analysed_at: ts,
          };
        }

        // Critical Notification
        nextNotifications.unshift({
          id: `notif-crit-${Date.now()}`,
          type: 'CRITICAL',
          title: `🚨 CRITICAL VIOLATION: Safety Interlock Disabled — ${machineCode}`,
          message: `Safety Interlock (N7) changed to OFF by ${engineer} — NOT in the approved plan! Machine safety compromised.`,
          machine_code: machineCode,
          timestamp: ts,
          read: false,
        });
      } else {
        // Restored to ON
        riskLevel = 'LOW';
        riskScore = 10;
        classification = 'EXPECTED';
        if (mIndex !== -1 && nextActive.active) {
          nextMachines[mIndex] = {
            ...nextMachines[mIndex],
            status: 'MAINTENANCE',
          };
        }

        // Restore PLC integrity
        const plcIdx = nextPlcResults.findIndex(p => p.machine_code === machineCode);
        if (plcIdx !== -1) {
          nextPlcResults[plcIdx] = {
            ...nextPlcResults[plcIdx],
            hash_match: true,
            current_hash: nextPlcResults[plcIdx].baseline_hash,
            integrity_status: 'VERIFIED',
            integrity_message: 'Safety interlock N7 restored to certified baseline.',
            safety_violations: [],
            total_changes: nextPlcResults[plcIdx].total_changes + 1,
            analysed_at: ts,
          };
        }
      }
    }

    // Add to Configuration Changes
    const changeEntry: ConfigurationChange = {
      id: `chg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      machine_id: nextMachines[mIndex]?.id || 'm-001',
      machine_code: machineCode,
      session_id: job,
      user_id: engineer,
      user_name: engineer,
      user_role: 'MAINTENANCE_ENGINEER',
      category,
      parameter_name: paramName,
      old_value: oldVal || 'Baseline',
      new_value: `${newVal}`,
      risk_level: riskLevel,
      risk_score: riskScore,
      is_expected: isAuthorized,
      is_authorized: isAuthorized,
      classification,
      timestamp: ts,
      reason: message,
    };
    nextChanges.unshift(changeEntry);

    // Update active session risk
    const sessIdx = nextSessions.findIndex(s => s.session_code === job);
    if (sessIdx !== -1) {
      if (riskLevel === 'CRITICAL') {
        nextSessions[sessIdx].risk_level = 'CRITICAL';
      } else if (riskLevel === 'HIGH' && nextSessions[sessIdx].risk_level !== 'CRITICAL') {
        nextSessions[sessIdx].risk_level = 'HIGH';
      }
    }

    // Audit Log Entry with Hash Chaining
    const prevBlock = nextAuditLog[nextAuditLog.length - 1];
    nextAuditLog.push({
      id: `block-${Date.now()}`,
      event_type: riskLevel === 'CRITICAL' ? 'CRITICAL_RISK_FLAGGED' : 'CONFIGURATION_CHANGE_DETECTED',
      user_id: engineer,
      machine_id: machineCode,
      session_id: job,
      event_data: { control: controlId, value: newVal, status, message, riskScore },
      previous_hash: prevBlock ? prevBlock.current_hash : GENESIS_HASH,
      current_hash: (payload.hash as string) || pseudoHash(`${prevBlock?.current_hash || ''}-${controlId}-${newVal}-${ts}`),
      created_at: ts,
    });

    // Unauthorized Notification
    if (!isAuthorized && controlId !== 'safetyInterlock') {
      nextNotifications.unshift({
        id: `notif-warn-${Date.now()}`,
        type: 'WARNING',
        title: `Unauthorized Change: ${paramName} — ${machineCode}`,
        message: `${message} Sent to supervisor review queue.`,
        machine_code: machineCode,
        timestamp: ts,
        read: false,
      });
    }
  }

  // 3. Session End & Verification
  else if (type === 'session_end') {
    nextActive.active = false;
    nextActive.riskScore = (payload.riskScore as number) ?? nextActive.riskScore;
    nextActive.lastEventTs = ts;

    // Restore machine status to OPERATIONAL
    if (mIndex !== -1) {
      nextMachines[mIndex] = {
        ...nextMachines[mIndex],
        status: 'OPERATIONAL',
      };
    }

    // Complete session
    const sessIdx = nextSessions.findIndex(s => s.session_code === job);
    if (sessIdx !== -1) {
      nextSessions[sessIdx] = {
        ...nextSessions[sessIdx],
        session_status: 'COMPLETED',
        verification_status: isChainTampered ? 'FAILED' : 'VERIFIED',
        completed_at: ts,
      };
    }

    // Audit log
    const prevBlock = nextAuditLog[nextAuditLog.length - 1];
    nextAuditLog.push({
      id: `block-${Date.now()}`,
      event_type: 'MAINTENANCE_SESSION_COMPLETED',
      user_id: engineer,
      machine_id: machineCode,
      session_id: job,
      event_data: { job, finalRiskScore: nextActive.riskScore, closedAt: ts },
      previous_hash: prevBlock ? prevBlock.current_hash : GENESIS_HASH,
      current_hash: (payload.hash as string) || pseudoHash(`${job}-end-${ts}`),
      created_at: ts,
    });

    // Notification
    nextNotifications.unshift({
      id: `notif-end-${Date.now()}`,
      type: 'SUCCESS',
      title: `Maintenance Session ${job} Closed & Verified`,
      message: `Zero-Trust verification completed on ${machineCode}. Final risk score: ${nextActive.riskScore ?? 0}. Ledger sealed.`,
      machine_code: machineCode,
      timestamp: ts,
      read: false,
    });
  }

  // 4. Log Integrity Check
  else if (type === 'log_integrity') {
    const valid = payload.valid as boolean;
    nextActive.integrityValid = valid;
    isChainTampered = !valid;

    if (!valid) {
      tamperedEntrySeq = (payload.brokenAt as number) || 1;
      nextNotifications.unshift({
        id: `notif-tamper-${Date.now()}`,
        type: 'CRITICAL',
        title: `🚨 LEDGER COMPROMISED: Hash Chain Broken at Block #${tamperedEntrySeq}`,
        message: 'Cryptographic hash chain verification failed. Unauthorized alteration detected in immutable audit log!',
        timestamp: ts,
        read: false,
      });
    } else {
      tamperedEntrySeq = null;
    }
  }

  // Compute fresh stats
  const stats = computeStats(
    nextMachines,
    nextSessions,
    nextChanges,
    nextPlcResults,
    nextAuditLog,
    isChainTampered
  );

  // Update store
  currentState = {
    machines: nextMachines,
    sessions: nextSessions,
    changes: nextChanges,
    auditLog: nextAuditLog,
    plcResults: nextPlcResults,
    notifications: nextNotifications.slice(0, 50),
    stats,
    activeSimSession: nextActive,
    isChainTampered,
    tamperedEntrySeq,
  };

  notify();
}

// ─── Reset Simulation Back to Clean Baseline ──────────────────────────────────

export function resetSimulation() {
  currentState = getInitialState();
  try {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem('maintx_sim_event');
  } catch {
    // ignore
  }
  notify();
}

// ─── Notification Actions ─────────────────────────────────────────────────────

export function markNotificationAsRead(id: string) {
  currentState = {
    ...currentState,
    notifications: currentState.notifications.map(n =>
      n.id === id ? { ...n, read: true } : n
    ),
  };
  notify();
}

export function markAllNotificationsAsRead() {
  currentState = {
    ...currentState,
    notifications: currentState.notifications.map(n => ({ ...n, read: true })),
  };
  notify();
}

export function clearAllNotifications() {
  currentState = {
    ...currentState,
    notifications: [],
  };
  notify();
}

export function pushNotification(notification: Notification) {
  currentState = {
    ...currentState,
    notifications: [notification, ...currentState.notifications],
  };
  notify();
}

// ─── Add Machine ──────────────────────────────────────────────────────────────

export async function addMachine(machine: Machine): Promise<{ success: boolean; dbSynced: boolean; error?: string }> {
  // 1. Optimistic immediate update to local state
  const stats = computeStats(
    [...currentState.machines, machine],
    currentState.sessions,
    currentState.changes,
    currentState.plcResults,
    currentState.auditLog,
    currentState.isChainTampered
  );
  currentState = {
    ...currentState,
    machines: [...currentState.machines, machine],
    stats,
    notifications: [
      {
        id: `notif-machine-${Date.now()}`,
        type: 'SUCCESS',
        title: `Machine Registered: ${machine.machine_code}`,
        message: `${machine.name} has been added to the Machine Registry.`,
        machine_code: machine.machine_code,
        timestamp: new Date().toISOString(),
        read: false,
      },
      ...currentState.notifications,
    ],
  };
  notify();

  // 2. Persist directly to Supabase database
  try {
    const res = await insertSupabaseMachine(machine);
    if (res.success && res.id) {
      // Update with persistent Supabase UUID
      currentState = {
        ...currentState,
        machines: currentState.machines.map(m =>
          m.machine_code === machine.machine_code ? { ...m, id: res.id! } : m
        ),
      };
      notify();
      return { success: true, dbSynced: true };
    } else {
      return { success: true, dbSynced: false, error: res.error };
    }
  } catch (err: any) {
    console.warn('[Store] Supabase machine sync warning:', err);
    return { success: true, dbSynced: false, error: err?.message };
  }
}

// Background sync from Supabase database on startup — DB is source of truth
if (typeof window !== 'undefined') {
  fetchSupabaseMachines().then(dbMachines => {
    if (dbMachines && dbMachines.length > 0) {
      // DB is the authoritative source: replace local baseline entirely.
      // Any locally-added machines (not yet persisted) are kept if they have
      // a temporary id prefix or don't exist in DB by machine_code.
      const dbCodes = new Set(dbMachines.map(m => m.machine_code.toUpperCase()));
      const localOnlyMachines = currentState.machines.filter(
        m => !dbCodes.has(m.machine_code.toUpperCase())
      );
      const mergedMachines = [...dbMachines, ...localOnlyMachines];
      const stats = computeStats(
        mergedMachines,
        currentState.sessions,
        currentState.changes,
        currentState.plcResults,
        currentState.auditLog,
        currentState.isChainTampered
      );
      currentState = {
        ...currentState,
        machines: mergedMachines,
        stats,
      };
      notify();
      console.info(`[Store] Loaded ${dbMachines.length} machines from Supabase (DB is source of truth).`);
    }
  }).catch(err => {
    console.warn('[Store] Background Supabase machines fetch warning:', err);
  });
}


// ─── React Hook: useSimulation() ──────────────────────────────────────────────

export function useSimulation(): SimulationState & {
  resetSimulation: () => void;
  markNotificationAsRead: (id: string) => void;
  markAllNotificationsAsRead: () => void;
  clearAllNotifications: () => void;
  pushNotification: (notification: Notification) => void;
  addMachine: (machine: Machine) => Promise<{ success: boolean; dbSynced: boolean; error?: string }>;
  riskTrendData: { date: string; critical: number; high: number; medium: number; low: number }[];
  categoryDistribution: { name: string; value: number; color: string }[];
  machineRiskData: { machine: string; score: number }[];
  verificationHistory: { month: string; verified: number; review: number; failed: number }[];
} {
  const state = useSyncExternalStore(
    (callback) => {
      subscribers.add(callback);
      return () => {
        subscribers.delete(callback);
      };
    },
    () => currentState,
    () => currentState
  );

  // Derive dynamic chart data
  const criticalCount = state.changes.filter(c => c.risk_level === 'CRITICAL').length;
  const highCount = state.changes.filter(c => c.risk_level === 'HIGH').length;
  const mediumCount = state.changes.filter(c => c.risk_level === 'MEDIUM').length;
  const lowCount = state.changes.filter(c => c.risk_level === 'LOW').length;

  const riskTrendData = [
    { date: 'Day -6', critical: 0, high: 0, medium: 1, low: 2 },
    { date: 'Day -5', critical: 0, high: 1, medium: 0, low: 3 },
    { date: 'Day -4', critical: 0, high: 0, medium: 2, low: 1 },
    { date: 'Day -3', critical: 0, high: 0, medium: 1, low: 4 },
    { date: 'Day -2', critical: 0, high: 1, medium: 1, low: 2 },
    { date: 'Yesterday', critical: 0, high: 0, medium: 2, low: 3 },
    {
      date: 'Today (Live)',
      critical: criticalCount,
      high: highCount,
      medium: mediumCount,
      low: Math.max(1, lowCount),
    },
  ];

  const paramCount = state.changes.filter(c => c.category === 'PARAMETERS').length;
  const fwCount = state.changes.filter(c => c.category === 'FIRMWARE').length;
  const netCount = state.changes.filter(c => c.category === 'NETWORK').length;
  const safetyCount = state.changes.filter(c => c.category === 'SAFETY_CONFIG').length;

  const categoryDistribution = [
    { name: 'Parameters', value: Math.max(1, paramCount), color: '#06b6d4' },
    { name: 'Firmware', value: Math.max(1, fwCount), color: '#f59e0b' },
    { name: 'Network', value: Math.max(1, netCount), color: '#a855f7' },
    { name: 'Safety Logic', value: Math.max(1, safetyCount), color: '#f43f5e' },
  ];

  const machineRiskData = state.machines.map(m => ({
    machine: m.machine_code,
    score: m.status === 'CRITICAL' ? 95 : m.status === 'MAINTENANCE' ? (state.activeSimSession.riskScore ?? 45) : 10,
  }));

  const verificationHistory = [
    { month: 'Jun', verified: 12, review: 1, failed: 0 },
    { month: 'Jul', verified: 15, review: 2, failed: 0 },
    { month: 'Aug', verified: 18, review: 1, failed: 0 },
    { month: 'Sep (Live)', verified: state.stats.verified_machines, review: state.stats.unresolved_changes, failed: state.stats.plc_violations },
  ];

  return {
    ...state,
    resetSimulation,
    markNotificationAsRead,
    markAllNotificationsAsRead,
    clearAllNotifications,
    pushNotification,
    addMachine,
    riskTrendData,
    categoryDistribution,
    machineRiskData,
    verificationHistory,
  };
}

// ─── Pseudo SHA-256 for Synchronous Event Chaining Fallback ───────────────────

function pseudoHash(str: string): string {
  let h1 = 0xdeadbeef;
  let h2 = 0x41c64e6d;
  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
  h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
  h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  const p1 = (h1 >>> 0).toString(16).padStart(8, '0');
  const p2 = (h2 >>> 0).toString(16).padStart(8, '0');
  const p3 = ((h1 ^ h2) >>> 0).toString(16).padStart(8, '0');
  const p4 = ((h1 + h2) >>> 0).toString(16).padStart(8, '0');
  return (p1 + p2 + p3 + p4 + p2 + p1 + p4 + p3).slice(0, 64);
}
