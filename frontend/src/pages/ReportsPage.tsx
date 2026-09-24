import { useState, useMemo } from 'react';
import {
  FileText, Download, ShieldCheck, ShieldAlert,
  Calendar, Filter, RefreshCw, FileCheck, AlertOctagon,
  CheckCircle2, Activity, Hash, Inbox
} from 'lucide-react';
import { Card, Badge, SectionHeader } from '../components/ui';
import { useSimulation } from '../lib/simulationStore';

type ReportCategory = 'COMPLIANCE' | 'SECURITY_INCIDENT' | 'MAINTENANCE_AUDIT' | 'PLC_INTEGRITY';

interface ReportItem {
  id: string;
  code: string;
  title: string;
  category: ReportCategory;
  standard: string;
  generated_at: string;
  generated_by: string;
  status: 'READY' | 'GENERATING' | 'ARCHIVED';
  summary: string;
  risk_level?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  file_size: string;
  session_code?: string;
  chain_length?: number;
  change_count?: number;
  unauthorized_count?: number;
  ledger_hash?: string;
  plc_violations?: number;
}

export function ReportsPage() {
  const {
    sessions,
    changes,
    auditLog,
    plcResults,
    stats,
    isChainTampered,
  } = useSimulation();

  const [filter, setFilter] = useState<string>('ALL');
  const [generating, setGenerating] = useState<boolean>(false);
  const [activeReport, setActiveReport] = useState<ReportItem | null>(null);

  const REPORTS = useMemo<ReportItem[]>(() => {
    const reports: ReportItem[] = [];

    sessions.forEach((s) => {
      const sessionChanges = changes.filter(c => c.session_id === s.session_code);
      const unauthorized = sessionChanges.filter(c => !c.is_authorized).length;
      const criticalChanges = sessionChanges.filter(c => c.risk_level === 'CRITICAL').length;
      const hasViolation = unauthorized > 0 || criticalChanges > 0;
      const riskLevel: ReportItem['risk_level'] =
        criticalChanges > 0 ? 'CRITICAL' :
        unauthorized > 0 ? 'HIGH' :
        sessionChanges.length > 0 ? 'MEDIUM' : 'LOW';

      reports.push({
        id: `rpt-maint-${s.id}`,
        code: `MNT-${s.session_code}`,
        title: `Maintenance Audit — ${s.session_code} on ${s.machine_code}`,
        category: 'MAINTENANCE_AUDIT',
        standard: 'MaintX Zero-Trust Gateway Policy v2.4',
        generated_at: (s.completed_at || s.started_at) as string,
        generated_by: s.engineer_name ?? 'Unknown Engineer',
        status: s.session_status === 'COMPLETED' ? 'READY' : 'GENERATING',
        summary: `Work order ${s.session_code} on ${s.machine_code} — ${sessionChanges.length} parameter change${sessionChanges.length !== 1 ? 's' : ''} recorded. ${unauthorized} unauthorized, ${criticalChanges} critical. ${hasViolation ? 'Flagged for supervisor review.' : 'Passed Zero-Trust verification.'}`,
        risk_level: riskLevel,
        file_size: `${(0.6 + sessionChanges.length * 0.15).toFixed(1)} MB`,
        session_code: s.session_code,
        change_count: sessionChanges.length,
        unauthorized_count: unauthorized,
      });

      if (hasViolation) {
        const critChange = sessionChanges.find(c => c.risk_level === 'CRITICAL' || !c.is_authorized);
        reports.push({
          id: `rpt-inc-${s.id}`,
          code: `INC-${s.session_code}-SEC`,
          title: `Security Incident: Unauthorized Action — ${s.machine_code}`,
          category: 'SECURITY_INCIDENT',
          standard: 'Zero-Trust Maintenance Enforcement',
          generated_at: (critChange?.timestamp ?? s.started_at) as string,
          generated_by: 'SOC Incident Response Engine',
          status: 'READY',
          summary: `Unauthorized or critical change during session ${s.session_code} on ${s.machine_code}. ${critChange ? `Parameter: ${critChange.parameter_name}. Risk: ${critChange.risk_level}.` : ''} Incident logged to immutable audit ledger.`,
          risk_level: 'CRITICAL',
          file_size: '1.2 MB',
          session_code: s.session_code,
          unauthorized_count: unauthorized,
        });
      }
    });

    plcResults.forEach(p => {
      const isCompromised = p.integrity_status !== 'VERIFIED';
      reports.push({
        id: `rpt-plc-${p.machine_code}`,
        code: `PLC-${p.machine_code}-${p.baseline_version}`,
        title: `PLC Integrity Certificate — ${p.machine_code} (${p.baseline_version} to ${p.current_version})`,
        category: 'PLC_INTEGRITY',
        standard: 'NIST SP 800-82r3 / IEC 62443-3-3',
        generated_at: p.analysed_at,
        generated_by: 'MaintX Cryptographic Hash Engine',
        status: 'READY',
        summary: `SHA-256 hash validation for PLC logic on ${p.machine_code}. Baseline: ${p.baseline_version}, Current: ${p.current_version}. ${isCompromised ? `INTEGRITY BREACH: ${p.integrity_message}` : `Hash match confirmed. ${p.integrity_message}`}`,
        risk_level: isCompromised ? 'CRITICAL' : 'LOW',
        file_size: '840 KB',
        ledger_hash: p.current_hash,
        plc_violations: p.safety_violations.length,
        chain_length: auditLog.length,
      });
    });

    if (auditLog.length > 1) {
      const headBlock = auditLog[auditLog.length - 1];
      reports.push({
        id: 'rpt-compliance-ledger',
        code: `LEDGER-COMPLIANCE-${new Date().toISOString().slice(0, 10)}`,
        title: 'Cryptographic Ledger Compliance Certificate',
        category: 'COMPLIANCE',
        standard: 'IEC 62443-3-3 / NIST SP 800-82r3',
        generated_at: headBlock.created_at,
        generated_by: 'MaintX Authoritative Hash Chain',
        status: 'READY',
        summary: `Immutable audit ledger integrity report. Chain length: ${auditLog.length} blocks. Genesis to HEAD hash chain ${isChainTampered ? 'BROKEN — tampering detected!' : 'INTACT and cryptographically verified'}. ${stats.changes_today} configuration events logged.`,
        risk_level: isChainTampered ? 'CRITICAL' : 'LOW',
        file_size: `${(auditLog.length * 0.08).toFixed(1)} MB`,
        chain_length: auditLog.length,
        ledger_hash: headBlock.current_hash,
      });

      if (sessions.length > 0) {
        reports.push({
          id: 'rpt-iec62443',
          code: `IEC-62443-${new Date().toISOString().slice(0, 10)}`,
          title: 'IEC 62443 Industrial Security Audit Report',
          category: 'COMPLIANCE',
          standard: 'IEC 62443-3-3 / ISA-99',
          generated_at: new Date().toISOString(),
          generated_by: 'Automated SOC Auditor',
          status: 'READY',
          summary: `Automated audit of ${stats.total_machines} industrial assets. ${stats.plc_violations} PLC violation${stats.plc_violations !== 1 ? 's' : ''} flagged. ${stats.critical_changes} critical change${stats.critical_changes !== 1 ? 's' : ''} recorded. Ledger: ${isChainTampered ? 'COMPROMISED' : 'INTACT'}.`,
          risk_level: stats.critical_changes > 0 || isChainTampered ? 'CRITICAL' : stats.high_risk_changes > 0 ? 'HIGH' : 'LOW',
          file_size: `${(2 + changes.length * 0.1).toFixed(1)} MB`,
          chain_length: auditLog.length,
          change_count: changes.length,
        });
      }
    }

    return reports.sort((a, b) =>
      new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime()
    );
  }, [sessions, changes, auditLog, plcResults, stats, isChainTampered]);

  const filtered = REPORTS.filter(r => filter === 'ALL' || r.category === filter);

  const handleGenerate = () => {
    setGenerating(true);
    setTimeout(() => setGenerating(false), 1500);
  };

  const downloadReport = (r: ReportItem) => {
    const latestBlock = auditLog[auditLog.length - 1];
    const changesText = changes.length === 0
      ? '  No changes recorded.'
      : changes.slice(0, 20).map((c, i) =>
          `  ${i + 1}. [${c.risk_level}] ${c.parameter_name} -- ${c.old_value} -> ${c.new_value}\n     By: ${c.user_name} | ${new Date(c.timestamp).toLocaleString()} | ${c.is_authorized ? 'AUTHORIZED' : 'UNAUTHORIZED'}`
        ).join('\n');
    const auditText = auditLog.slice(-10).map((b, i) =>
      `  Block #${i + 1}: ${b.event_type}\n  Hash: ${b.current_hash}\n  Prev: ${b.previous_hash}\n  At:   ${new Date(b.created_at).toLocaleString()}`
    ).join('\n\n');
    const plcText = plcResults.map(p =>
      `  ${p.machine_code}: ${p.integrity_status} | ${p.baseline_version} -> ${p.current_version} | Match: ${p.hash_match ? 'YES' : 'NO'}`
    ).join('\n');

    const content = [
      '===============================================================',
      'MAINTX INDUSTRIAL ZERO-TRUST CYBERSECURITY REPORT',
      '===============================================================',
      `Report Code:     ${r.code}`,
      `Title:           ${r.title}`,
      `Category:        ${r.category}`,
      `Standard:        ${r.standard}`,
      `Generated:       ${new Date(r.generated_at).toLocaleString()}`,
      `Generated By:    ${r.generated_by}`,
      `Risk Level:      ${r.risk_level || 'N/A'}`,
      `Ledger Chain:    ${r.chain_length ?? auditLog.length} blocks`,
      `Ledger State:    ${isChainTampered ? 'COMPROMISED' : 'INTACT -- SHA-256 Verified'}`,
      `Head Hash:       ${r.ledger_hash || latestBlock?.current_hash || 'N/A'}`,
      '===============================================================',
      '',
      'EXECUTIVE SUMMARY:',
      r.summary,
      '',
      'LIVE DATA SNAPSHOT:',
      `  Machines:            ${stats.total_machines}`,
      `  In Maintenance:      ${stats.machines_in_maintenance}`,
      `  Config Changes:      ${stats.changes_today}`,
      `  Critical Changes:    ${stats.critical_changes}`,
      `  Unauthorized:        ${stats.unresolved_changes}`,
      `  PLC Violations:      ${stats.plc_violations}`,
      `  Verified Baselines:  ${stats.verified_machines}`,
      `  Audit Chain Length:  ${stats.chain_length}`,
      '',
      'CONFIGURATION CHANGES:',
      changesText,
      '',
      'AUDIT LOG (Last 10 Blocks):',
      auditText,
      '',
      'PLC INTEGRITY STATUS:',
      plcText,
      '',
      'CERTIFICATION:',
      'Digitally sealed by MaintX Authoritative Hash Engine.',
      'Report reflects live simulation state at time of export.',
      '===============================================================',
    ].join('\n');

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${r.code}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const categoryIcon = (cat: ReportCategory) => {
    if (cat === 'SECURITY_INCIDENT') return <ShieldAlert className="w-4 h-4 text-rose-400" />;
    if (cat === 'PLC_INTEGRITY') return <Hash className="w-4 h-4 text-indigo-400" />;
    if (cat === 'MAINTENANCE_AUDIT') return <Activity className="w-4 h-4 text-amber-400" />;
    return <ShieldCheck className="w-4 h-4 text-cyan-400" />;
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<FileText className="w-5 h-5" />}
        title="Industrial Compliance & Security Reports"
        subtitle={`${REPORTS.length} report${REPORTS.length !== 1 ? 's' : ''} available — auto-compiled from maintenance sessions & integrity audits`}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-300 text-xs font-mono hover:bg-slate-800 transition disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
              {generating ? 'Refreshing...' : 'Refresh Reports'}
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Reports Generated', val: REPORTS.length, icon: <FileText className="w-4 h-4" />, color: 'text-cyan-400' },
          { label: 'Critical Events', val: stats.critical_changes, icon: <AlertOctagon className="w-4 h-4" />, color: stats.critical_changes > 0 ? 'text-rose-400' : 'text-emerald-400' },
          { label: 'PLC Violations', val: stats.plc_violations, icon: <ShieldAlert className="w-4 h-4" />, color: stats.plc_violations > 0 ? 'text-amber-400' : 'text-emerald-400' },
          { label: 'Ledger Integrity', val: isChainTampered ? 'COMPROMISED' : 'INTACT', icon: <CheckCircle2 className="w-4 h-4" />, color: isChainTampered ? 'text-rose-400' : 'text-emerald-400' },
        ].map((item, i) => (
          <Card key={i} className="p-4 flex items-center gap-3">
            <span className={`${item.color} opacity-70`}>{item.icon}</span>
            <div>
              <p className={`text-lg font-bold font-mono ${item.color}`}>{item.val}</p>
              <p className="text-[10px] text-slate-500 font-mono uppercase">{item.label}</p>
            </div>
          </Card>
        ))}
      </div>

      <div className="flex items-center gap-2 flex-wrap border-b border-slate-800/80 pb-3">
        <Filter className="w-4 h-4 text-slate-500" />
        {(['ALL', 'COMPLIANCE', 'SECURITY_INCIDENT', 'MAINTENANCE_AUDIT', 'PLC_INTEGRITY'] as const).map(cat => (
          <button
            key={cat}
            onClick={() => setFilter(cat)}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono transition border ${
              filter === cat
                ? 'bg-cyan-950/70 border-cyan-500/50 text-cyan-300 font-bold'
                : 'border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            {cat.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {filtered.length === 0 && (
        <Card className="p-16 text-center">
          <Inbox className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-300 font-mono text-sm font-semibold">No Reports Yet</p>
          <p className="text-slate-500 text-xs mt-2 max-w-sm mx-auto">
            Operational maintenance sessions, PLC logic integrity scans, and tamper-evident audit blocks will auto-generate compliance reports.
          </p>
        </Card>
      )}

      <div className="space-y-4">
        {filtered.map(report => (
          <Card
            key={report.id}
            className={`p-5 hover:border-slate-700 transition ${report.status === 'GENERATING' ? 'opacity-70 border-dashed' : ''}`}
          >
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2.5 flex-wrap mb-1.5">
                  {categoryIcon(report.category)}
                  <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 font-mono text-[10px] text-cyan-400 font-semibold">
                    {report.code}
                  </span>
                  <span className="text-[11px] font-mono text-slate-400">{report.standard}</span>
                  {report.risk_level && <Badge riskLevel={report.risk_level}>{report.risk_level}</Badge>}
                  {report.status === 'GENERATING' && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-amber-950/40 border border-amber-700/40 text-amber-400 text-[10px] font-mono">
                      <RefreshCw className="w-2.5 h-2.5 animate-spin" /> IN PROGRESS
                    </span>
                  )}
                </div>
                <h3 className="text-base font-bold text-white tracking-tight">{report.title}</h3>
                <p className="text-xs text-slate-300 mt-2 leading-relaxed">{report.summary}</p>
                <div className="flex items-center flex-wrap gap-3 text-[10px] font-mono text-slate-500 mt-3 pt-3 border-t border-slate-800/60">
                  <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{new Date(report.generated_at).toLocaleString()}</span>
                  <span className="flex items-center gap-1"><ShieldCheck className="w-3 h-3 text-cyan-500" />{report.generated_by}</span>
                  {report.chain_length !== undefined && <span className="flex items-center gap-1 text-indigo-400"><Hash className="w-3 h-3" />{report.chain_length} blocks</span>}
                  {report.change_count !== undefined && <span className="text-amber-400">{report.change_count} changes</span>}
                  {!!report.unauthorized_count && <span className="text-rose-400">{report.unauthorized_count} unauthorized</span>}
                  <span>Size: {report.file_size}</span>
                </div>
              </div>
              <div className="flex md:flex-col items-center gap-2 flex-shrink-0">
                <button
                  onClick={() => downloadReport(report)}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-cyan-950/40 border border-cyan-800/40 text-cyan-300 text-xs font-mono hover:bg-cyan-900/40 transition"
                >
                  <Download className="w-3.5 h-3.5" /><span>Export .TXT</span>
                </button>
                <button
                  onClick={() => setActiveReport(report)}
                  className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 text-xs font-mono hover:border-slate-600 transition"
                >
                  <FileCheck className="w-3.5 h-3.5 text-emerald-400" /><span>Inspect Digest</span>
                </button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {activeReport && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <Card className="w-full max-w-2xl p-6 bg-[#0a0f1d] border-cyan-800/60 shadow-2xl relative max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between border-b border-slate-800 pb-4 mb-4">
              <div>
                <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-widest">CRYPTOGRAPHIC ATTESTATION DIGEST</span>
                <h3 className="text-lg font-bold text-white mt-1">{activeReport.title}</h3>
                <p className="text-xs text-slate-400 font-mono mt-0.5">{activeReport.code} -- {activeReport.standard}</p>
              </div>
              <button onClick={() => setActiveReport(null)} className="text-slate-400 hover:text-white transition p-1">X</button>
            </div>
            <div className="space-y-3 text-xs font-mono">
              <div className="p-3 rounded bg-slate-950/70 border border-slate-800 space-y-1">
                <span className="text-slate-500 uppercase text-[10px]">Ledger HEAD Block Hash</span>
                <p className="text-emerald-400 break-all select-all">
                  {activeReport.ledger_hash || auditLog[auditLog.length - 1]?.current_hash || 'No blocks yet'}
                </p>
              </div>
              <div className={`p-3 rounded border space-y-1 ${isChainTampered ? 'bg-rose-950/20 border-rose-800/40' : 'bg-emerald-950/10 border-emerald-800/30'}`}>
                <span className="text-slate-500 uppercase text-[10px]">Hash Chain Integrity</span>
                <p className={isChainTampered ? 'text-rose-400' : 'text-emerald-400'}>
                  {isChainTampered
                    ? 'CHAIN COMPROMISED -- Unauthorized block alteration detected'
                    : `INTACT -- ${auditLog.length} blocks verified, genesis to HEAD unbroken`}
                </p>
              </div>
              <div className="p-3 rounded bg-slate-950/70 border border-slate-800 space-y-2">
                <span className="text-slate-500 uppercase text-[10px]">Live Session Metrics</span>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-slate-300">
                  <span>Config Changes:</span><span className="text-white">{activeReport.change_count ?? stats.changes_today}</span>
                  <span>Unauthorized:</span><span className={(activeReport.unauthorized_count ?? 0) > 0 ? 'text-rose-400' : 'text-slate-300'}>{activeReport.unauthorized_count ?? stats.unresolved_changes}</span>
                  <span>PLC Violations:</span><span className={stats.plc_violations > 0 ? 'text-amber-400' : 'text-slate-300'}>{activeReport.plc_violations ?? stats.plc_violations}</span>
                  <span>Audit Blocks:</span><span className="text-indigo-400">{activeReport.chain_length ?? stats.chain_length}</span>
                </div>
              </div>
              <div className="p-3 rounded bg-slate-950/70 border border-slate-800 space-y-1">
                <span className="text-slate-500 uppercase text-[10px]">Compliance Attestation</span>
                <p className="text-slate-300 leading-relaxed">Sealed under IEC 62443 Technical Security Requirements (SL-T Level 3). All events cryptographically chained and tamper-evident via Zero-Trust Maintenance Gateway.</p>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-slate-800">
              <button onClick={() => setActiveReport(null)} className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono transition">Close</button>
              <button onClick={() => { downloadReport(activeReport); setActiveReport(null); }} className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono transition flex items-center gap-2">
                <Download className="w-3.5 h-3.5" />Export Verified Report
              </button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
