import { useEffect, useRef, useState, useCallback } from 'react';
import { Shield, Zap, Lock, Cpu, ChevronRight, Radio, Fingerprint, Terminal } from 'lucide-react';

interface Props { onNext: () => void; exiting: boolean; }

export function BrochureScreen({ onNext, exiting }: Props) {
  const [visible, setVisible] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const [tilt, setTilt] = useState({ x: 0, y: 0, px: 50, py: 50 });

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 80);
    return () => clearTimeout(t);
  }, []);

  // Smooth 3D tilt tracking
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const px = (x / rect.width) * 100;
    const py = (y / rect.height) * 100;
    const tiltX = ((y / rect.height) - 0.5) * -7;
    const tiltY = ((x / rect.width) - 0.5) * 7;
    setTilt({ x: tiltX, y: tiltY, px, py });
  }, []);

  const handleMouseLeave = useCallback(() => {
    setTilt({ x: 0, y: 0, px: 50, py: 50 });
  }, []);

  // Subtle particle grid canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let w = canvas.width = window.innerWidth;
    let h = canvas.height = window.innerHeight;

    const dots: { x: number; y: number; vx: number; vy: number; a: number }[] = [];
    for (let i = 0; i < 75; i++) {
      dots.push({ x: Math.random() * w, y: Math.random() * h, vx: (Math.random() - 0.5) * 0.25, vy: (Math.random() - 0.5) * 0.25, a: Math.random() });
    }

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      dots.forEach(d => {
        d.x += d.vx; d.y += d.vy; d.a += 0.005;
        if (d.x < 0) d.x = w; if (d.x > w) d.x = 0;
        if (d.y < 0) d.y = h; if (d.y > h) d.y = 0;
        const alpha = 0.15 + Math.sin(d.a) * 0.1;
        ctx.beginPath();
        ctx.arc(d.x, d.y, 1, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0,240,255,${alpha})`;
        ctx.fill();
      });
      // Grid lines
      ctx.strokeStyle = 'rgba(0,240,255,0.035)';
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 60) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
      for (let y = 0; y < h; y += 60) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
      animRef.current = requestAnimationFrame(draw);
    };
    draw();

    const onResize = () => { w = canvas.width = window.innerWidth; h = canvas.height = window.innerHeight; };
    window.addEventListener('resize', onResize);
    return () => { cancelAnimationFrame(animRef.current); window.removeEventListener('resize', onResize); };
  }, []);

  return (
    <div
      className="relative w-full h-full flex flex-col items-center justify-center cursor-pointer select-none overflow-hidden"
      onClick={onNext}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{
        background: 'radial-gradient(ellipse at 50% 40%, rgba(10,22,40,0.80) 0%, rgba(4,6,14,0.92) 75%)',
        opacity: exiting ? 0 : visible ? 1 : 0,
        transform: exiting ? 'scale(1.04)' : visible ? 'scale(1)' : 'scale(0.97)',
        transition: 'opacity 0.55s ease, transform 0.55s ease',
      }}
    >
      <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" />

      {/* Top cyber stripes */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan-500/60 to-transparent" />
      <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-cyan-400 to-transparent opacity-40" />

      {/* Brochure container with 3D perspective */}
      <div
        className="relative z-10 w-full max-w-5xl mx-auto px-6 flex flex-col items-center gap-0"
        style={{ perspective: 1200 }}
      >
        {/* ── 3D HOLOGRAPHIC BROCHURE CARD ── */}
        <div
          className="relative w-full max-w-[820px] rounded-2xl overflow-hidden shadow-[0_0_90px_rgba(0,240,255,0.14)] border border-cyan-800/40 transition-transform duration-200 ease-out"
          style={{
            background: 'linear-gradient(160deg, #050d1e 0%, #08132a 50%, #060913 100%)',
            transform: `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
          }}
        >
          {/* Dynamic specular sheen on mouse hover */}
          <div
            className="absolute inset-0 pointer-events-none opacity-40 transition-opacity duration-300"
            style={{
              background: `radial-gradient(circle at ${tilt.px}% ${tilt.py}%, rgba(0,240,255,0.18) 0%, rgba(99,102,241,0.06) 40%, transparent 70%)`,
            }}
          />

          {/* Cybernetic Header Band */}
          <div className="relative h-2 w-full" style={{ background: 'linear-gradient(90deg, #0e7490, #4f46e5, #00f0ff, #7c3aed, #0e7490)' }} />

          {/* Brochure Body */}
          <div className="p-8 md:p-12 flex flex-col items-center text-center gap-7">

            {/* Event badge with security classification */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3.5 py-1 rounded-full border border-cyan-800/70 bg-cyan-950/50 shadow-sm">
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                <span className="text-[10px] font-mono text-cyan-300 uppercase tracking-[0.25em] font-semibold">
                  Official Event Brochure
                </span>
              </div>
              <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full border border-indigo-900/50 bg-indigo-950/30">
                <Radio className="w-3 h-3 text-indigo-400 animate-pulse" />
                <span className="text-[10px] font-mono text-indigo-300 uppercase tracking-widest">
                  Live Defense Grid
                </span>
              </div>
            </div>

            {/* Main title */}
            <div className="flex flex-col items-center gap-2">
              <h1
                className="text-6xl md:text-7xl lg:text-8xl font-black tracking-tight"
                style={{
                  background: 'linear-gradient(135deg, #ffffff 0%, #a5f3fc 45%, #818cf8 100%)',
                  WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
                  letterSpacing: '-0.035em',
                  filter: 'drop-shadow(0 0 25px rgba(0,240,255,0.2))',
                }}
              >
                HackfiniX
              </h1>
              <div className="flex items-center gap-4">
                <div className="h-px w-14 bg-gradient-to-r from-transparent to-cyan-500/70" />
                <span className="text-2xl md:text-3xl font-mono font-bold text-cyan-400 tracking-[0.25em]">2026</span>
                <div className="h-px w-14 bg-gradient-to-l from-transparent to-cyan-500/70" />
              </div>
            </div>

            {/* Theme pill */}
            <div
              className="px-8 py-2.5 rounded-xl border border-indigo-500/40 text-xs md:text-sm font-mono font-bold uppercase tracking-[0.25em] text-indigo-300 shadow-[0_0_20px_rgba(99,102,241,0.15)]"
              style={{ background: 'linear-gradient(90deg, rgba(79,70,229,0.15) 0%, rgba(14,116,144,0.15) 100%)' }}
            >
              Industrial Cybersecurity Track
            </div>

            {/* Feature grid — 4 Industrial Cybersecurity Pillars */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5 w-full mt-1">
              {[
                { icon: Shield,      label: 'OT Security',       sub: 'ICS / SCADA Defense',   color: 'text-cyan-400',    glow: 'rgba(0,240,255,0.15)' },
                { icon: Zap,         label: 'Real-Time',         sub: 'Threat Intelligence',  color: 'text-amber-400',   glow: 'rgba(245,158,11,0.15)' },
                { icon: Lock,        label: 'Zero-Trust Gate',   sub: 'Strict Access Control', color: 'text-indigo-400',  glow: 'rgba(99,102,241,0.15)' },
                { icon: Cpu,         label: 'PLC Integrity',     sub: 'Logic Hash Proofs',     color: 'text-emerald-400', glow: 'rgba(16,185,129,0.15)' },
              ].map(({ icon: Icon, label, sub, color, glow }) => (
                <div
                  key={label}
                  className="group relative flex flex-col items-center gap-2 p-4 rounded-xl border border-slate-800/80 bg-slate-900/40 hover:border-cyan-700/60 hover:bg-slate-900/70 transition-all duration-300"
                  style={{ boxShadow: `0 0 15px ${glow}` }}
                >
                  <div className="p-2 rounded-lg bg-slate-950/70 border border-slate-800 group-hover:border-cyan-500/50 transition">
                    <Icon className={`w-4 h-4 ${color}`} />
                  </div>
                  <span className="text-xs font-bold text-white tracking-wide font-mono">{label}</span>
                  <span className="text-[10px] text-slate-400 text-center leading-tight font-mono">{sub}</span>
                </div>
              ))}
            </div>

            {/* Creative Cyber Telemetry HUD Matrix (Replaces the generic stats row) */}
            <div className="w-full rounded-xl border border-cyan-900/50 bg-[#050b17]/90 p-4 mt-1 flex flex-col gap-3">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-2.5">
                <div className="flex items-center gap-2">
                  <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                  <span className="text-[10px] font-mono text-cyan-300 uppercase tracking-widest font-semibold">
                    DEFENSE SPECIFICATION // PROTOCOL MATRIX
                  </span>
                </div>
                <div className="flex items-center gap-1.5 font-mono text-[9px] text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span>ONLINE & ARMED</span>
                </div>
              </div>

              {/* 3 Telemetry Pillars */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-left">
                <div className="flex items-start gap-2.5 p-2 rounded bg-slate-900/40 border border-slate-800/60">
                  <Fingerprint className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="text-[10px] font-mono font-bold text-slate-200">SHA-256 LEDGER</div>
                    <div className="text-[9px] font-mono text-slate-500 leading-tight">Cryptographic audit chain</div>
                  </div>
                </div>

                <div className="flex items-start gap-2.5 p-2 rounded bg-slate-900/40 border border-slate-800/60">
                  <Cpu className="w-4 h-4 text-indigo-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="text-[10px] font-mono font-bold text-slate-200">PLC LOGIC GATE</div>
                    <div className="text-[9px] font-mono text-slate-500 leading-tight">Zero-drift verification</div>
                  </div>
                </div>

                <div className="flex items-start gap-2.5 p-2 rounded bg-slate-900/40 border border-slate-800/60">
                  <Shield className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="text-[10px] font-mono font-bold text-slate-200">AIR-GAP SECURITY</div>
                    <div className="text-[9px] font-mono text-slate-500 leading-tight">Zero-trust session locks</div>
                  </div>
                </div>
              </div>

              {/* Live hex data stream ticker */}
              <div className="flex items-center justify-between text-[9px] font-mono text-slate-500 pt-1 border-t border-slate-800/50">
                <span className="text-cyan-600 truncate">SYS_KEY: 0x7F49A2B · ICS-62443 · ENFORCED</span>
                <span className="text-slate-600 hidden sm:inline">TAMPER-EVIDENT ARCHITECTURE</span>
                <span className="text-emerald-500 font-semibold">STATUS: NOMINAL</span>
              </div>
            </div>

            {/* Tagline */}
            <div className="flex flex-col items-center gap-1">
              <p className="text-slate-300 text-xs md:text-sm font-mono tracking-wide">
                Hack · Defend · Innovate · Secure
              </p>
              <p className="text-[10px] text-slate-500 font-mono uppercase tracking-[0.2em]">
                Protecting Critical Industrial Infrastructure Through Innovation
              </p>
            </div>
          </div>

          {/* Brochure Footer Band */}
          <div className="px-8 py-3.5 border-t border-slate-800/70 flex items-center justify-between bg-slate-950/80">
            <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">
              HackfiniX 2026 · Industrial Cybersecurity
            </span>
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-mono text-emerald-400 font-semibold tracking-wider">LIVE CHALLENGE</span>
            </div>
          </div>
        </div>
      </div>

      {/* Modern Glowing CTA Button */}
      <div
        className="absolute bottom-8 left-0 right-0 flex flex-col items-center gap-2"
        style={{ opacity: visible ? 1 : 0, transition: 'opacity 1s ease 1s' }}
      >
        <div className="group px-6 py-2 rounded-full border border-cyan-500/50 bg-cyan-950/50 hover:bg-cyan-900/60 text-cyan-300 hover:text-white transition-all duration-300 shadow-[0_0_20px_rgba(0,240,255,0.25)] flex items-center gap-3">
          <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
          <span className="text-[11px] font-mono uppercase tracking-[0.25em] font-bold">
            Click to Enter Experience
          </span>
          <ChevronRight className="w-3.5 h-3.5 text-cyan-400 group-hover:translate-x-0.5 transition-transform" />
        </div>
        <span className="text-[9px] font-mono text-slate-600 uppercase tracking-widest">
          or press [ Enter / Space ]
        </span>
      </div>
    </div>
  );
}
