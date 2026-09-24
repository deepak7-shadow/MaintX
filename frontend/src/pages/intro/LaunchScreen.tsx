import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';

interface Props { onNext: () => void; exiting: boolean; }

const BOOT_LINES = [
  { text: '> INITIALIZING MAINTX SECURITY CORE...', delay: 100,  color: 'text-slate-400' },
  { text: '> Loading PLC integrity verification module...', delay: 600,  color: 'text-slate-500' },
  { text: '> Connecting to maintenance accountability ledger...', delay: 1100, color: 'text-slate-500' },
  { text: '> Zero-trust policy engine: ACTIVE', delay: 1600, color: 'text-cyan-400' },
  { text: '> SHA-256 hash chain: VERIFIED ✓', delay: 2000, color: 'text-emerald-400' },
  { text: '> Cryptographic audit log: ONLINE', delay: 2400, color: 'text-emerald-400' },
  { text: '> RBAC access control: ENFORCED', delay: 2800, color: 'text-indigo-400' },
  { text: '> ALL SYSTEMS NOMINAL — LAUNCHING MAINTX', delay: 3400, color: 'text-cyan-300' },
];

export function LaunchScreen({ onNext, exiting }: Props) {
  const navigate = useNavigate();
  const [visibleLines, setVisibleLines] = useState<number[]>([]);
  const [progress, setProgress] = useState(0);
  const [done, setDone] = useState(false);

  const jumpToDashboard = () => {
    if (done) return;
    setDone(true);
    onNext();
  };

  // Reveal boot lines swiftly
  useEffect(() => {
    const timers = BOOT_LINES.map((line, i) =>
      setTimeout(() => setVisibleLines(p => [...p, i]), Math.floor(line.delay * 0.28))
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  // Snappy progress bar (reaches 100% in ~750ms)
  useEffect(() => {
    const interval = setInterval(() => {
      setProgress(p => {
        const next = p + 4;
        if (next >= 100) { clearInterval(interval); return 100; }
        return next;
      });
    }, 30);
    return () => clearInterval(interval);
  }, []);

  // Auto-navigate when done
  useEffect(() => {
    if (progress < 100) return;
    const t = setTimeout(() => {
      setDone(true);
      setTimeout(() => navigate('/dashboard', { replace: true }), 350);
    }, 200);
    return () => clearTimeout(t);
  }, [progress, navigate]);

  return (
    <div
      className="relative w-full h-full flex flex-col items-center justify-center overflow-hidden cursor-pointer"
      onClick={jumpToDashboard}
      style={{
        background: '#04060e',
        opacity: exiting || done ? 0 : 1,
        transition: 'opacity 0.6s ease',
      }}
    >
      {/* Fine scan lines */}
      <div className="absolute inset-0 pointer-events-none" style={{
        backgroundImage: 'repeating-linear-gradient(0deg, rgba(0,0,0,0.15) 0px, rgba(0,0,0,0.15) 1px, transparent 1px, transparent 4px)',
      }} />

      {/* Center glow */}
      <div className="absolute inset-0 pointer-events-none" style={{
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,240,255,0.03) 0%, transparent 60%)',
      }} />

      <div className="relative z-10 w-full max-w-xl px-8 flex flex-col items-center gap-8">

        {/* MaintX icon */}
        <div className="flex flex-col items-center gap-3">
          <div
            className="p-4 rounded-2xl border border-cyan-900/60 bg-cyan-950/30"
            style={{ boxShadow: '0 0 40px rgba(0,240,255,0.15)' }}
          >
            <ShieldCheck className="w-10 h-10 text-cyan-400" />
          </div>
          <h1 className="text-3xl font-black tracking-tight text-white">
            Maint<span className="text-cyan-400">X</span>
          </h1>
        </div>

        {/* Boot terminal */}
        <div
          className="w-full rounded-xl border border-slate-800/80 bg-slate-950/60 overflow-hidden font-mono text-xs"
          style={{ boxShadow: '0 0 30px rgba(0,0,0,0.5)' }}
        >
          {/* Terminal titlebar */}
          <div className="flex items-center gap-1.5 px-3 py-2 border-b border-slate-800 bg-slate-900/60">
            <div className="w-2.5 h-2.5 rounded-full bg-rose-500/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/70" />
            <span className="ml-2 text-[10px] text-slate-600 uppercase tracking-wider">maintx-core — system boot</span>
          </div>
          <div className="p-4 space-y-1.5 min-h-[200px]">
            {BOOT_LINES.map((line, i) => (
              <div
                key={i}
                className={`${line.color} leading-relaxed`}
                style={{
                  opacity: visibleLines.includes(i) ? 1 : 0,
                  transform: visibleLines.includes(i) ? 'none' : 'translateX(-8px)',
                  transition: 'opacity 0.4s ease, transform 0.4s ease',
                }}
              >
                {line.text}
              </div>
            ))}
            {visibleLines.length < BOOT_LINES.length && (
              <span className="text-slate-600 animate-pulse">_</span>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full flex flex-col gap-2">
          <div className="w-full h-0.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${progress}%`,
                background: 'linear-gradient(90deg, #0891b2, #4f46e5)',
                boxShadow: '0 0 8px rgba(0,240,255,0.4)',
                transition: 'width 0.05s linear',
              }}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-slate-600 uppercase tracking-wider">
              {progress < 100 ? 'INITIALIZING MAINTX...' : 'SYSTEM READY'}
            </span>
            <span className="text-[10px] font-mono text-cyan-600">{Math.round(progress)}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
