import { Cpu, ShieldCheck, AlertOctagon, CheckCircle2, Hash, History } from 'lucide-react';
import { PLC_RESULTS } from '../lib/mockData';
import { Badge, Card, HashChip, SectionHeader } from '../components/ui';
import type { PLCStatus } from '../lib/types';

const statusIcon = (s: PLCStatus) => {
  if (s === 'VERIFIED') return <CheckCircle2 className="w-5 h-5 text-emerald-400" />;
  if (s === 'SAFETY_INTERLOCK_COMPROMISED') return <AlertOctagon className="w-5 h-5 text-rose-400 animate-pulse" />;
  return <AlertOctagon className="w-5 h-5 text-amber-400" />;
};

const statusBg = (s: PLCStatus) => {
  if (s === 'VERIFIED') return 'border-emerald-700/30 bg-emerald-950/10';
  if (s === 'SAFETY_INTERLOCK_COMPROMISED') return 'border-rose-700/50 bg-rose-950/20';
  return 'border-amber-700/40 bg-amber-950/10';
};

export function PLCIntegrityPage() {
  // Derive hash_match by comparing the actual hash strings — never trust the stored boolean.
  const resultsWithDerivedMatch = PLC_RESULTS.map(r => ({
    ...r,
    hash_match: r.baseline_hash === r.current_hash,
  }));

  const violations = resultsWithDerivedMatch.filter(r => r.integrity_status !== 'VERIFIED');
  const verified = resultsWithDerivedMatch.filter(r => r.integrity_status === 'VERIFIED');

  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<Cpu className="w-5 h-5" />}
        title="PLC Logic Integrity Monitor"
        subtitle="SHA-256 hash comparison · Semantic AST diff · N7 safety interlock tracking"
      />

      {/* Summary Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4 border-emerald-800/30 bg-emerald-950/10">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-mono text-slate-400 uppercase">Verified</span>
          </div>
          <p className="text-3xl font-bold font-mono text-emerald-400">{verified.length}</p>
          <p className="text-[10px] text-slate-500 mt-1">Hash matches approved baseline</p>
        </Card>
        <Card className="p-4 border-rose-800/40 bg-rose-950/10">
          <div className="flex items-center gap-2 mb-2">
            <AlertOctagon className="w-4 h-4 text-rose-400" />
            <span className="text-xs font-mono text-slate-400 uppercase">Violations</span>
          </div>
          <p className="text-3xl font-bold font-mono text-rose-400">{violations.length}</p>
          <p className="text-[10px] text-slate-500 mt-1">Requires immediate investigation</p>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <Hash className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-mono text-slate-400 uppercase">Total Audited</span>
          </div>
          <p className="text-3xl font-bold font-mono text-white">{PLC_RESULTS.length}</p>
          <p className="text-[10px] text-slate-500 mt-1">PLC programs analysed</p>
        </Card>
      </div>

      {/* PLC Results */}
      <div className="space-y-4">
        {resultsWithDerivedMatch.map(r => (
          <Card key={r.machine_code} className={`p-5 ${statusBg(r.integrity_status)}`}>
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                {statusIcon(r.integrity_status)}
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-white font-mono">{r.machine_code}</h3>
                    <Badge plcStatus={r.integrity_status}>
                      {r.integrity_status.replace(/_/g, ' ')}
                    </Badge>
                  </div>
                  <p className={`text-xs mt-1 ${
                    r.integrity_status === 'VERIFIED' ? 'text-emerald-400' :
                    r.integrity_status === 'SAFETY_INTERLOCK_COMPROMISED' ? 'text-rose-400' : 'text-amber-400'
                  }`}>
                    {r.integrity_message}
                  </p>
                </div>
              </div>
              <div className="text-[10px] font-mono text-slate-500">
                {new Date(r.analysed_at).toLocaleString()}
              </div>
            </div>

            {/* Hash comparison */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Left: Hash table */}
              <div className="space-y-2">
                <div className="flex items-center justify-between p-2 bg-slate-900/60 border border-slate-800 rounded text-xs font-mono">
                  <span className="text-slate-400 uppercase text-[10px]">Baseline Version</span>
                  <span className="text-slate-200">{r.baseline_version}</span>
                </div>
                <div className="flex items-center justify-between p-2 bg-slate-900/60 border border-slate-800 rounded text-xs font-mono">
                  <span className="text-slate-400 uppercase text-[10px]">Current Version</span>
                  <span className="text-slate-200">{r.current_version}</span>
                </div>
                <div className="flex items-center justify-between p-2 bg-slate-900/60 border border-slate-800 rounded text-xs">
                  <span className="text-slate-400 font-mono uppercase text-[10px]">Baseline Hash</span>
                  <HashChip hash={r.baseline_hash} />
                </div>
                <div className="flex items-center justify-between p-2 bg-slate-900/60 border border-slate-800 rounded text-xs">
                  <span className="text-slate-400 font-mono uppercase text-[10px]">Current Hash</span>
                  <HashChip hash={r.current_hash} />
                </div>
                <div className={`flex items-center justify-between p-2 rounded text-xs font-mono border ${
                  r.hash_match
                    ? 'bg-emerald-950/30 border-emerald-700/40'
                    : 'bg-rose-950/30 border-rose-700/50'
                }`}>
                  <span className="text-slate-400 uppercase text-[10px]">Hash Match</span>
                  <span className={r.hash_match ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                    {r.hash_match ? '✓ MATCH' : '✗ MISMATCH'}
                  </span>
                </div>
              </div>

              {/* Right: Violations / Safety */}
              <div className="space-y-2">
                {r.safety_violations.length > 0 ? (
                  <div className="p-3 bg-rose-950/40 border border-rose-700/40 rounded-lg space-y-2">
                    <div className="flex items-center gap-1.5">
                      <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
                      <span className="text-xs font-mono font-bold text-rose-300 uppercase">Safety Violations</span>
                    </div>
                    {r.safety_violations.map((v, i) => (
                      <p key={i} className="text-xs text-rose-300 leading-snug border-l-2 border-rose-500 pl-2">{v}</p>
                    ))}
                  </div>
                ) : (
                  <div className="p-3 bg-emerald-950/20 border border-emerald-700/30 rounded-lg">
                    <div className="flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-xs font-mono font-bold text-emerald-300">No Safety Violations</span>
                    </div>
                    <p className="text-xs text-emerald-400/70 mt-1">All safety-critical networks are intact.</p>
                  </div>
                )}

                <div className="p-2 bg-slate-900/50 border border-slate-800 rounded flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400 uppercase text-[10px]">Total Changes</span>
                  <span className="text-slate-200">{r.total_changes}</span>
                </div>
              </div>
            </div>

            {/* Full hashes */}
            <div className="mt-3 p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-1">
              <p className="text-[9px] font-mono text-slate-600 uppercase tracking-widest mb-1">Full SHA-256 Hashes</p>
              <div className="flex items-center gap-2 text-[10px] font-mono">
                <span className="text-slate-500 w-20 flex-shrink-0">BASELINE:</span>
                <span className="text-slate-400 break-all">{r.baseline_hash}</span>
              </div>
              <div className="flex items-start gap-2 text-[10px] font-mono">
                <span className="text-slate-500 w-20 flex-shrink-0">CURRENT:</span>
                <span className={`break-all ${r.hash_match ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {r.current_hash}
                </span>
              </div>
              {r.previous_hash && (
                <div className="mt-2 pt-2 border-t border-slate-800">
                  <div className="flex items-center gap-1.5 mb-1">
                    <History className="w-3 h-3 text-slate-500" />
                    <span className="text-[9px] font-mono text-slate-600 uppercase tracking-widest">
                      Previous Version ({r.previous_version}) Hash
                    </span>
                  </div>
                  <div className="flex items-start gap-2 text-[10px] font-mono">
                    <span className="text-slate-600 w-20 flex-shrink-0">PREVIOUS:</span>
                    <span className="text-slate-600 break-all">{r.previous_hash}</span>
                  </div>
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>

      {/* Legend */}
      <Card className="p-4">
        <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-3">PLC Integrity Status Legend</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
          {[
            { status: 'VERIFIED' as PLCStatus, desc: 'Current hash matches approved baseline. No unauthorized changes.' },
            { status: 'HASH_MISMATCH' as PLCStatus, desc: 'Hash differs from approved logic. Logic content modified.' },
            { status: 'UNAPPROVED_LOGIC' as PLCStatus, desc: 'Logic modified beyond approved change scope.' },
            { status: 'SAFETY_INTERLOCK_COMPROMISED' as PLCStatus, desc: 'Safety-critical network (e.g. N7) removed or modified. IMMEDIATE ACTION REQUIRED.' },
          ].map(item => (
            <div key={item.status} className="p-3 bg-slate-900/50 border border-slate-800 rounded-lg space-y-1.5">
              <Badge plcStatus={item.status}>{item.status.replace(/_/g, ' ')}</Badge>
              <p className="text-slate-400 text-[10px] leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
