// ─── Core Domain Types ────────────────────────────────────────────────────────

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type SessionStatus = 'PENDING' | 'ASSIGNED' | 'SUPERVISOR_APPROVED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';
export type VerificationStatus = 'PENDING' | 'VERIFIED' | 'REVIEW_REQUIRED' | 'FAILED';
export type PLCStatus = 'VERIFIED' | 'HASH_MISMATCH' | 'UNAPPROVED_LOGIC' | 'SAFETY_INTERLOCK_COMPROMISED';
export type ChangeClassification = 'EXPECTED' | 'UNEXPECTED' | 'UNAUTHORIZED' | 'UNRESOLVED';
export type ChangeCategory = 'PARAMETERS' | 'PLC_LOGIC' | 'NETWORK' | 'FIREWALL' | 'FIRMWARE' | 'SAFETY_CONFIG';
export type UserRole = 'ADMIN' | 'SUPERVISOR' | 'MAINTENANCE_ENGINEER' | 'SECURITY_ANALYST' | 'AUDITOR';

export interface Machine {
  id: string;
  machine_code: string;
  name: string;
  location: string;
  sector: string;
  machine_type: string;
  status: 'OPERATIONAL' | 'MAINTENANCE' | 'OFFLINE' | 'CRITICAL';
  plc_version: string;
  motor_speed_rpm: number;
  temperature_limit_c: number;
  pressure_limit_bar: number;
  ip_address: string;
  firmware_version: string;
  last_maintenance: string;
  created_at: string;
}

export interface MaintenanceSession {
  id: string;
  session_code: string;
  machine_id: string;
  machine_code?: string;
  machine_name?: string;
  engineer_id: string;
  engineer_name?: string;
  session_status: SessionStatus;
  verification_status: VerificationStatus;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  notes?: string;
  risk_level?: RiskLevel;
}

export interface ConfigurationChange {
  id: string;
  machine_id: string;
  machine_code?: string;
  session_id?: string;
  user_id: string;
  user_name?: string;
  user_role: UserRole;
  category: ChangeCategory;
  parameter_name: string;
  old_value: string;
  new_value: string;
  risk_level: RiskLevel;
  risk_score: number;
  is_expected: boolean;
  is_authorized: boolean;
  ai_anomaly_score?: number;
  classification?: ChangeClassification;
  timestamp: string;
  reason?: string;
}

export interface AuditLogEntry {
  id: string;
  event_type: string;
  user_id?: string;
  machine_id?: string;
  session_id?: string;
  event_data: Record<string, unknown>;
  previous_hash: string;
  current_hash: string;
  created_at: string;
}

export interface PLCIntegrityResult {
  machine_code: string;
  baseline_version: string;
  current_version: string;
  baseline_hash: string;
  current_hash: string;
  previous_version?: string;
  previous_hash?: string;
  hash_match: boolean;
  integrity_status: PLCStatus;
  integrity_message: string;
  safety_violations: string[];
  total_changes: number;
  analysed_at: string;
}

export interface DashboardStats {
  total_machines: number;
  operational_machines: number;
  machines_in_maintenance: number;
  active_sessions: number;
  changes_today: number;
  high_risk_changes: number;
  critical_changes: number;
  unresolved_changes: number;
  plc_violations: number;
  verified_machines: number;
  audit_log_integrity: 'INTACT' | 'COMPROMISED' | 'UNVERIFIED';
  chain_length: number;
}

export interface Notification {
  id: string;
  type: 'CRITICAL' | 'WARNING' | 'INFO' | 'SUCCESS';
  title: string;
  message: string;
  machine_code?: string;
  timestamp: string;
  read: boolean;
}
