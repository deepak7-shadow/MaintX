import { useEffect, useRef, useState } from 'react';
import { ShieldCheck, Activity, Lock, FileSearch, ChevronRight } from 'lucide-react';

interface Props { onNext: () => void; exiting: boolean; }

type Phase = 0 | 1 | 2 | 3 | 4 | 5;

const STATUS_ITEMS = [
  { icon: Activity,    label: 'SYSTEM INITIALIZING',   color: 'text-cyan-400',    delay: 1900 },
  { icon: ShieldCheck, label: 'PLC INTEGRITY',          color: 'text-emerald-400', delay: 2200 },
  { icon: Lock,        label: 'MAINTENANCE SECURITY',   color: 'text-indigo-400',  delay: 2500 },
  { icon: FileSearch,  label: 'AUDIT MONITORING',       color: 'text-amber-400',   delay: 2800 },
];

export function ProjectScreen({ onNext, exiting }: Props) {
  const [phase, setPhase] = useState<Phase>(0);
  const [statusVisible, setStatusVisible] = useState<boolean[]>([false, false, false, false]);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const [typedTagline, setTypedTagline] = useState('');

  const tagline = `"Know what changed.\nKnow who changed it.\nProve whether it was authorized."`;

  // Phase sequence
  useEffect(() => {
    const timers = [
      setTimeout(() => setPhase(1), 200),   // "VRAZAN PRESENTS"
      setTimeout(() => setPhase(2), 700),   // MaintX title
      setTimeout(() => setPhase(3), 1200),  // subtitle
      setTimeout(() => setPhase(4), 1600),  // tagline typing
      setTimeout(() => setPhase(5), 3200),  // ENTER MAINTX
    ];
    return () => timers.forEach(clearTimeout);
  }, []);

  // Typewriter for tagline
  useEffect(() => {
    if (phase < 4) return;
    let i = 0;
    const interval = setInterval(() => {
      setTypedTagline(tagline.slice(0, i + 1));
      i++;
      if (i >= tagline.length) clearInterval(interval);
    }, 18);
    return () => clearInterval(interval);
  }, [phase]);

  // Status items staggered appearance
  useEffect(() => {
    const timers = STATUS_ITEMS.map((item, idx) =>
      setTimeout(() => {
        setStatusVisible(prev => {
          const next = [...prev];
          next[idx] = true;
          return next;
        });
      }, item.delay)
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  // Subtle hexagonal grid canvas
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
      // Flowing data lines
      for (let i = 0; i < 6; i++) {
        const x = (i / 5) * canvas.width;
        const alpha = 0.04 + Math.sin(t * 0.5 + i) * 0.02;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.strokeStyle = `rgba(0,240,255,${Math.max(0, alpha)})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      // Moving horizontal data stream
      const streamY = (canvas.height * 0.6 + Math.sin(t * 0.3) * 40);
      const grd = ctx.createLinearGradient(0, streamY - 1, canvas.width, streamY + 1);
      grd.addColorStop(0, 'rgba(0,240,255,0)');
      grd.addColorStop(0.3 + Math.sin(t * 0.4) * 0.2, 'rgba(0,240,255,0.08)');
      grd.addColorStop(1, 'rgba(0,240,255,0)');
      ctx.fillStyle = grd;
      ctx.fillRect(0, streamY - 1, canvas.width, 2);
      t += 0.016;
      animRef.current = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animRef.current);
  }, []);

  const fi = (show: boolean, y = 20) => ({
    opacity: show ? 1 : 0,
    transform: show ? 'translateY(0)' : `translateY(${y}px)`,
    transition: 'opacity 0.7s ease, transform 0.7s ease',
  });

  return (
    <div
      className="relative w-full h-full min-h-screen flex flex-col items-center justify-center cursor-pointer overflow-y-auto py-10 px-4"
      onClick={onNext}
      style={{
        background: 'radial-gradient(ellipse at 50% 45%, rgba(8,13,31,0.80) 0%, rgba(4,6,14,0.90) 80%)',
        opacity: exiting ? 0 : 1,
        transform: exiting ? 'scale(0.97)' : 'scale(1)',
        transition: 'opacity 0.55s ease, transform 0.55s ease',
      }}
    >
      <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" />

      {/* Fine grid */}
      <div className="absolute inset-0 pointer-events-none" style={{
        backgroundImage: 'linear-gradient(rgba(0,240,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(0,240,255,0.025) 1px, transparent 1px)',
        backgroundSize: '40px 40px',
      }} />

      {/* Center glow */}
      <div className="absolute inset-0 pointer-events-none" style={{
        background: 'radial-gradient(ellipse at 50% 50%, rgba(0,240,255,0.04) 0%, transparent 60%)',
      }} />

      <div className="relative z-10 flex flex-col items-center text-center gap-3.5 px-4 max-w-2xl w-full my-auto">

        {/* VRAZAN PRESENTS */}
        <div style={fi(phase >= 1)}>
          <div className="inline-flex items-center gap-2 px-4 py-1 rounded-full border border-slate-800 bg-slate-900/40">
            <div className="w-1 h-1 rounded-full bg-cyan-500" />
            <span className="text-[11px] font-mono text-slate-500 uppercase tracking-[0.3em]">VRAZAN Presents</span>
          </div>
        </div>

        {/* MaintX */}
        <div style={fi(phase >= 2, 30)}>
          <div className="flex flex-col items-center gap-1">
            <h1
              className="text-6xl md:text-7xl lg:text-8xl font-black tracking-tight"
              style={{
                background: 'linear-gradient(135deg, #ffffff 0%, #67e8f9 35%, #818cf8 70%, #ffffff 100%)',
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
                letterSpacing: '-0.04em',
                filter: 'drop-shadow(0 0 40px rgba(0,240,255,0.25))',
              }}
            >
              Maint<span style={{ WebkitTextFillColor: '#22d3ee' }}>X</span>
            </h1>
            {/* Glow underline */}
            <div className="h-px w-32 mt-1" style={{
              background: 'linear-gradient(90deg, transparent, rgba(0,240,255,0.7), transparent)',
              boxShadow: '0 0 12px rgba(0,240,255,0.5)',
            }} />
          </div>
        </div>

        {/* Subtitle */}
        <div style={fi(phase >= 3)}>
          <p className="text-xs md:text-sm font-mono text-slate-400 leading-relaxed max-w-md">
            PLC Logic Integrity &amp;<br />
            <span className="text-slate-300">Maintenance Accountability Platform</span>
          </p>
        </div>

        {/* Tagline */}
        <div style={fi(phase >= 4)} className="min-h-[54px]">
          <p className="text-xs md:text-sm font-mono text-cyan-300/80 leading-relaxed whitespace-pre-line text-left border-l-2 border-cyan-800/60 pl-4 italic">
            {typedTagline}
            {phase >= 4 && typedTagline.length < tagline.length && (
              <span className="animate-pulse">_</span>
            )}
          </p>
        </div>

        {/* Status indicators */}
        <div className="grid grid-cols-2 gap-2 w-full max-w-md mt-1">
          {STATUS_ITEMS.map(({ icon: Icon, label, color }, i) => (
            <div
              key={label}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-800/60 bg-slate-900/30"
              style={{
                opacity: statusVisible[i] ? 1 : 0,
                transform: statusVisible[i] ? 'translateX(0)' : 'translateX(-12px)',
                transition: 'opacity 0.5s ease, transform 0.5s ease',
              }}
            >
              <div className={`${color} animate-pulse-slow`}>
                <Icon className="w-3.5 h-3.5" />
              </div>
              <span className={`text-[10px] font-mono font-bold uppercase tracking-wider ${color}`}>{label}</span>
            </div>
          ))}
        </div>

        {/* ENTER MAINTX CTA — in flow, cleanly below status indicators */}
        <div
          className="flex flex-col items-center gap-2 mt-4"
          style={{ opacity: phase >= 5 ? 1 : 0, transition: 'opacity 0.8s ease' }}
        >
          <div
            className="px-8 py-2.5 rounded-full border border-cyan-500/50 bg-cyan-950/60 text-cyan-300 text-xs font-mono font-bold uppercase tracking-[0.25em] cursor-pointer hover:bg-cyan-900/60 hover:border-cyan-400 transition shadow-[0_0_20px_rgba(0,240,255,0.2)]"
          >
            ⟶ Enter MaintX
          </div>
          <div className="flex items-center gap-1 text-[10px] font-mono text-slate-500 uppercase tracking-widest">
            <ChevronRight className="w-3 h-3 text-cyan-400" /> Click or Press Enter
          </div>
        </div>

      </div>
    </div>
  );
}
