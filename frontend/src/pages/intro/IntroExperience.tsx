import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { BrochureScreen } from './BrochureScreen';
import { HackathonScreen } from './HackathonScreen';
import { ProjectScreen } from './ProjectScreen';
import { LaunchScreen } from './LaunchScreen';
import { Background3D } from '../../components/Background3D';

export type IntroScreen = 'brochure' | 'hackathon' | 'project' | 'launch';
const SCREEN_ORDER: IntroScreen[] = ['brochure', 'hackathon', 'project', 'launch'];

export function IntroExperience() {
  const [screen, setScreen] = useState<IntroScreen>('brochure');
  const [exiting, setExiting] = useState(false);
  const navigate = useNavigate();
  const lockRef = useRef(false);

  const next = useCallback(() => {
    if (lockRef.current) return;
    lockRef.current = true;
    const idx = SCREEN_ORDER.indexOf(screen);
    if (idx < SCREEN_ORDER.length - 1) {
      setExiting(true);
      setTimeout(() => {
        setScreen(SCREEN_ORDER[idx + 1]);
        setExiting(false);
        lockRef.current = false;
      }, 560);
    } else {
      // last screen is LaunchScreen — it auto-navigates, but support manual too
      setExiting(true);
      setTimeout(() => { navigate('/dashboard', { replace: true }); }, 500);
    }
  }, [screen, navigate]);

  const skipToDashboard = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate('/dashboard', { replace: true });
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        next();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [next]);

  const currentIdx = SCREEN_ORDER.indexOf(screen);
  const sp = { onNext: next, exiting };

  return (
    <div className="fixed inset-0 bg-[#04060e] overflow-hidden select-none" style={{ zIndex: 9999 }}>
      {/* 3D Cybernetic Space */}
      <Background3D />

      {/* Top Bar Indicators & Skip Option */}
      <div className="absolute top-4 left-6 right-6 z-50 flex items-center justify-between pointer-events-auto">
        <div className="flex items-center gap-2">
          {SCREEN_ORDER.map((s, i) => (
            <div
              key={s}
              className={`h-1 rounded-full transition-all duration-500 ${
                i === currentIdx
                  ? 'w-8 bg-cyan-400 shadow-[0_0_10px_rgba(0,240,255,0.8)]'
                  : i < currentIdx
                  ? 'w-4 bg-cyan-800/60'
                  : 'w-2 bg-slate-800/80'
              }`}
            />
          ))}
          <span className="ml-2 text-[10px] font-mono text-slate-500 uppercase tracking-widest hidden sm:inline">
            Phase 0{currentIdx + 1} / 04
          </span>
        </div>

        <button
          onClick={skipToDashboard}
          className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-400 hover:text-cyan-300 px-3 py-1 rounded border border-slate-800/80 hover:border-cyan-800/80 bg-slate-950/60 transition shadow-sm"
        >
          Skip to App ⟶
        </button>
      </div>

      {/* Active Screen */}
      <div className="relative z-10 w-full h-full">
        {screen === 'brochure'  && <BrochureScreen  {...sp} />}
        {screen === 'hackathon' && <HackathonScreen {...sp} />}
        {screen === 'project'   && <ProjectScreen   {...sp} />}
        {screen === 'launch'    && <LaunchScreen    {...sp} />}
      </div>
    </div>
  );
}

