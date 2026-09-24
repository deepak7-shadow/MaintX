import { useEffect, useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react';

interface Props { onNext: () => void; exiting: boolean; }

type Phase = 0 | 1 | 2 | 3 | 4;

export function HackathonScreen({ onNext, exiting }: Props) {
  const [phase, setPhase] = useState<Phase>(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);

  // Sequential reveal phases
  useEffect(() => {
    const timers = [
      setTimeout(() => setPhase(1), 200),   // HackfiniX 2026
      setTimeout(() => setPhase(2), 1000),  // INDUSTRIAL CYBERSECURITY
      setTimeout(() => setPhase(3), 1900),  // VRAZAN
      setTimeout(() => setPhase(4), 2900),  // CTA
    ];
    return () => timers.forEach(clearTimeout);
  }, []);

  // Subtle radar/scan canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    let t = 0;

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const cx = canvas.width / 2, cy = canvas.height / 2;

      // Concentric rings
      for (let r = 80; r < 600; r += 100) {
        const alpha = 0.05 - r * 0.00005;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(0,240,255,${Math.max(0, alpha)})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Radar sweep
      const sweep = (t * 0.4) % (Math.PI * 2);
      const sweepGrad = ctx.createLinearGradient(cx, cy, cx + Math.cos(sweep) * 500, cy + Math.sin(sweep) * 500);
      sweepGrad.addColorStop(0, 'rgba(0,240,255,0.12)');
      sweepGrad.addColorStop(1, 'rgba(0,240,255,0)');
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, 500, sweep - 0.5, sweep);
      ctx.closePath();
      ctx.fillStyle = sweepGrad;
      ctx.fill();

      // Horizontal scanlines
      for (let y = 0; y < canvas.height; y += 4) {
        ctx.fillStyle = `rgba(0,0,0,0.03)`;
        ctx.fillRect(0, y, canvas.width, 1);
      }

      t += 0.016;
      animRef.current = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animRef.current);
  }, []);

  const fadeIn = (show: boolean, delay = 0) => ({
    opacity: show ? 1 : 0,
    transform: show ? 'translateY(0) scale(1)' : 'translateY(24px) scale(0.96)',
    transition: `opacity 0.7s ease ${delay}ms, transform 0.7s ease ${delay}ms`,
  });

  return (
    <div
      className="relative w-full h-full flex flex-col items-center justify-center cursor-pointer overflow-hidden"
      onClick={onNext}
      style={{
        background: 'radial-gradient(ellipse at 50% 50%, rgba(8,15,32,0.80) 0%, rgba(4,6,14,0.90) 100%)',
        opacity: exiting ? 0 : 1,
        transition: 'opacity 0.55s ease',
      }}
    >
      <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none opacity-70" />

      {/* Grid overlay */}
      <div className="absolute inset-0 pointer-events-none" style={{
        backgroundImage: 'linear-gradient(rgba(0,240,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,240,255,0.03) 1px, transparent 1px)',
        backgroundSize: '60px 60px',
      }} />

      {/* Top/bottom edge glow */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan-500/50 to-transparent" />
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-indigo-500/30 to-transparent" />

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center text-center gap-6 px-8 max-w-3xl">

        {/* HackfiniX 2026 */}
        <div style={fadeIn(phase >= 1)}>
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-slate-700/60 bg-slate-900/40 mb-3">
            <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-[0.25em]">HackfiniX 2026</span>
          </div>
        </div>

        {/* INDUSTRIAL CYBERSECURITY */}
        <div style={fadeIn(phase >= 2, 0)}>
          <h1
            className="text-5xl md:text-6xl lg:text-7xl font-black uppercase tracking-tight leading-none"
            style={{
              background: 'linear-gradient(135deg, #e2e8f0 0%, #67e8f9 40%, #a5b4fc 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              letterSpacing: '-0.02em',
              textShadow: 'none',
            }}
          >
            Industrial
            <br />
            Cybersecurity
          </h1>
        </div>

        {/* Separator */}
        <div style={fadeIn(phase >= 2, 100)}>
          <div className="flex items-center gap-4">
            <div className="h-px w-16 bg-gradient-to-r from-transparent to-cyan-500/50" />
            <div className="flex gap-1">
              {[0,1,2].map(i => <div key={i} className="w-1 h-1 rounded-full bg-cyan-500/60" />)}
            </div>
            <div className="h-px w-16 bg-gradient-to-l from-transparent to-cyan-500/50" />
          </div>
        </div>

        {/* VRAZAN */}
        <div style={fadeIn(phase >= 3, 0)}>
          <div className="flex flex-col items-center gap-2">
            <span className="text-[11px] font-mono text-slate-500 uppercase tracking-[0.35em]">Team</span>
            <h2
              className="text-5xl md:text-6xl font-black uppercase tracking-[0.12em]"
              style={{
                background: 'linear-gradient(90deg, #22d3ee 0%, #818cf8 50%, #22d3ee 100%)',
                backgroundSize: '200% auto',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
                animation: 'gradientShift 3s linear infinite',
              }}
            >
              VRAZAN
            </h2>
            <div className="flex items-center gap-1.5">
              <div className="h-px w-8 bg-indigo-500/40" />
              <span className="text-[10px] font-mono text-indigo-400/60 uppercase tracking-widest">Industrial Cybersecurity Division</span>
              <div className="h-px w-8 bg-indigo-500/40" />
            </div>
          </div>
        </div>
      </div>

      {/* CTA */}
      <div
        className="absolute bottom-10 left-0 right-0 flex flex-col items-center gap-2"
        style={{ opacity: phase >= 4 ? 1 : 0, transition: 'opacity 0.8s ease' }}
      >
        <div className="flex items-center gap-2">
          <div className="h-px w-8 bg-slate-700" />
          <span className="text-[11px] font-mono uppercase tracking-[0.3em] text-slate-500">Click to Continue</span>
          <div className="h-px w-8 bg-slate-700" />
        </div>
        <div className="flex items-center gap-1 text-[10px] font-mono text-slate-700 uppercase tracking-widest">
          <ChevronRight className="w-3 h-3" /> Press Enter
        </div>
      </div>

      <style>{`
        @keyframes gradientShift {
          0%   { background-position: 0% center; }
          100% { background-position: 200% center; }
        }
      `}</style>
    </div>
  );
}
