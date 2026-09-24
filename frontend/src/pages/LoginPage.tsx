import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldCheck, Lock, User, Key, ArrowRight,
  CheckCircle2
} from 'lucide-react';
import { Card } from '../components/ui';
import { Background3D } from '../components/Background3D';
import type { UserRole } from '../lib/types';

interface LoginPageProps {
  onLogin: (user: { name: string; role: UserRole; email: string }) => void;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const navigate = useNavigate();
  const [email, setEmail] = useState('admin@maintx.internal');
  const [password, setPassword] = useState('••••••••••••');
  const [role, setRole] = useState<UserRole>('ADMIN');
  const [authenticating, setAuthenticating] = useState(false);
  const [mfaCode, setMfaCode] = useState('948210');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setAuthenticating(true);

    setTimeout(() => {
      setAuthenticating(false);
      onLogin({
        name: role === 'ADMIN' ? 'SOC Lead Controller' : role === 'SUPERVISOR' ? 'Supervisor S. Patel' : 'Engineer T. Rodriguez',
        role,
        email: email || `${role.toLowerCase()}@maintx.internal`,
      });
      navigate('/dashboard');
    }, 600);
  };

  const quickRoles: { role: UserRole; name: string; desc: string }[] = [
    { role: 'ADMIN', name: 'SOC Lead Controller', desc: 'Full root access, ledger verification, policy gate overrides' },
    { role: 'SUPERVISOR', name: 'Supervisor S. Patel', desc: 'Work order approvals, verification sign-offs, change reviews' },
    { role: 'MAINTENANCE_ENGINEER', name: 'Eng. T. Rodriguez', desc: 'Physical maintenance sessions, PLC logic deployments' },
    { role: 'SECURITY_ANALYST', name: 'Analyst K. Jensen', desc: 'Change investigation, anomaly review, threat mitigation' },
    { role: 'AUDITOR', name: 'Lead Auditor V. Chen', desc: 'Read-only compliance verification & cryptographic log validation' },
  ];

  return (
    <div className="min-h-screen bg-[#060913] text-slate-100 flex flex-col justify-center items-center p-4 relative overflow-hidden">
      {/* 3D Background */}
      <Background3D />
      <div className="absolute top-0 w-full h-1 bg-gradient-to-r from-cyan-500 via-indigo-500 to-rose-500 z-10" />

      {/* Main card */}
      <div className="w-full max-w-md relative z-10">
        <div className="flex flex-col items-center mb-6">
          <div className="p-3 rounded-2xl bg-cyan-950/60 border border-cyan-500/40 text-cyan-400 shadow-[0_0_25px_rgba(6,182,212,0.25)] mb-3">
            <ShieldCheck className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-black tracking-widest text-white uppercase">
            Maint<span className="text-cyan-400">X</span>
          </h1>
          <p className="text-xs font-mono text-cyan-500 uppercase tracking-widest mt-1">
            Zero-Trust Industrial Cybersecurity Platform
          </p>
        </div>

        <Card className="p-6 bg-[#0a0f1d]/90 backdrop-blur-md border-slate-800 shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-5">
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-mono text-slate-300 font-bold uppercase tracking-wider">
                Authoritative Portal
              </span>
            </div>
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800/40 px-2 py-0.5 rounded">
              ENCRYPTED: TLS 1.3
            </span>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1">
                Security Identity / Email
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
                <input
                  type="text"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-xs font-mono text-white focus:outline-none focus:border-cyan-600 transition"
                  placeholder="operator@plant.internal"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1">
                Cryptographic Key / Password
              </label>
              <div className="relative">
                <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-xs font-mono text-white focus:outline-none focus:border-cyan-600 transition"
                  placeholder="••••••••••••"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1">
                Active Operational Role (RBAC)
              </label>
              <select
                value={role}
                onChange={e => setRole(e.target.value as UserRole)}
                className="w-full px-3 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-xs font-mono text-cyan-300 focus:outline-none focus:border-cyan-600 transition"
              >
                <option value="ADMIN">ADMIN — Security Administrator</option>
                <option value="SUPERVISOR">SUPERVISOR — Maintenance Supervisor</option>
                <option value="MAINTENANCE_ENGINEER">MAINTENANCE_ENGINEER — Field Engineer</option>
                <option value="SECURITY_ANALYST">SECURITY_ANALYST — Incident Response</option>
                <option value="AUDITOR">AUDITOR — Compliance & Hash Ledger</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1">
                Hardware Token / TOTP Token
              </label>
              <input
                type="text"
                value={mfaCode}
                onChange={e => setMfaCode(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950/80 border border-slate-800 rounded-lg text-xs font-mono text-emerald-400 focus:outline-none focus:border-cyan-600 transition tracking-widest"
                placeholder="6-digit MFA Code"
              />
            </div>

            <button
              type="submit"
              disabled={authenticating}
              className="w-full py-2.5 mt-2 rounded-lg bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white text-xs font-mono font-bold uppercase tracking-wider transition flex items-center justify-center gap-2 shadow-lg shadow-cyan-900/30 disabled:opacity-50"
            >
              {authenticating ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                  <span>Verifying Credentials…</span>
                </>
              ) : (
                <>
                  <span>Authenticate & Enter SOC</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Personas */}
          <div className="mt-6 pt-5 border-t border-slate-800/80">
            <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider block mb-2">
              Quick Demo Personas (Instant Access)
            </span>
            <div className="grid grid-cols-1 gap-1.5">
              {quickRoles.map(p => (
                <button
                  key={p.role}
                  type="button"
                  onClick={() => {
                    setRole(p.role);
                    setEmail(`${p.role.toLowerCase()}@maintx.internal`);
                  }}
                  className={`text-left p-2 rounded border text-xs font-mono transition flex items-center justify-between ${
                    role === p.role
                      ? 'bg-cyan-950/50 border-cyan-600/50 text-cyan-300'
                      : 'bg-slate-900/40 border-slate-800/70 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                  }`}
                >
                  <div className="truncate mr-2">
                    <span className="font-bold">{p.role}</span>
                    <span className="text-[10px] text-slate-500 ml-2 block truncate">{p.desc}</span>
                  </div>
                  {role === p.role && <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />}
                </button>
              ))}
            </div>
          </div>
        </Card>

        {/* Security watermark */}
        <div className="flex items-center justify-between text-[10px] font-mono text-slate-600 mt-4 px-2">
          <span>SHA-256 Ledger Node: ACTIVE</span>
          <span>Zero-Trust v2.4</span>
        </div>
      </div>
    </div>
  );
}
