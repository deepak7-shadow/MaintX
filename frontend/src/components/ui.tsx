import { type ReactNode } from 'react';
import type { RiskLevel, VerificationStatus, SessionStatus, PLCStatus, ChangeClassification } from '../lib/types';

// ─── Badge Component ──────────────────────────────────────────────────────────

interface BadgeProps {
  children: ReactNode;
  variant?: 'risk' | 'status' | 'plc' | 'classification' | 'custom';
  riskLevel?: RiskLevel;
  sessionStatus?: SessionStatus;
  verificationStatus?: VerificationStatus;
  plcStatus?: PLCStatus;
  classification?: ChangeClassification;
  className?: string;
}

export function Badge({ children, riskLevel, sessionStatus, verificationStatus, plcStatus, classification, className = '' }: BadgeProps) {
  let base = 'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest border ';

  if (riskLevel) {
    const map: Record<RiskLevel, string> = {
      LOW: 'bg-emerald-950/70 border-emerald-500/40 text-emerald-300',
      MEDIUM: 'bg-yellow-950/70 border-yellow-500/40 text-yellow-300',
      HIGH: 'bg-amber-950/70 border-amber-500/40 text-amber-300',
      CRITICAL: 'bg-rose-950/70 border-rose-500/50 text-rose-300',
    };
    return <span className={base + map[riskLevel] + ' ' + className}>{children}</span>;
  }

  if (sessionStatus) {
    const map: Record<SessionStatus, string> = {
      PENDING: 'bg-slate-800 border-slate-600 text-slate-300',
      ASSIGNED: 'bg-blue-950/70 border-blue-500/40 text-blue-300',
      SUPERVISOR_APPROVED: 'bg-indigo-950/70 border-indigo-500/40 text-indigo-300',
      IN_PROGRESS: 'bg-cyan-950/70 border-cyan-500/40 text-cyan-300',
      COMPLETED: 'bg-emerald-950/70 border-emerald-500/40 text-emerald-300',
      CANCELLED: 'bg-slate-900 border-slate-700 text-slate-500',
    };
    return <span className={base + map[sessionStatus] + ' ' + className}>{children}</span>;
  }

  if (verificationStatus) {
    const map: Record<VerificationStatus, string> = {
      PENDING: 'bg-slate-800 border-slate-600 text-slate-300',
      VERIFIED: 'bg-emerald-950/70 border-emerald-500/40 text-emerald-300',
      REVIEW_REQUIRED: 'bg-amber-950/70 border-amber-500/40 text-amber-300',
      FAILED: 'bg-rose-950/70 border-rose-500/50 text-rose-300',
    };
    return <span className={base + map[verificationStatus] + ' ' + className}>{children}</span>;
  }

  if (plcStatus) {
    const map: Record<PLCStatus, string> = {
      VERIFIED: 'bg-emerald-950/70 border-emerald-500/40 text-emerald-300',
      HASH_MISMATCH: 'bg-amber-950/70 border-amber-500/40 text-amber-300',
      UNAPPROVED_LOGIC: 'bg-amber-950/70 border-amber-500/40 text-amber-300',
      SAFETY_INTERLOCK_COMPROMISED: 'bg-rose-950/70 border-rose-600/60 text-rose-300',
    };
    return <span className={base + map[plcStatus] + ' ' + className}>{children}</span>;
  }

  if (classification) {
    const map: Record<ChangeClassification, string> = {
      EXPECTED: 'bg-emerald-950/70 border-emerald-500/40 text-emerald-300',
      UNEXPECTED: 'bg-amber-950/70 border-amber-500/40 text-amber-300',
      UNAUTHORIZED: 'bg-rose-950/70 border-rose-500/50 text-rose-300',
      UNRESOLVED: 'bg-purple-950/70 border-purple-500/40 text-purple-300',
    };
    return <span className={base + map[classification] + ' ' + className}>{children}</span>;
  }

  return <span className={base + 'bg-slate-800 border-slate-700 text-slate-300 ' + className}>{children}</span>;
}

// ─── Risk Score Bar ───────────────────────────────────────────────────────────

export function RiskBar({ score }: { score: number }) {
  const color =
    score >= 85 ? 'from-rose-500 to-red-600' :
    score >= 60 ? 'from-amber-500 to-orange-500' :
    score >= 30 ? 'from-yellow-400 to-amber-400' :
    'from-emerald-400 to-teal-500';

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${color} transition-all duration-500`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="text-xs font-mono text-slate-400 w-6 text-right">{score}</span>
    </div>
  );
}

// ─── Section Card ─────────────────────────────────────────────────────────────

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-[#0f1524] border border-slate-800 rounded-xl ${className}`}>
      {children}
    </div>
  );
}

// ─── Hash Chip ────────────────────────────────────────────────────────────────

export function HashChip({ hash, short = true }: { hash: string; short?: boolean }) {
  const display = short ? `${hash.slice(0, 8)}…${hash.slice(-6)}` : hash;
  return (
    <span className="font-mono text-[10px] text-slate-400 bg-slate-900/70 border border-slate-800 px-1.5 py-0.5 rounded select-all">
      {display}
    </span>
  );
}

// ─── Status Dot ──────────────────────────────────────────────────────────────

export function StatusDot({ status }: { status: 'OPERATIONAL' | 'MAINTENANCE' | 'OFFLINE' | 'CRITICAL' }) {
  const map = {
    OPERATIONAL: 'bg-emerald-400',
    MAINTENANCE: 'bg-cyan-400',
    OFFLINE: 'bg-slate-500',
    CRITICAL: 'bg-rose-500 animate-pulse',
  };
  return <span className={`w-2 h-2 rounded-full inline-block ${map[status]}`} />;
}

// ─── Empty State ─────────────────────────────────────────────────────────────

export function EmptyState({ icon, title, desc }: { icon: ReactNode; title: string; desc: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center space-y-3">
      <div className="text-slate-600 w-12 h-12">{icon}</div>
      <p className="text-slate-400 font-medium">{title}</p>
      <p className="text-slate-500 text-sm">{desc}</p>
    </div>
  );
}

// ─── Section Header ───────────────────────────────────────────────────────────

export function SectionHeader({
  icon, title, subtitle, actions
}: {
  icon: ReactNode; title: string; subtitle?: string; actions?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-cyan-950/40 border border-cyan-800/30 text-cyan-400">
          {icon}
        </div>
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">{title}</h1>
          {subtitle && <p className="text-sm text-slate-400 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
