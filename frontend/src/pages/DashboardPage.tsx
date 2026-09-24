import {
  LayoutDashboard, Server, Wrench, Cpu, AlertTriangle,
  ShieldCheck, CheckCircle2, Activity, GitCompare,
  TrendingUp, Hash, AlertOctagon
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';
import { Link } from 'react-router-dom';
import { useSimulation } from '../lib/simulationStore';
import { Badge, Card, RiskBar } from '../components/ui';

// ─── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({
  icon, label, value, sub, color, to, pulse
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  color: string;
  to?: string;
  pulse?: boolean;
}) {
  const content = (
    <div className={`bg-[#0f1524] border rounded-xl p-4 flex flex-col gap-3 transition hover:border-slate-600 group ${
      pulse ? 'border-rose-700/60' : 'border-slate-800'
    }`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">{label}</span>
        <div className={`p-1.5 rounded-lg ${color}`}>
          {icon}
        </div>
      </div>
      <div>
        <div className={`text-3xl font-extrabold font-mono tracking-tight ${pulse ? 'text-rose-400' : 'text-white'}`}>
          {value}
          {pulse && <span className="inline-block w-2 h-2 rounded-full bg-rose-500 ml-2 animate-pulse align-middle" />}
        </div>
        {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
      </div>
    </div>
  );

  if (to) {
    return <Link to={to}>{content}</Link>;
  }
  return content;
}

// ─── Dashboard Page ───────────────────────────────────────────────────────────

export function DashboardPage() {
  const {
    stats: s,
    sessions,
    notifications,
    riskTrendData,
    categoryDistribution,
    machineRiskData,
    activeSimSession,
    resetSimulation
  } = useSimulation();

  const STATS = [
    {
      icon: <Server className="w-4 h-4" />,
      label: 'Total Machines',
      value: s.total_machines,
      sub: `${s.operational_machines} operational`,
      color: 'bg-cyan-950/50 text-cyan-400',
      to: '/machines',
    },
    {
      icon: <Wrench className="w-4 h-4" />,
      label: 'Active Maintenance',
      value: s.active_sessions,
      sub: `${s.machines_in_maintenance} machine(s) in maintenance`,
      color: 'bg-blue-950/50 text-blue-400',
      to: '/maintenance',
    },
    {
      icon: <Activity className="w-4 h-4" />,
      label: 'Changes Today',
      value: s.changes_today,
      sub: 'All tracked categories',
      color: 'bg-indigo-950/50 text-indigo-400',
      to: '/changes',
    },
    {
      icon: <AlertTriangle className="w-4 h-4" />,
      label: 'High Risk Changes',
      value: s.high_risk_changes,
      sub: 'Risk score ≥ 60',
      color: 'bg-amber-950/50 text-amber-400',
      to: '/changes',
    },
    {
      icon: <AlertOctagon className="w-4 h-4" />,
      label: 'Critical Changes',
      value: s.critical_changes,
      sub: 'Requires immediate review',
      color: 'bg-rose-950/50 text-rose-400',
      to: '/changes',
      pulse: s.critical_changes > 0,
    },
    {
      icon: <GitCompare className="w-4 h-4" />,
      label: 'Unresolved Changes',
      value: s.unresolved_changes,
      sub: 'Pending classification',
      color: 'bg-purple-950/50 text-purple-400',
      to: '/changes',
    },
    {
      icon: <Cpu className="w-4 h-4" />,
      label: 'PLC Integrity Violations',
      value: s.plc_violations,
      sub: 'Hash mismatch or safety breach',
      color: 'bg-rose-950/50 text-rose-400',
      to: '/plc-integrity',
      pulse: s.plc_violations > 0,
    },
    {
      icon: <CheckCircle2 className="w-4 h-4" />,
      label: 'Verified Machines',
      value: s.verified_machines,
      sub: `of ${s.total_machines} total`,
      color: 'bg-emerald-950/50 text-emerald-400',
      to: '/machines',
    },
    {
      icon: <Hash className="w-4 h-4" />,
      label: 'Audit Log Integrity',
      value: s.audit_log_integrity,
      sub: `${s.chain_length} events in chain`,
      color: 'bg-cyan-950/50 text-cyan-400',
      to: '/logbook',
    },
  ];

  const criticalAlerts = notifications.filter(n => n.type === 'CRITICAL' && !n.read);

  return (
    <div className="space-y-6">
      {/* Critical Alert Banner */}
      {criticalAlerts.length > 0 && (
        <div className="bg-rose-950/30 border border-rose-700/50 rounded-xl p-4 flex items-start gap-3">
          <AlertOctagon className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5 animate-pulse" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-rose-300">
              {criticalAlerts.length} CRITICAL ALERT{criticalAlerts.length > 1 ? 'S' : ''} REQUIRING IMMEDIATE ATTENTION
            </p>
            <p className="text-xs text-rose-400/80 mt-0.5">{criticalAlerts[0].title}</p>
          </div>
          <Link
            to="/notifications"
            className="text-xs font-mono text-rose-400 hover:text-rose-300 border border-rose-700/50 px-2.5 py-1 rounded transition whitespace-nowrap"
          >
            VIEW ALL
          </Link>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <LayoutDashboard className="w-5 h-5 text-cyan-400" />
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-white">Security Operations Dashboard</h1>
              {activeSimSession.active && (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-950/80 border border-rose-500/60 text-rose-300 animate-pulse">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                  LIVE SIMULATION: {activeSimSession.machine} ({activeSimSession.job})
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">
              CNC Sector · Real-time ICS/SCADA monitoring · Zero-Trust Maintenance
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={resetSimulation}
            className="px-2.5 py-1.5 rounded-lg text-xs font-mono text-slate-400 hover:text-slate-200 border border-slate-800 hover:border-slate-700 bg-slate-900/50 transition"
            title="Reset simulation data back to initial baseline"
          >
            Reset
          </button>
        </div>
      </div>

      {/* 9 KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {STATS.map((s, i) => (
          <StatCard key={i} {...s} />
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Risk Trend Area Chart */}
        <Card className="lg:col-span-2 p-5">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-semibold text-white">Risk Trend — Last 7 Days</span>
            </div>
            <span className="text-[10px] text-slate-500 font-mono">ALL MACHINES</span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={riskTrendData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="critical" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="high" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, fontSize: 11 }}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Area type="monotone" dataKey="critical" stroke="#f43f5e" fill="url(#critical)" strokeWidth={2} />
              <Area type="monotone" dataKey="high" stroke="#f59e0b" fill="url(#high)" strokeWidth={2} />
              <Area type="monotone" dataKey="medium" stroke="#eab308" fill="none" strokeDasharray="3 3" strokeWidth={1.5} />
              <Area type="monotone" dataKey="low" stroke="#10b981" fill="none" strokeDasharray="3 3" strokeWidth={1.5} />
            </AreaChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-2 text-[10px] font-mono text-slate-500">
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-rose-500 rounded-full inline-block" />CRITICAL</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-amber-500 rounded-full inline-block" />HIGH</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-yellow-400 rounded-full inline-block" />MEDIUM</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-emerald-400 rounded-full inline-block" />LOW</span>
          </div>
        </Card>

        {/* Change Category Pie */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-indigo-400" />
            <span className="text-sm font-semibold text-white">By Category</span>
          </div>
          <ResponsiveContainer width="100%" height={170}>
            <PieChart>
              <Pie
                data={categoryDistribution}
                innerRadius={50}
                outerRadius={80}
                dataKey="value"
                paddingAngle={3}
              >
                {categoryDistribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, fontSize: 11 }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1 mt-2">
            {categoryDistribution.map(cat => (
              <div key={cat.name} className="flex items-center justify-between text-[10px] font-mono">
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: cat.color }} />
                  <span className="text-slate-400">{cat.name}</span>
                </span>
                <span className="text-slate-300">{cat.value}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Machine Risk Scores */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <ShieldCheck className="w-4 h-4 text-cyan-400" />
            <span className="text-sm font-semibold text-white">Machine Risk Scores</span>
          </div>
          <div className="space-y-3">
            {machineRiskData.map(m => (
              <div key={m.machine}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <Link to={`/machines/${m.machine}`} className="font-mono text-slate-300 hover:text-cyan-400 transition">
                    {m.machine}
                  </Link>
                  <Badge riskLevel={m.score >= 85 ? 'CRITICAL' : m.score >= 60 ? 'HIGH' : m.score >= 30 ? 'MEDIUM' : 'LOW'}>
                    {m.score >= 85 ? 'CRITICAL' : m.score >= 60 ? 'HIGH' : m.score >= 30 ? 'MEDIUM' : 'LOW'}
                  </Badge>
                </div>
                <RiskBar score={m.score} />
              </div>
            ))}
          </div>
        </Card>

        {/* Recent Sessions */}
        <Card className="p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Wrench className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-semibold text-white">Recent Sessions</span>
            </div>
            <Link to="/maintenance" className="text-[10px] font-mono text-cyan-400 hover:text-cyan-300 transition">
              VIEW ALL →
            </Link>
          </div>
          <div className="space-y-2">
            {sessions.slice(0, 4).map(s => (
              <Link
                key={s.id}
                to={`/maintenance/${s.id}`}
                className="flex items-center justify-between p-2.5 rounded-lg bg-slate-900/50 border border-slate-800 hover:border-slate-600 transition"
              >
                <div>
                  <p className="text-xs font-mono text-white">{s.session_code}</p>
                  <p className="text-[10px] text-slate-400">{s.machine_code} · {s.engineer_name}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <Badge sessionStatus={s.session_status}>{s.session_status.replace('_', ' ')}</Badge>
                  <Badge verificationStatus={s.verification_status}>{s.verification_status}</Badge>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
