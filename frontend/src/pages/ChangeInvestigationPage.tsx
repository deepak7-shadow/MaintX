import { useState } from 'react';
import { Search, Filter, AlertOctagon, AlertTriangle, Activity, User, Clock } from 'lucide-react';
import { useSimulation } from '../lib/simulationStore';
import { Badge, Card, RiskBar, SectionHeader } from '../components/ui';
import type { RiskLevel, ChangeCategory } from '../lib/types';

const CATEGORY_COLORS: Record<ChangeCategory, string> = {
  PARAMETERS: 'text-cyan-400',
  PLC_LOGIC: 'text-indigo-400',
  NETWORK: 'text-purple-400',
  FIRMWARE: 'text-amber-400',
  FIREWALL: 'text-pink-400',
  SAFETY_CONFIG: 'text-rose-400',
};

export function ChangeInvestigationPage() {
  const { changes: CHANGES } = useSimulation();
  const [query, setQuery] = useState('');
  const [riskFilter, setRiskFilter] = useState<string>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [authFilter, setAuthFilter] = useState<'ALL' | 'AUTHORIZED' | 'UNAUTHORIZED'>('ALL');

  const filtered = CHANGES.filter(c => {
    const q = query.toLowerCase();
    const matchQ = !q ||
      c.parameter_name.toLowerCase().includes(q) ||
      (c.machine_code ?? '').toLowerCase().includes(q) ||
      (c.user_name ?? '').toLowerCase().includes(q) ||
      c.category.toLowerCase().includes(q);
    const matchR = riskFilter === 'ALL' || c.risk_level === riskFilter;
    const matchC = categoryFilter === 'ALL' || c.category === categoryFilter;
    const matchA =
      authFilter === 'ALL' ||
      (authFilter === 'AUTHORIZED' && c.is_authorized) ||
      (authFilter === 'UNAUTHORIZED' && !c.is_authorized);
    return matchQ && matchR && matchC && matchA;
  });

  const criticalCount = CHANGES.filter(c => c.risk_level === 'CRITICAL').length;
  const unauthorizedCount = CHANGES.filter(c => !c.is_authorized).length;

  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<Search className="w-5 h-5" />}
        title="Change Investigation"
        subtitle={`${CHANGES.length} total changes detected across all machines`}
      />

      {/* Alert bar */}
      {criticalCount > 0 && (
        <div className="bg-rose-950/30 border border-rose-700/50 rounded-xl p-4 flex items-center gap-3">
          <AlertOctagon className="w-4 h-4 text-rose-400 animate-pulse flex-shrink-0" />
          <p className="text-sm text-rose-300">
            <strong>{criticalCount} CRITICAL</strong> and <strong>{unauthorizedCount} UNAUTHORIZED</strong> changes require immediate investigation.
          </p>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Critical', count: CHANGES.filter(c => c.risk_level === 'CRITICAL').length, color: 'text-rose-400', bg: 'border-rose-800/30 bg-rose-950/10' },
          { label: 'High Risk', count: CHANGES.filter(c => c.risk_level === 'HIGH').length, color: 'text-amber-400', bg: 'border-amber-800/30' },
          { label: 'Unauthorized', count: CHANGES.filter(c => !c.is_authorized).length, color: 'text-rose-400', bg: 'border-rose-800/30' },
          { label: 'Expected', count: CHANGES.filter(c => c.is_expected).length, color: 'text-emerald-400', bg: 'border-emerald-800/20' },
        ].map((s, i) => (
          <Card key={i} className={`p-4 ${s.bg}`}>
            <p className="text-[10px] font-mono text-slate-500 uppercase">{s.label}</p>
            <p className={`text-2xl font-bold font-mono mt-1 ${s.color}`}>{s.count}</p>
          </Card>
        ))}
      </div>

      {/* Filters */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            placeholder="Search parameter, machine, engineer, category…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-900/80 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-700 transition"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-500" />
          <div className="flex items-center gap-1 flex-wrap">
            {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as (string | RiskLevel)[]).map(r => (
              <button
                key={r}
                onClick={() => setRiskFilter(r)}
                className={`px-2 py-1 rounded text-[10px] font-mono uppercase border transition ${
                  riskFilter === r ? 'bg-cyan-950/60 border-cyan-600/50 text-cyan-300' : 'border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
          <div className="h-4 w-px bg-slate-700" />
          <div className="flex items-center gap-1 flex-wrap">
            {(['ALL', ...(['PARAMETERS', 'PLC_LOGIC', 'NETWORK', 'FIRMWARE', 'FIREWALL', 'SAFETY_CONFIG'] as ChangeCategory[])]).map(c => (
              <button
                key={c}
                onClick={() => setCategoryFilter(c)}
                className={`px-2 py-1 rounded text-[10px] font-mono uppercase border transition ${
                  categoryFilter === c ? 'bg-cyan-950/60 border-cyan-600/50 text-cyan-300' : 'border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
          <div className="h-4 w-px bg-slate-700" />
          <div className="flex items-center gap-1">
            {(['ALL', 'AUTHORIZED', 'UNAUTHORIZED'] as const).map(a => (
              <button
                key={a}
                onClick={() => setAuthFilter(a)}
                className={`px-2 py-1 rounded text-[10px] font-mono uppercase border transition ${
                  authFilter === a ? 'bg-cyan-950/60 border-cyan-600/50 text-cyan-300' : 'border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                {a}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Changes List */}
      <div className="space-y-3">
        {filtered.length === 0 && (
          <Card className="p-8 text-center">
            <p className="text-slate-400">No changes match your filters.</p>
          </Card>
        )}
        {filtered.map(c => (
          <Card
            key={c.id}
            className={`p-4 ${
              c.risk_level === 'CRITICAL' ? 'border-rose-800/50 bg-rose-950/10' :
              c.risk_level === 'HIGH' ? 'border-amber-800/40' : ''
            }`}
          >
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
              {/* Left */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-2">
                  {(c.risk_level === 'CRITICAL' || c.risk_level === 'HIGH') && (
                    <AlertTriangle className={`w-3.5 h-3.5 flex-shrink-0 ${
                      c.risk_level === 'CRITICAL' ? 'text-rose-400 animate-pulse' : 'text-amber-400'
                    }`} />
                  )}
                  <span className="text-sm font-mono font-bold text-white">{c.parameter_name}</span>
                  <span className={`text-[10px] font-mono font-semibold ${CATEGORY_COLORS[c.category]}`}>
                    [{c.category}]
                  </span>
                  {!c.is_authorized && (
                    <span className="text-[10px] font-mono bg-rose-950/70 border border-rose-700/50 text-rose-300 px-1.5 py-0.5 rounded font-bold">
                      UNAUTHORIZED
                    </span>
                  )}
                </div>

                {/* Value change */}
                <div className="flex items-center gap-2 text-xs font-mono mb-2">
                  <span className="px-2 py-0.5 rounded bg-rose-950/40 border border-rose-800/30 text-rose-300">{c.old_value}</span>
                  <span className="text-slate-500">→</span>
                  <span className="px-2 py-0.5 rounded bg-emerald-950/40 border border-emerald-800/30 text-emerald-300">{c.new_value}</span>
                </div>

                <p className="text-[10px] text-slate-400 leading-snug">{c.reason || 'No reason provided.'}</p>
              </div>

              {/* Right */}
              <div className="flex flex-col items-end gap-2 flex-shrink-0">
                <div className="flex items-center gap-1.5">
                  <Badge riskLevel={c.risk_level}>{c.risk_level}</Badge>
                  {c.classification && <Badge classification={c.classification}>{c.classification}</Badge>}
                </div>
                <div className="w-28">
                  <RiskBar score={c.risk_score} />
                </div>
                {c.ai_anomaly_score !== undefined && (
                  <span className="text-[10px] font-mono text-indigo-400">
                    ML Score: {c.ai_anomaly_score}/100
                  </span>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center gap-4 mt-3 pt-3 border-t border-slate-800/50 text-[10px] font-mono text-slate-500">
              <span className="flex items-center gap-1"><Activity className="w-3 h-3" />{c.machine_code}</span>
              <span className="flex items-center gap-1"><User className="w-3 h-3" />{c.user_name}</span>
              <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{new Date(c.timestamp).toLocaleString()}</span>
              <span className={c.is_authorized ? 'text-emerald-500' : 'text-rose-500'}>
                {c.is_authorized ? '✓ AUTHORIZED' : '✗ UNAUTHORIZED'}
              </span>
              <span className={c.is_expected ? 'text-emerald-500' : 'text-amber-500'}>
                {c.is_expected ? '✓ EXPECTED' : '⚠ UNEXPECTED'}
              </span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
