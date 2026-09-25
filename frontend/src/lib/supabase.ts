import { createClient } from '@supabase/supabase-js';
import type { Machine } from './types';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://grdmoxhfwsqkhcsrqvau.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || '';

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
  },
});

// Map between frontend status and database CHECK constraint
function toDbStatus(s: Machine['status']): string {
  switch (s) {
    case 'OPERATIONAL': return 'OPERATIONAL';
    case 'MAINTENANCE': return 'MAINTENANCE_MODE';
    case 'CRITICAL': return 'COMPROMISED';
    case 'OFFLINE': return 'IDLE';
    default: return 'OPERATIONAL';
  }
}

function fromDbStatus(s: string): Machine['status'] {
  switch (s) {
    case 'OPERATIONAL': return 'OPERATIONAL';
    case 'MAINTENANCE_MODE': return 'MAINTENANCE';
    case 'COMPROMISED':
    case 'LOCKOUT_TAGOUT': return 'CRITICAL';
    case 'IDLE':
    case 'DECOMMISSIONED': return 'OFFLINE';
    default: return 'OPERATIONAL';
  }
}

// Derive a safe gateway IP from machine IP (e.g. 192.168.10.50 -> 192.168.10.1)
function deriveGateway(ip: string): string {
  const parts = ip.trim().split('.');
  if (parts.length === 4) {
    return `${parts[0]}.${parts[1]}.${parts[2]}.1`;
  }
  return '192.168.10.1';
}

/**
 * Ensures an active Supabase authentication session so writes succeed under RLS.
 */
export async function ensureAuthSession(email = 'admin@maintx.internal', password = 'MaintX@2026!Admin'): Promise<boolean> {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session) return true;

    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      console.warn('[Supabase] Auth login warning:', error.message);
      return false;
    }
    return !!data.session;
  } catch (err) {
    console.warn('[Supabase] Auth exception:', err);
    return false;
  }
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Inserts a new machine via the FastAPI backend (POST /api/machines).
 * The backend uses the service-role key so it bypasses RLS reliably.
 */
export async function insertSupabaseMachine(machine: Machine): Promise<{ success: boolean; error?: string; id?: string }> {
  try {
    const payload = {
      machine_code: machine.machine_code.toUpperCase(),
      name: machine.name,
      machine_type: machine.machine_type || '5_AXIS_CNC',
      criticality: machine.status === 'CRITICAL' ? 'CRITICAL' : 'HIGH',
      location: machine.location,
      status: toDbStatus(machine.status),
      plc_version: machine.plc_version || 'v17',
      plc_integrity_status: 'VERIFIED',
      firmware: machine.firmware_version || '4.9.0',
      ip_address: machine.ip_address,
      subnet: '255.255.255.0',
      gateway: deriveGateway(machine.ip_address),
      firewall_configuration: { mac_filtering: true, inspection_mode: 'STRICT' },
      safety_configuration: { estop_circuit: 'DUAL_CHANNEL_CAT4' },
      parameters: {
        operating_mode: 'AUTO',
        motor_speed_rpm: machine.motor_speed_rpm,
        temperature_limit_celsius: machine.temperature_limit_c,
        pressure_limit_bar: machine.pressure_limit_bar,
        sector: machine.sector,
      },
    };

    const res = await fetch(`${API_URL}/api/machines`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errText = await res.text();
      console.error('[API] Insert machine error:', res.status, errText);
      return { success: false, error: `HTTP ${res.status}: ${errText}` };
    }

    const data = await res.json();
    console.info('[API] Successfully saved machine to database:', machine.machine_code, data?.id);
    return { success: true, id: data?.id };
  } catch (err: any) {
    console.error('[API] Unexpected error saving machine:', err);
    return { success: false, error: err?.message || 'Network error' };
  }
}

/**
 * Fetches all registered machines from Supabase and transforms them to frontend domain model.
 */
export async function fetchSupabaseMachines(): Promise<Machine[]> {
  try {
    await ensureAuthSession();

    const { data, error } = await supabase
      .from('machines')
      .select('*')
      .neq('status', 'DECOMMISSIONED')
      .order('machine_code');

    if (error || !data) {
      if (error) console.warn('[Supabase] fetch machines warning:', error.message);
      return [];
    }

    return data.map((row: any): Machine => {
      const params = row.parameters || {};
      return {
        id: row.id,
        machine_code: row.machine_code,
        name: row.name,
        location: row.location,
        sector: params.sector || 'Automated Systems',
        machine_type: row.machine_type,
        status: fromDbStatus(row.status),
        plc_version: row.plc_version || 'v17',
        motor_speed_rpm: Number(params.motor_speed_rpm) || 1500,
        temperature_limit_c: Number(params.temperature_limit_celsius) || 80,
        pressure_limit_bar: Number(params.pressure_limit_bar) || 6.0,
        ip_address: String(row.ip_address || ''),
        firmware_version: row.firmware || 'FW-4.9.0',
        last_maintenance: row.updated_at || row.created_at || new Date().toISOString(),
        created_at: row.created_at || new Date().toISOString(),
      };
    });
  } catch (err) {
    console.warn('[Supabase] Failed to fetch machines from database:', err);
    return [];
  }
}
