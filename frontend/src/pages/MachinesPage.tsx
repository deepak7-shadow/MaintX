import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Server, Search, Filter, Cpu, Activity,
  Thermometer, Gauge, Wifi, ChevronRight, Shield, Clock,
  Plus, X, CheckCircle2, AlertTriangle, Database
} from 'lucide-react';
import { useSimulation } from '../lib/simulationStore';
import { Badge, Card, StatusDot, SectionHeader, RiskBar } from '../components/ui';
import type { Machine } from '../lib/types';

// ─── Machine Status Badge ─────────────────────────────────────────────────────

function MachineStatusBadge({ status }: { status: Machine['status'] }) {
  const map = {
    OPERATIONAL: 'bg-emerald-950/70 border-emerald-500/40 text-emerald-300',
    MAINTENANCE: 'bg-cyan-950/70 border-cyan-500/40 text-cyan-300',
    OFFLINE: 'bg-slate-800 border-slate-600 text-slate-400',
    CRITICAL: 'bg-rose-950/70 border-rose-500/50 text-rose-300',
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${map[status]}`}>
      <StatusDot status={status} />
      {status}
    </span>
  );
}

// ─── Machine Card ─────────────────────────────────────────────────────────────

function MachineCard({ m }: { m: Machine }) {
  return (
    <Link to={`/machines/${m.machine_code}`} className="block">
      <Card className="p-4 hover:border-slate-600 transition-all group cursor-pointer">
        <div className="flex items-start justify-between mb-3">
          <div>
            <p className="text-xs font-mono text-slate-400">{m.machine_type.replace(/_/g, ' ')}</p>
            <h3 className="text-sm font-bold text-white group-hover:text-cyan-400 transition mt-0.5">
              {m.machine_code}
            </h3>
          </div>
          <MachineStatusBadge status={m.status} />
        </div>
        <p className="text-xs text-slate-300 mb-3 leading-snug">{m.name}</p>

        <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-slate-400 mb-3">
          <span className="flex items-center gap-1"><Cpu className="w-3 h-3" /> PLC {m.plc_version}</span>
          <span className="flex items-center gap-1"><Wifi className="w-3 h-3" /> {m.ip_address}</span>
          <span className="flex items-center gap-1"><Activity className="w-3 h-3" /> {m.motor_speed_rpm} RPM</span>
          <span className="flex items-center gap-1"><Thermometer className="w-3 h-3" /> {m.temperature_limit_c}°C</span>
        </div>

        <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 pt-2 border-t border-slate-800">
          <span>{m.location}</span>
          <ChevronRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-cyan-500 transition" />
        </div>
      </Card>
    </Link>
  );
}

// ─── Add Machine Modal ────────────────────────────────────────────────────────

const MACHINE_TYPES = [
  '5_AXIS_CNC', 'VERTICAL_MILL', 'WELDING_ROBOT', 'CONVEYOR', 'HYDRAULIC_PRESS',
  'LATHE', 'INJECTION_MOLDING', 'COMPRESSOR', 'PUMP', 'ROBOT_ARM', 'HEAT_EXCHANGER', 'OTHER'
];
const STATUSES: Machine['status'][] = ['OPERATIONAL', 'MAINTENANCE', 'OFFLINE', 'CRITICAL'];

type FormData = {
  machine_code: string; name: string; location: string; sector: string;
  machine_type: string; status: Machine['status']; plc_version: string;
  motor_speed_rpm: string; temperature_limit_c: string; pressure_limit_bar: string;
  ip_address: string; firmware_version: string;
};

const EMPTY_FORM: FormData = {
  machine_code: '', name: '', location: '', sector: '',
  machine_type: '5_AXIS_CNC', status: 'OPERATIONAL', plc_version: 'v17',
  motor_speed_rpm: '1500', temperature_limit_c: '80', pressure_limit_bar: '6.0',
  ip_address: '', firmware_version: 'FW-4.9.0',
};

function Field({ label, required, error, children }: {
  label: string; required?: boolean; error?: string; children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
        {label}{required && <span className="text-rose-400 ml-0.5">*</span>}
      </label>
      {children}
      {error && <p className="text-[10px] text-rose-400 font-mono">{error}</p>}
    </div>
  );
}

const inputCls = 'w-full px-3 py-2 bg-slate-900/80 border border-slate-700/80 rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-600 transition font-mono';
const selectCls = 'w-full px-3 py-2 bg-slate-900/80 border border-slate-700/80 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-cyan-600 transition font-mono';

function AddMachineModal({ open, onClose, onAdd, existingCodes }: {
  open: boolean; onClose: () => void;
  onAdd: (m: Machine) => Promise<{ success: boolean; dbSynced: boolean; error?: string }> | void;
  existingCodes: Set<string>;
}) {
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [errors, setErrors] = useState<Partial<Record<keyof FormData, string>>>({});
  const [syncState, setSyncState] = useState<'idle' | 'syncing' | 'synced' | 'local'>('idle');

  if (!open) return null;

  const set = (k: keyof FormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm(f => ({ ...f, [k]: e.target.value }));
    setErrors(er => ({ ...er, [k]: undefined }));
  };

  const validate = (): boolean => {
    const errs: Partial<Record<keyof FormData, string>> = {};
    if (!form.machine_code.trim()) errs.machine_code = 'Required';
    else if (existingCodes.has(form.machine_code.trim().toUpperCase()))
      errs.machine_code = 'Machine code already exists';
    if (!form.name.trim()) errs.name = 'Required';
    if (!form.location.trim()) errs.location = 'Required';
    if (!form.sector.trim()) errs.sector = 'Required';
    if (!form.ip_address.trim()) errs.ip_address = 'Required';
    else if (!/^\d{1,3}(\.\d{1,3}){3}$/.test(form.ip_address.trim()))
      errs.ip_address = 'Invalid IP (e.g. 192.168.10.50)';
    const rpm = Number(form.motor_speed_rpm);
    if (isNaN(rpm) || rpm <= 0) errs.motor_speed_rpm = 'Must be > 0';
    const temp = Number(form.temperature_limit_c);
    if (isNaN(temp) || temp <= 0) errs.temperature_limit_c = 'Must be > 0';
    const press = Number(form.pressure_limit_bar);
    if (isNaN(press) || press <= 0) errs.pressure_limit_bar = 'Must be > 0';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate() || syncState === 'syncing') return;
    setSyncState('syncing');

    const now = new Date().toISOString();
    const machine: Machine = {
      id: `m-custom-${Date.now()}`,
      machine_code: form.machine_code.trim().toUpperCase(),
      name: form.name.trim(),
      location: form.location.trim(),
      sector: form.sector.trim(),
      machine_type: form.machine_type,
      status: form.status,
      plc_version: form.plc_version.trim() || 'v17',
      motor_speed_rpm: Number(form.motor_speed_rpm),
      temperature_limit_c: Number(form.temperature_limit_c),
      pressure_limit_bar: Number(form.pressure_limit_bar),
      ip_address: form.ip_address.trim(),
      firmware_version: form.firmware_version.trim() || 'FW-4.9.0',
      last_maintenance: now,
      created_at: now,
    };

    try {
      const res = await onAdd(machine);
      if (res && res.dbSynced) {
        setSyncState('synced');
      } else {
        setSyncState('local');
      }
    } catch {
      setSyncState('local');
    }

    setTimeout(() => {
      setSyncState('idle');
      setForm(EMPTY_FORM);
      setErrors({});
      onClose();
    }, 1400);
  };

  const handleClose = () => {
    setForm(EMPTY_FORM);
    setErrors({});
    setSyncState('idle');
    onClose();
  };

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" onClick={handleClose} />
      <div className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-[520px] flex flex-col bg-[#0b1322] border-l border-slate-700/60 shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-1.5 rounded-lg bg-cyan-950/60 border border-cyan-800/40">
              <Plus className="w-4 h-4 text-cyan-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-white">Register New Machine</h2>
                <span className="flex items-center gap-1 text-[9px] font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800/40 px-2 py-0.5 rounded">
                  <Database className="w-2.5 h-2.5 text-emerald-400" /> Cloud DB
                </span>
              </div>
              <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Machine Registry · Supabase Synced</p>
            </div>
          </div>
          <button onClick={handleClose} className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable form */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">

          {/* Identity */}
          <div>
            <p className="text-[10px] font-mono text-cyan-500 uppercase tracking-[0.2em] mb-3 flex items-center gap-2">
              <span className="h-px flex-1 bg-cyan-900/40" />Identity<span className="h-px flex-1 bg-cyan-900/40" />
            </p>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Machine Code" required error={errors.machine_code}>
                <input className={inputCls} placeholder="e.g. CNC-07" value={form.machine_code} onChange={set('machine_code')} />
              </Field>
              <Field label="Status" required>
                <select className={selectCls} value={form.status} onChange={set('status')}>
                  {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </Field>
            </div>
            <div className="mt-4">
              <Field label="Machine Name" required error={errors.name}>
                <input className={inputCls} placeholder="e.g. High-Speed Vertical Milling Centre" value={form.name} onChange={set('name')} />
              </Field>
            </div>
          </div>

          {/* Location */}
          <div>
            <p className="text-[10px] font-mono text-indigo-500 uppercase tracking-[0.2em] mb-3 flex items-center gap-2">
              <span className="h-px flex-1 bg-indigo-900/40" />Location<span className="h-px flex-1 bg-indigo-900/40" />
            </p>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Location" required error={errors.location}>
                <input className={inputCls} placeholder="e.g. Shop Floor - Bay 5" value={form.location} onChange={set('location')} />
              </Field>
              <Field label="Sector" required error={errors.sector}>
                <input className={inputCls} placeholder="e.g. Automotive Components" value={form.sector} onChange={set('sector')} />
              </Field>
            </div>
          </div>

          {/* Configuration */}
          <div>
            <p className="text-[10px] font-mono text-amber-500 uppercase tracking-[0.2em] mb-3 flex items-center gap-2">
              <span className="h-px flex-1 bg-amber-900/40" />Configuration<span className="h-px flex-1 bg-amber-900/40" />
            </p>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Machine Type" required>
                <select className={selectCls} value={form.machine_type} onChange={set('machine_type')}>
                  {MACHINE_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                </select>
              </Field>
              <Field label="PLC Version">
                <input className={inputCls} placeholder="e.g. v17" value={form.plc_version} onChange={set('plc_version')} />
              </Field>
              <Field label="Motor Speed (RPM)" error={errors.motor_speed_rpm}>
                <input type="number" className={inputCls} placeholder="1500" value={form.motor_speed_rpm} onChange={set('motor_speed_rpm')} />
              </Field>
              <Field label="Temp Limit (°C)" error={errors.temperature_limit_c}>
                <input type="number" className={inputCls} placeholder="80" value={form.temperature_limit_c} onChange={set('temperature_limit_c')} />
              </Field>
              <Field label="Pressure Limit (bar)" error={errors.pressure_limit_bar}>
                <input type="number" className={inputCls} placeholder="6.0" value={form.pressure_limit_bar} onChange={set('pressure_limit_bar')} />
              </Field>
              <Field label="Firmware Version">
                <input className={inputCls} placeholder="FW-4.9.0" value={form.firmware_version} onChange={set('firmware_version')} />
              </Field>
            </div>
          </div>

          {/* Network */}
          <div>
            <p className="text-[10px] font-mono text-emerald-500 uppercase tracking-[0.2em] mb-3 flex items-center gap-2">
              <span className="h-px flex-1 bg-emerald-900/40" />Network<span className="h-px flex-1 bg-emerald-900/40" />
            </p>
            <Field label="IP Address" required error={errors.ip_address}>
              <input className={inputCls} placeholder="192.168.10.50" value={form.ip_address} onChange={set('ip_address')} />
            </Field>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/60 flex items-center gap-3 flex-shrink-0">
          <button
            onClick={handleClose}
            className="flex-1 py-2.5 rounded-lg border border-slate-700 text-slate-300 text-sm font-mono hover:bg-slate-800 transition"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={syncState !== 'idle'}
            className={`flex-1 py-2.5 rounded-lg text-sm font-mono font-bold flex items-center justify-center gap-2 transition ${
              syncState === 'syncing'
                ? 'bg-cyan-900/60 border border-cyan-600/40 text-cyan-200 cursor-wait'
                : syncState === 'synced'
                ? 'bg-emerald-700/60 border border-emerald-600/40 text-emerald-300 cursor-not-allowed'
                : syncState === 'local'
                ? 'bg-amber-700/60 border border-amber-600/40 text-amber-200 cursor-not-allowed'
                : 'bg-cyan-700/70 hover:bg-cyan-600/80 border border-cyan-500/50 text-white shadow-[0_0_20px_rgba(0,240,255,0.15)]'
            }`}
          >
            {syncState === 'syncing' && (
              <>
                <div className="w-3.5 h-3.5 border-2 border-cyan-300 border-t-transparent rounded-full animate-spin" />
                <span>Syncing to Supabase...</span>
              </>
            )}
            {syncState === 'synced' && (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-300" />
                <span>Saved to Supabase DB!</span>
              </>
            )}
            {syncState === 'local' && (
              <>
                <CheckCircle2 className="w-4 h-4 text-amber-300" />
                <span>Saved (Local Registry)</span>
              </>
            )}
            {syncState === 'idle' && (
              <>
                <Plus className="w-4 h-4" />
                <span>Register Machine</span>
              </>
            )}
          </button>
        </div>
      </div>
    </>
  );
}

// ─── Machines List Page ───────────────────────────────────────────────────────

export function MachinesPage() {
  const { machines, addMachine } = useSimulation();
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [modalOpen, setModalOpen] = useState(false);

  const filtered = machines.filter(m => {
    const q = query.toLowerCase();
    const matchQ = !q || m.machine_code.toLowerCase().includes(q) || m.name.toLowerCase().includes(q) || m.sector.toLowerCase().includes(q);
    const matchS = statusFilter === 'ALL' || m.status === statusFilter;
    return matchQ && matchS;
  });

  const existingCodes = new Set(machines.map(m => m.machine_code.toUpperCase()));

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <SectionHeader
          icon={<Server className="w-5 h-5" />}
          title="Machine Registry"
          subtitle={`${machines.length} registered assets across ${new Set(machines.map(m => m.sector)).size} sectors`}
        />
        <button
          onClick={() => setModalOpen(true)}
          className="flex-shrink-0 flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-700/60 hover:bg-cyan-600/70 border border-cyan-500/50 text-white text-sm font-mono font-bold transition shadow-[0_0_20px_rgba(0,240,255,0.12)] hover:shadow-[0_0_28px_rgba(0,240,255,0.2)]"
        >
          <Plus className="w-4 h-4" />
          Add Machine
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            placeholder="Search machines, code, sector…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-900/80 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-700 transition"
          />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-slate-500" />
          {['ALL', 'OPERATIONAL', 'MAINTENANCE', 'CRITICAL', 'OFFLINE'].map(s => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-2.5 py-1.5 rounded text-[10px] font-mono uppercase transition border ${
                statusFilter === s
                  ? 'bg-cyan-950/60 border-cyan-600/50 text-cyan-300'
                  : 'border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
          <AlertTriangle className="w-8 h-8 text-slate-600" />
          <p className="text-slate-400 text-sm">No machines match your filter.</p>
          <p className="text-slate-600 text-xs font-mono">Try adjusting the search or status filter.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(m => <MachineCard key={m.id} m={m} />)}
        </div>
      )}

      <AddMachineModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onAdd={addMachine}
        existingCodes={existingCodes}
      />
    </div>
  );
}

// ─── Machine Detail Page ──────────────────────────────────────────────────────

export function MachineDetailPage() {
  const { code } = useParams<{ code: string }>();
  const { machines, sessions: allSessions, changes: allChanges, plcResults } = useSimulation();
  const machine = machines.find(m => m.machine_code === code);

  if (!machine) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-400">Machine <span className="font-mono text-white">{code}</span> not found.</p>
      </div>
    );
  }

  const sessions = allSessions.filter(s => s.machine_code === machine.machine_code);
  const changes = allChanges.filter(c => c.machine_code === machine.machine_code);
  const plcResult = plcResults.find(p => p.machine_code === machine.machine_code);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-950/40 border border-cyan-800/30">
            <Server className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-white">{machine.machine_code}</h1>
              <span className="text-slate-400">—</span>
              <span className="text-sm text-slate-300">{machine.name}</span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">{machine.location} · {machine.sector}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <MachineStatusBadge status={machine.status} />
        </div>
      </div>

      {/* Parameters Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'PLC Version', value: machine.plc_version, icon: <Cpu className="w-4 h-4" />, color: 'text-indigo-400' },
          { label: 'Motor Speed', value: `${machine.motor_speed_rpm} RPM`, icon: <Activity className="w-4 h-4" />, color: 'text-cyan-400' },
          { label: 'Temp Limit', value: `${machine.temperature_limit_c}°C`, icon: <Thermometer className="w-4 h-4" />, color: 'text-amber-400' },
          { label: 'Pressure', value: `${machine.pressure_limit_bar} bar`, icon: <Gauge className="w-4 h-4" />, color: 'text-blue-400' },
          { label: 'IP Address', value: machine.ip_address, icon: <Wifi className="w-4 h-4" />, color: 'text-emerald-400' },
          { label: 'Firmware', value: machine.firmware_version, icon: <Shield className="w-4 h-4" />, color: 'text-purple-400' },
          { label: 'Machine Type', value: machine.machine_type.replace(/_/g, ' '), icon: <Server className="w-4 h-4" />, color: 'text-slate-400' },
          { label: 'Last Maintenance', value: new Date(machine.last_maintenance).toLocaleDateString(), icon: <Clock className="w-4 h-4" />, color: 'text-slate-400' },
        ].map((p, i) => (
          <Card key={i} className="p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-mono text-slate-500 uppercase">{p.label}</span>
              <span className={p.color}>{p.icon}</span>
            </div>
            <p className="text-sm font-mono font-semibold text-white">{p.value}</p>
          </Card>
        ))}
      </div>

      {/* PLC Status */}
      {plcResult && (
        <Card className="p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-semibold text-white">PLC Logic Integrity</span>
            </div>
            <Badge plcStatus={plcResult.integrity_status}>{plcResult.integrity_status.replace(/_/g, ' ')}</Badge>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2 text-xs font-mono">
              <div className="flex items-center justify-between p-2 bg-slate-900/50 rounded border border-slate-800">
                <span className="text-slate-400">Baseline Hash</span>
                <span className="text-slate-300 truncate ml-2">{plcResult.baseline_hash.slice(0, 16)}…</span>
              </div>
              <div className="flex items-center justify-between p-2 bg-slate-900/50 rounded border border-slate-800">
                <span className="text-slate-400">Current Hash</span>
                <span className={`truncate ml-2 ${plcResult.hash_match ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {plcResult.current_hash.slice(0, 16)}…
                </span>
              </div>
              <div className="flex items-center justify-between p-2 bg-slate-900/50 rounded border border-slate-800">
                <span className="text-slate-400">Hash Match</span>
                <span className={plcResult.hash_match ? 'text-emerald-400' : 'text-rose-400'}>
                  {plcResult.hash_match ? '✓ MATCH' : '✗ MISMATCH'}
                </span>
              </div>
            </div>
            <div className={`p-3 rounded-lg border text-xs ${
              plcResult.safety_violations.length > 0
                ? 'bg-rose-950/30 border-rose-700/50 text-rose-300'
                : 'bg-emerald-950/20 border-emerald-700/30 text-emerald-300'
            }`}>
              <p className="font-mono font-bold mb-1">{plcResult.integrity_message}</p>
              {plcResult.safety_violations.map((v, i) => (
                <p key={i} className="text-rose-400 mt-1">⚠ {v}</p>
              ))}
            </div>
          </div>
        </Card>
      )}

      {/* Sessions */}
      <Card className="p-5">
        <div className="flex items-center gap-2 mb-4">
          <Clock className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-semibold text-white">Maintenance Sessions ({sessions.length})</span>
        </div>
        <div className="space-y-2">
          {sessions.length === 0 && <p className="text-xs text-slate-500 text-center py-4">No sessions recorded.</p>}
          {sessions.map(s => (
            <Link key={s.id} to={`/maintenance/${s.id}`}
              className="flex items-center justify-between p-3 bg-slate-900/50 border border-slate-800 rounded-lg hover:border-slate-600 transition"
            >
              <div>
                <p className="text-xs font-mono text-white">{s.session_code}</p>
                <p className="text-[10px] text-slate-400">{s.engineer_name}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge sessionStatus={s.session_status}>{s.session_status.replace('_', ' ')}</Badge>
                <Badge verificationStatus={s.verification_status}>{s.verification_status}</Badge>
              </div>
            </Link>
          ))}
        </div>
      </Card>

      {/* Recent Changes */}
      <Card className="p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-amber-400" />
            <span className="text-sm font-semibold text-white">Changes ({changes.length})</span>
          </div>
          <Link to="/changes" className="text-[10px] font-mono text-cyan-400 hover:text-cyan-300">VIEW ALL →</Link>
        </div>
        <div className="space-y-2">
          {changes.length === 0 && <p className="text-xs text-slate-500 text-center py-4">No changes recorded.</p>}
          {changes.map(c => (
            <div key={c.id} className="flex items-center justify-between p-3 bg-slate-900/50 border border-slate-800 rounded-lg">
              <div>
                <p className="text-xs font-mono text-white">{c.parameter_name}</p>
                <p className="text-[10px] text-slate-400">{c.old_value} → {c.new_value}</p>
              </div>
              <div className="flex items-center gap-2">
                <RiskBar score={c.risk_score} />
                <Badge riskLevel={c.risk_level}>{c.risk_level}</Badge>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
