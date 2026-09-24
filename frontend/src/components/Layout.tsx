import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  ShieldCheck, LayoutDashboard, Server, Wrench, Cpu,
  Search, BookOpen, BarChart3, FileText, Bell,
  LogOut, Menu, X, Film, ExternalLink
} from 'lucide-react';
import { useState, useRef } from 'react';
import { useSimulation } from '../lib/simulationStore';
import type { UserRole } from '../lib/types';
import { Background3D } from './Background3D';

const NAV = [
  { to: '/dashboard',  label: 'Dashboard',           icon: LayoutDashboard },
  { to: '/machines',   label: 'Machines',             icon: Server },
  { to: '/maintenance',label: 'Maintenance',          icon: Wrench },
  { to: '/plc-integrity', label: 'PLC Integrity',     icon: Cpu },
  { to: '/changes',    label: 'Change Investigation', icon: Search },
  { to: '/logbook',    label: 'Logbook',              icon: BookOpen },
  { to: '/analytics',  label: 'Analytics',            icon: BarChart3 },
  { to: '/reports',    label: 'Reports',              icon: FileText },
  { to: '/notifications', label: 'Notifications',     icon: Bell },
];

interface SidebarProps {
  currentUser?: { name: string; role: UserRole; email: string };
  onLogout?: () => void;
}

