import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Server, Search, Filter, Cpu, Activity,
  Thermometer, Gauge, Wifi, ChevronRight, Shield, Clock
} from 'lucide-react';
import { MACHINES, SESSIONS, CHANGES, PLC_RESULTS } from '../lib/mockData';
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
            <p className="text-xs font-mono text-slate-400">{m.machine_type.replace('_', ' ')}</p>
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

// ─── Machines List Page ───────────────────────────────────────────────────────

export function MachinesPage() {
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  const filtered = MACHINES.filter(m => {
    const q = query.toLowerCase();
    const matchQ = !q || m.machine_code.toLowerCase().includes(q) || m.name.toLowerCase().includes(q) || m.sector.toLowerCase().includes(q);
    const matchS = statusFilter === 'ALL' || m.status === statusFilter;
    return matchQ && matchS;
  });

  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<Server className="w-5 h-5" />}
        title="Machine Registry"
        subtitle={`${MACHINES.length} registered assets across ${new Set(MACHINES.map(m => m.sector)).size} sectors`}
      />

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
        <div className="flex items-center gap-2">
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
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map(m => <MachineCard key={m.id} m={m} />)}
      </div>
    </div>
  );
}

// ─── Machine Detail Page ──────────────────────────────────────────────────────

export function MachineDetailPage() {
  const { code } = useParams<{ code: string }>();
  const machine = MACHINES.find(m => m.machine_code === code);

  if (!machine) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-400">Machine <span className="font-mono text-white">{code}</span> not found.</p>
      </div>
    );
  }

  const sessions = SESSIONS.filter(s => s.machine_code === machine.machine_code);
  const changes = CHANGES.filter(c => c.machine_code === machine.machine_code);
  const plcResult = PLC_RESULTS.find(p => p.machine_code === machine.machine_code);

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
          { label: 'Machine Type', value: machine.machine_type.replace('_', ' '), icon: <Server className="w-4 h-4" />, color: 'text-slate-400' },
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
