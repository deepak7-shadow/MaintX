import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Wrench, Search, CheckCircle2,
  User, ShieldCheck, Calendar, ChevronRight, Activity
} from 'lucide-react';
import { useSimulation } from '../lib/simulationStore';
import { Badge, Card, SectionHeader, RiskBar } from '../components/ui';
import type { SessionStatus } from '../lib/types';

// ─── Maintenance List Page ────────────────────────────────────────────────────

export function MaintenancePage() {
  const { sessions } = useSimulation();
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  const filtered = sessions.filter(s => {
    const q = query.toLowerCase();
    const matchQ = !q ||
      s.session_code.toLowerCase().includes(q) ||
      (s.machine_code ?? '').toLowerCase().includes(q) ||
      (s.engineer_name ?? '').toLowerCase().includes(q);
    const matchS = statusFilter === 'ALL' || s.session_status === statusFilter;
    return matchQ && matchS;
  });

  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<Wrench className="w-5 h-5" />}
        title="Maintenance Sessions"
        subtitle={`${sessions.length} sessions — ${sessions.filter(s => s.session_status === 'IN_PROGRESS').length} active`}
      />

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'In Progress', value: sessions.filter(s => s.session_status === 'IN_PROGRESS').length, color: 'text-cyan-400' },
          { label: 'Awaiting Approval', value: sessions.filter(s => s.session_status === 'SUPERVISOR_APPROVED').length, color: 'text-indigo-400' },
          { label: 'Completed', value: sessions.filter(s => s.session_status === 'COMPLETED').length, color: 'text-emerald-400' },
          { label: 'Pending', value: sessions.filter(s => s.session_status === 'PENDING').length, color: 'text-slate-400' },
        ].map((s, i) => (
          <Card key={i} className="p-4">
            <p className="text-[10px] font-mono text-slate-500 uppercase">{s.label}</p>
            <p className={`text-2xl font-bold font-mono mt-1 ${s.color}`}>{s.value}</p>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            placeholder="Search session code, machine, engineer…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-900/80 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-700 transition"
          />
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          {['ALL', 'IN_PROGRESS', 'PENDING', 'SUPERVISOR_APPROVED', 'COMPLETED'].map(s => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-2.5 py-1.5 rounded text-[10px] font-mono uppercase transition border ${
                statusFilter === s
                  ? 'bg-cyan-950/60 border-cyan-600/50 text-cyan-300'
                  : 'border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {s.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Sessions Table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-800">
                {['Session', 'Machine', 'Engineer', 'Status', 'Verification', 'Risk', 'Started', ''].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {filtered.map(s => (
                <tr key={s.id} className="hover:bg-slate-800/20 transition">
                  <td className="px-4 py-3">
                    <p className="font-mono font-semibold text-white">{s.session_code}</p>
                  </td>
                  <td className="px-4 py-3">
                    <Link to={`/machines/${s.machine_code}`} className="font-mono text-cyan-400 hover:text-cyan-300 transition">
                      {s.machine_code}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <User className="w-3 h-3 text-slate-500" />
                      <span className="text-slate-300">{s.engineer_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge sessionStatus={s.session_status}>
                      {s.session_status.replace(/_/g, ' ')}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge verificationStatus={s.verification_status}>
                      {s.verification_status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge riskLevel={s.risk_level ?? 'LOW'}>{s.risk_level ?? 'LOW'}</Badge>
                  </td>
                  <td className="px-4 py-3 text-slate-400 font-mono">
                    {s.started_at ? new Date(s.started_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <Link to={`/maintenance/${s.id}`} className="text-slate-500 hover:text-cyan-400 transition">
                      <ChevronRight className="w-4 h-4" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <p className="text-center text-slate-500 py-8 text-sm">No sessions match your filters.</p>
          )}
        </div>
      </Card>
    </div>
  );
}

// ─── Maintenance Detail Page ──────────────────────────────────────────────────

export function MaintenanceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { sessions, changes } = useSimulation();
  const session = sessions.find(s => s.id === id || s.session_code === id);

  if (!session) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-400">Session <span className="font-mono text-white">{id}</span> not found.</p>
      </div>
    );
  }

  const sessionChanges = changes.filter(c => c.session_id === session.session_code || c.session_id === session.id);

  const steps: { label: string; key: SessionStatus; icon: typeof CheckCircle2 }[] = [
    { label: 'Created', key: 'PENDING', icon: Calendar },
    { label: 'Assigned', key: 'ASSIGNED', icon: User },
    { label: 'Approved', key: 'SUPERVISOR_APPROVED', icon: ShieldCheck },
    { label: 'In Progress', key: 'IN_PROGRESS', icon: Wrench },
    { label: 'Completed', key: 'COMPLETED', icon: CheckCircle2 },
  ];

  const stepOrder: SessionStatus[] = ['PENDING', 'ASSIGNED', 'SUPERVISOR_APPROVED', 'IN_PROGRESS', 'COMPLETED'];
  const currentIdx = stepOrder.indexOf(session.session_status);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-950/40 border border-blue-800/30">
            <Wrench className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-white">{session.session_code}</h1>
              <Badge sessionStatus={session.session_status}>{session.session_status.replace(/_/g, ' ')}</Badge>
              <Badge verificationStatus={session.verification_status}>{session.verification_status}</Badge>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              <Link to={`/machines/${session.machine_code}`} className="text-cyan-400 hover:underline">
                {session.machine_code}
              </Link>
              {' '}· {session.engineer_name}
            </p>
          </div>
        </div>
      </div>

      {/* Progress Timeline */}
      <Card className="p-5">
        <p className="text-xs font-mono text-slate-400 uppercase tracking-wider mb-4">Workflow Progress</p>
        <div className="flex items-center gap-0">
          {steps.map((step, i) => {
            const done = i <= currentIdx;
            const active = i === currentIdx;
            const Icon = step.icon;
            return (
              <div key={step.key} className="flex items-center flex-1">
                <div className={`flex flex-col items-center gap-1.5 flex-1 ${i === 0 ? '' : ''}`}>
                  {i > 0 && (
                    <div className={`h-0.5 w-full -mt-3 mb-3 ${done ? 'bg-cyan-600' : 'bg-slate-800'}`} />
                  )}
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center border-2 transition ${
                    active ? 'bg-cyan-950 border-cyan-500 text-cyan-400' :
                    done ? 'bg-emerald-950 border-emerald-600 text-emerald-400' :
                    'bg-slate-900 border-slate-700 text-slate-600'
                  }`}>
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <span className={`text-[9px] font-mono text-center ${
                    active ? 'text-cyan-400' : done ? 'text-emerald-400' : 'text-slate-600'
                  }`}>
                    {step.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-5 space-y-3">
          <p className="text-xs font-mono text-slate-400 uppercase tracking-wider mb-2">Session Details</p>
          {[
            { label: 'Machine', value: session.machine_name, link: `/machines/${session.machine_code}` },
            { label: 'Engineer', value: session.engineer_name },
            { label: 'Started', value: session.started_at ? new Date(session.started_at).toLocaleString() : 'Not yet started' },
            { label: 'Completed', value: session.completed_at ? new Date(session.completed_at).toLocaleString() : '—' },
          ].map((row, i) => (
            <div key={i} className="flex items-start justify-between text-xs">
              <span className="text-slate-500 font-mono uppercase w-24 flex-shrink-0">{row.label}</span>
              {row.link ? (
                <Link to={row.link} className="text-cyan-400 hover:underline text-right">{row.value}</Link>
              ) : (
                <span className="text-slate-200 text-right">{row.value}</span>
              )}
            </div>
          ))}
        </Card>

        <Card className="p-5">
          <p className="text-xs font-mono text-slate-400 uppercase tracking-wider mb-3">Notes</p>
          <p className="text-sm text-slate-300 leading-relaxed">{session.notes || 'No notes recorded.'}</p>
        </Card>
      </div>

      {/* Changes During Session */}
      <Card className="p-5">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-semibold text-white">Changes During Session ({sessionChanges.length})</span>
        </div>
        {sessionChanges.length === 0 ? (
          <p className="text-xs text-slate-500 text-center py-4">No changes recorded for this session.</p>
        ) : (
          <div className="space-y-2">
            {sessionChanges.map(c => (
              <div key={c.id} className="p-3 bg-slate-900/50 border border-slate-800 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono text-white">{c.parameter_name}</span>
                  <div className="flex items-center gap-1.5">
                    <Badge classification={c.classification}>{c.classification}</Badge>
                    <Badge riskLevel={c.risk_level}>{c.risk_level}</Badge>
                  </div>
                </div>
                <div className="flex items-center gap-3 text-[10px] font-mono text-slate-400">
                  <span className="text-rose-400">{c.old_value}</span>
                  <span>→</span>
                  <span className="text-emerald-400">{c.new_value}</span>
                  <span className="text-slate-500">·</span>
                  <span>{c.category}</span>
                </div>
                <RiskBar score={c.risk_score} />
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Verification Result */}
      <Card className={`p-5 border ${
        session.verification_status === 'VERIFIED'
          ? 'border-emerald-700/40 bg-emerald-950/10'
          : session.verification_status === 'FAILED'
          ? 'border-rose-700/40 bg-rose-950/10'
          : 'border-slate-800'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className={`w-4 h-4 ${
              session.verification_status === 'VERIFIED' ? 'text-emerald-400' :
              session.verification_status === 'FAILED' ? 'text-rose-400' : 'text-slate-400'
            }`} />
            <span className="text-sm font-semibold text-white">Final Verification</span>
          </div>
          <Badge verificationStatus={session.verification_status}>{session.verification_status}</Badge>
        </div>
        <p className="text-xs text-slate-400 mt-2">
          {session.verification_status === 'VERIFIED'
            ? 'All changes matched approved scope. PLC integrity confirmed. Maintenance closure authorized.'
            : session.verification_status === 'FAILED'
            ? 'Critical changes detected. Maintenance closure BLOCKED pending resolution.'
            : 'Verification not yet executed for this session.'}
        </p>
      </Card>
    </div>
  );
}