export function Sidebar({ currentUser, onLogout }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const { notifications } = useSimulation();
  const unread = notifications.filter(n => !n.read).length;
  const navigate = useNavigate();

  const handleLogout = () => {
    if (onLogout) {
      onLogout();
    } else {
      navigate('/login');
    }
  };

  const userInitial = (currentUser?.name || 'A')[0].toUpperCase();
  const userName = currentUser?.name || 'SOC Operator';
  const userRole = currentUser?.role || 'ADMIN';

  return (
    <aside
      className={`flex flex-col bg-[#080d1a]/90 backdrop-blur-xl border-r border-slate-800/80 transition-all duration-300 ${
        collapsed ? 'w-16' : 'w-60'
      } flex-shrink-0 min-h-screen z-30`}
    >
      {/* Logo */}
      <div className="flex items-center justify-between px-3.5 py-4 border-b border-slate-800/60">
        {!collapsed && (
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-cyan-950/60 border border-cyan-500/40 text-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.2)]">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <span className="text-sm font-black tracking-widest text-white uppercase">
                Maint<span className="text-cyan-400">X</span>
              </span>
              <div className="text-[9px] font-mono text-cyan-500 tracking-widest uppercase">
                ICS/SCADA SOC
              </div>
            </div>
          </div>
        )}
        {collapsed && (
          <div className="mx-auto p-1.5 rounded-lg bg-cyan-950/60 border border-cyan-500/40 text-cyan-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
        )}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="ml-auto text-slate-500 hover:text-slate-300 p-1 rounded hover:bg-slate-800/50 transition"
          title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {collapsed ? <Menu className="w-4 h-4" /> : <X className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2.5 py-3 space-y-1 overflow-y-auto">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-mono font-medium transition-all group relative ${
                isActive
                  ? 'bg-cyan-950/60 border border-cyan-700/50 text-cyan-300 shadow-[inset_0_0_8px_rgba(6,182,212,0.15)] font-semibold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border border-transparent'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span className="relative flex-shrink-0">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400 group-hover:text-slate-200'}`} />
                  {label === 'Notifications' && unread > 0 && (
                    <span className="absolute -top-1.5 -right-1.5 w-3.5 h-3.5 rounded-full bg-rose-500 text-[8px] font-bold text-white flex items-center justify-center animate-pulse">
                      {unread}
                    </span>
                  )}
                </span>
                {!collapsed && <span className="truncate">{label}</span>}
                {collapsed && (
                  <div className="absolute left-full ml-3 px-2 py-1 bg-slate-900 border border-slate-700 rounded text-xs font-mono text-white whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-xl">
                    {label}
                  </div>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User profile & Logout */}
      <div className="border-t border-slate-800/60 p-2.5">
        <div className={`flex items-center gap-2.5 p-2 rounded-lg bg-slate-900/60 border border-slate-800/80 ${collapsed ? 'justify-center' : ''}`}>
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-600 to-indigo-600 flex items-center justify-center text-white text-xs font-bold font-mono flex-shrink-0 shadow-sm">
            {userInitial}
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold text-slate-200 truncate">{userName}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                <p className="text-[9px] text-cyan-400 font-mono tracking-wider font-semibold truncate">
                  {userRole}
                </p>
              </div>
            </div>
          )}
          {!collapsed && (
            <button
              onClick={handleLogout}
              className="text-slate-500 hover:text-rose-400 p-1 rounded hover:bg-rose-950/30 transition"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}

// ─── Top Bar ─────────────────────────────────────────────────────────────────

export function TopBar({
  title,
  currentUser
}: {
  title: string;
  currentUser?: { name: string; role: UserRole; email: string };
}) {
  const { notifications, activeSimSession, isChainTampered } = useSimulation();
  const unread = notifications.filter(n => !n.read).length;

  return (
    <header className="bg-[#090d18]/90 backdrop-blur-md border-b border-slate-800/70 px-6 py-3.5 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-bold text-white tracking-wide font-mono uppercase">
          {title}
        </h2>
        <span className="hidden md:inline-block text-[10px] font-mono text-slate-500 border-l border-slate-700 pl-3">
          SOC MODE: <span className="text-cyan-400 font-semibold">{currentUser?.role || 'ADMIN'}</span>
        </span>
      </div>

      <div className="flex items-center gap-3">
        {/* 3D Engine Status Indicator */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-cyan-950/40 border border-cyan-800/50 text-[10px] font-mono text-cyan-300">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          <span className="font-semibold tracking-wider">3D CORE ACTIVE</span>
        </div>

        {/* Live status */}
        {activeSimSession.active && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-rose-950/70 border border-rose-500/50 text-[10px] font-mono animate-pulse">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
            <span className="text-rose-300 font-bold">SIM ACTIVE: {activeSimSession.machine}</span>
          </div>
        )}

        <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-md bg-slate-900/90 border border-slate-800 text-[10px] font-mono">
          <span className={`w-2 h-2 rounded-full ${isChainTampered ? 'bg-rose-500' : 'bg-emerald-400'} animate-pulse`} />
          <span className="text-slate-400">LEDGER:</span>
          <span className={`${isChainTampered ? 'text-rose-400' : 'text-emerald-400'} font-semibold tracking-wider`}>
            {isChainTampered ? 'TAMPER DETECTED' : 'SHA-256 VALID'}
          </span>
        </div>

        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900/90 border border-slate-800 text-[10px] font-mono">
          <span className="text-slate-400">PLC GATE:</span>
          <span className="text-cyan-400 font-semibold">ENFORCED</span>
        </div>

        <NavLink
          to="/intro"
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-cyan-950/40 hover:bg-cyan-900/50 border border-cyan-800/50 hover:border-cyan-500 text-[10px] font-mono text-cyan-300 hover:text-white transition shadow-sm"
          title="Replay HackfiniX 2026 Intro Experience"
        >
          <Film className="w-3 h-3 text-cyan-400" />
          <span className="hidden sm:inline font-semibold tracking-wider">REPLAY INTRO</span>
        </NavLink>

        <a
          href="/simulator.html"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-950/40 hover:bg-emerald-900/50 border border-emerald-800/50 hover:border-emerald-500 text-[10px] font-mono text-emerald-300 hover:text-white transition shadow-sm"
          title="Open Live PLC Simulator in New Tab"
        >
          <ExternalLink className="w-3 h-3 text-emerald-400" />
          <span className="hidden sm:inline font-semibold tracking-wider">SIMULATOR TAB</span>
        </a>

        <NavLink
          to="/notifications"
          className="relative p-2 rounded-lg hover:bg-slate-800 transition text-slate-400 hover:text-slate-200 border border-transparent hover:border-slate-700"
          title="Security Notifications"
        >
          <Bell className="w-4 h-4" />
          {unread > 0 && (
            <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-rose-500 text-[8px] font-bold text-white flex items-center justify-center animate-bounce">
              {unread}
            </span>
          )}
        </NavLink>
      </div>
    </header>
  );
}

interface LayoutProps {
  children: React.ReactNode;
  currentUser?: { name: string; role: UserRole; email: string };
  onLogout?: () => void;
}

export function AppLayout({ children, currentUser, onLogout }: LayoutProps) {
  const location = useLocation();
  const mainRef = useRef<HTMLElement | null>(null);

  const getPageTitle = (path: string) => {
    if (path === '/' || path === '/dashboard' || path.startsWith('/dashboard')) return 'Security Operations Center';
    if (path.startsWith('/machines')) return 'Industrial Machine Fleet';
    if (path.startsWith('/maintenance')) return 'Maintenance Sessions & Verification Gate';
    if (path.startsWith('/plc-integrity')) return 'PLC Logic Integrity Verification';
    if (path.startsWith('/changes')) return 'Change Investigation & Risk Engine';
    if (path.startsWith('/logbook')) return 'Tamper-Evident Security Logbook';
    if (path.startsWith('/analytics')) return 'Security Analytics & Threat Posture';
    if (path.startsWith('/reports')) return 'Compliance & Certification Reports';
    if (path.startsWith('/notifications')) return 'Security Operations Notification Queue';
    return 'MaintX SOC';
  };

  return (
    <div className="relative flex min-h-screen bg-[#060913] text-slate-100 font-sans overflow-hidden">
      {/* 3D Scroll-Driven Interactive Background Canvas */}
      <Background3D scrollTargetRef={mainRef} />

      {/* Main SOC Interface */}
      <Sidebar currentUser={currentUser} onLogout={onLogout} />
      <div className="relative z-10 flex-1 flex flex-col min-w-0">
        <TopBar title={getPageTitle(location.pathname)} currentUser={currentUser} />
        <main ref={mainRef} className="flex-1 min-w-0 overflow-y-auto p-6 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
