import { useEffect, useState } from 'react';
import { 
  ShieldCheck, 
  Cpu, 
  AlertTriangle, 
  Lock, 
  CheckCircle2, 
  Terminal,
  RefreshCw,
  Server
} from 'lucide-react';

interface HealthStatus {
  status: string;
  service: string;
  version: string;
  environment: string;
  timestamp: string;
  security_integrity: string;
}

export function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await fetch(`${apiUrl}/health`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      setHealth(data);
    } catch (err: any) {
      setError(err.message || 'Failed to connect to MaintX backend API');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <div className="min-h-screen bg-[#0b0f19] text-slate-100 flex flex-col font-sans">
      {/* Top Industrial SOC Header */}
      <header className="border-b border-slate-800 bg-[#0f1524]/90 backdrop-blur px-6 py-4 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded bg-cyan-950/60 border border-cyan-500/40 text-cyan-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-wider uppercase text-white">MaintX</h1>
              <span className="px-2 py-0.5 text-[10px] font-mono tracking-widest uppercase rounded bg-cyan-900/40 border border-cyan-600/30 text-cyan-300">
                INDUSTRIAL SOC
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono">PLC Logic Integrity & Maintenance Accountability Platform</p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 px-3 py-1.5 rounded bg-slate-900/80 border border-slate-800 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="text-slate-300">INTEGRITY:</span>
            <span className="text-emerald-400 font-semibold">TAMPER-EVIDENT</span>
          </div>

          <button 
            onClick={checkHealth}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 transition border border-slate-700"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Check Backend</span>
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8 space-y-8">
        {/* Banner / Stage 1 Status */}
        <section className="bg-gradient-to-r from-[#121a2f] via-[#101827] to-[#121a2f] border border-cyan-900/40 rounded-xl p-6 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none">
            <Cpu className="w-48 h-48 text-cyan-400" />
          </div>

          <div className="max-w-2xl relative z-10 space-y-3">
            <div className="inline-flex items-center space-x-2 px-2.5 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>STAGE 1 OPERATIONAL FOUNDATION</span>
            </div>
            <h2 className="text-2xl font-bold text-white tracking-tight">
              Industrial Machine Logic Security Engine
            </h2>
            <p className="text-sm text-slate-300 leading-relaxed font-sans">
              MaintX continuously models trusted machine baselines, detects unauthorized PLC modifications,
              calculates deterministic risk scores, and anchors immutable maintenance audits in a tamper-evident hash chain.
            </p>
          </div>
        </section>

        {/* System Architecture Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: Backend Connection */}
          <div className="bg-[#101726] border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Backend API</span>
                <Server className="w-4 h-4 text-cyan-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">FastAPI Core Runtime</h3>
              <p className="text-xs text-slate-400">
                Pydantic validation, deterministic risk engine, PLC canonicalization, and SHA-256 hash chaining.
              </p>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800/80 font-mono text-xs">
              {loading ? (
                <div className="flex items-center space-x-2 text-slate-400">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Probing /health endpoint...</span>
                </div>
              ) : error ? (
                <div className="flex items-center space-x-2 text-amber-400">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">Backend offline ({error})</span>
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-emerald-400">
                    <span className="flex items-center space-x-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>ONLINE</span>
                    </span>
                    <span className="text-slate-400">v{health?.version}</span>
                  </div>
                  <div className="text-[11px] text-slate-400 truncate">
                    Security: <span className="text-cyan-300">{health?.security_integrity}</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Card 2: PLC Simulator */}
          <div className="bg-[#101726] border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Logic Integrity</span>
                <Cpu className="w-4 h-4 text-emerald-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">Software PLC Simulator</h3>
              <p className="text-xs text-slate-400">
                Simulated Ladder/Structured text logic parser with canonical key ordering, SHA-256 hashing, and AST-level semantic diffing.
              </p>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800/80 font-mono text-xs flex items-center justify-between text-slate-300">
              <span>CANONICAL HASH</span>
              <span className="text-emerald-400">READY</span>
            </div>
          </div>

          {/* Card 3: Audit Hash Chain */}
          <div className="bg-[#101726] border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Cryptographic Proof</span>
                <Lock className="w-4 h-4 text-amber-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">Tamper-Evident Ledger</h3>
              <p className="text-xs text-slate-400">
                Every maintenance event links forward from a genesis hash. Any alteration in PostgreSQL flags immediate compromise.
              </p>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800/80 font-mono text-xs flex items-center justify-between text-slate-300">
              <span>CHAIN INTEGRITY</span>
              <span className="text-cyan-400">ACTIVE</span>
            </div>
          </div>
        </div>

        {/* Workflow Pipeline */}
        <section className="bg-[#0f1524] border border-slate-800 rounded-lg p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <Terminal className="w-4 h-4 text-cyan-400" />
              <h3 className="text-sm font-semibold text-white tracking-wide uppercase font-mono">
                Mandatory Security Pipeline
              </h3>
            </div>
            <span className="text-xs text-slate-400 font-mono">Zero Trust Maintenance Architecture</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-8 gap-2 pt-2 text-center text-xs font-mono">
            {[
              { step: '01', name: 'PLAN', color: 'border-cyan-500/50 bg-cyan-950/20 text-cyan-300' },
              { step: '02', name: 'BASELINE', color: 'border-blue-500/50 bg-blue-950/20 text-blue-300' },
              { step: '03', name: 'WATCH', color: 'border-indigo-500/50 bg-indigo-950/20 text-indigo-300' },
              { step: '04', name: 'COMPARE', color: 'border-purple-500/50 bg-purple-950/20 text-purple-300' },
              { step: '05', name: 'AUTHORIZE', color: 'border-amber-500/50 bg-amber-950/20 text-amber-300' },
              { step: '06', name: 'RISK', color: 'border-rose-500/50 bg-rose-950/20 text-rose-300' },
              { step: '07', name: 'VERIFY', color: 'border-emerald-500/50 bg-emerald-950/20 text-emerald-300' },
              { step: '08', name: 'LOG', color: 'border-slate-500/50 bg-slate-900 text-slate-300' },
            ].map((item, idx) => (
              <div key={idx} className={`p-3 rounded border ${item.color} flex flex-col justify-center items-center`}>
                <span className="text-[10px] text-slate-500">{item.step}</span>
                <span className="font-bold tracking-wider mt-1">{item.name}</span>
              </div>
            ))}
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-[#0d121f] px-6 py-4 text-xs font-mono text-slate-500 flex flex-col md:flex-row items-center justify-between">
        <div>MaintX Security Platform &bull; Industrial Cybersecurity Hackathon</div>
        <div className="text-slate-400 mt-2 md:mt-0">
          Architecture: <span className="text-cyan-400">Untrusted Frontend / Authoritative Backend & PostgreSQL RLS</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
