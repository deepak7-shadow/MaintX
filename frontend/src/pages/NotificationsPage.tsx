import { useState } from 'react';
import {
  Bell, AlertOctagon, AlertTriangle, Info, CheckCircle2,
  Check, Trash2, Filter, ExternalLink, ShieldAlert
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { NOTIFICATIONS as INITIAL_NOTIFICATIONS } from '../lib/mockData';
import { Card, SectionHeader } from '../components/ui';
import type { Notification } from '../lib/types';

export function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>(INITIAL_NOTIFICATIONS);
  const [filter, setFilter] = useState<'ALL' | 'CRITICAL' | 'WARNING' | 'INFO' | 'SUCCESS'>('ALL');

  const filtered = notifications.filter(n => filter === 'ALL' || n.type === filter);
  const unreadCount = notifications.filter(n => !n.read).length;

  const markAsRead = (id: string) => {
    setNotifications(prev =>
      prev.map(n => (n.id === id ? { ...n, read: true } : n))
    );
  };

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  };

  const clearAll = () => {
    setNotifications([]);
  };

  const triggerSimulatedAlert = () => {
    const newAlert: Notification = {
      id: `notif-${Date.now()}`,
      type: 'CRITICAL',
      title: 'Real-Time Interlock Tripped — CNC-01',
      message: 'Hardware E-stop circuit feedback mismatch detected on CNC-01 spindle interlock. Safety gateway locked.',
      machine_code: 'CNC-01',
      timestamp: new Date().toISOString(),
      read: false,
    };
    setNotifications(prev => [newAlert, ...prev]);
  };

  const getIcon = (type: Notification['type']) => {
    switch (type) {
      case 'CRITICAL':
        return <AlertOctagon className="w-4 h-4 text-rose-400 animate-pulse" />;
      case 'WARNING':
        return <AlertTriangle className="w-4 h-4 text-amber-400" />;
      case 'SUCCESS':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'INFO':
        return <Info className="w-4 h-4 text-cyan-400" />;
    }
  };

  const getBorderColor = (type: Notification['type'], read: boolean) => {
    if (read) return 'border-slate-800/80 bg-slate-950/40 opacity-75';
    switch (type) {
      case 'CRITICAL':
        return 'border-rose-700/60 bg-rose-950/20 shadow-[0_0_15px_rgba(244,63,94,0.1)]';
      case 'WARNING':
        return 'border-amber-700/50 bg-amber-950/15';
      case 'SUCCESS':
        return 'border-emerald-700/40 bg-emerald-950/10';
      case 'INFO':
        return 'border-cyan-700/40 bg-cyan-950/10';
    }
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<Bell className="w-5 h-5" />}
        title="Security Operations Notifications"
        subtitle={`${unreadCount} unacknowledged alert${unreadCount === 1 ? '' : 's'} in queue`}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={triggerSimulatedAlert}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-950/60 border border-rose-700/50 text-rose-300 text-xs font-mono hover:bg-rose-900/60 transition"
            >
              <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
              <span>Simulate Critical Event</span>
            </button>
            {unreadCount > 0 && (
              <button
                onClick={markAllAsRead}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 text-xs font-mono hover:bg-slate-700 transition"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Mark All Read</span>
              </button>
            )}
            {notifications.length > 0 && (
              <button
                onClick={clearAll}
                className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-slate-800 transition"
                title="Clear all"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        }
      />

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 flex-wrap border-b border-slate-800/80 pb-3">
        <Filter className="w-4 h-4 text-slate-500" />
        {(['ALL', 'CRITICAL', 'WARNING', 'INFO', 'SUCCESS'] as const).map(t => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono transition border ${
              filter === t
                ? 'bg-cyan-950/70 border-cyan-500/50 text-cyan-300 font-bold'
                : 'border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Notifications Queue */}
      <div className="space-y-3">
        {filtered.length === 0 ? (
          <Card className="p-12 text-center">
            <CheckCircle2 className="w-10 h-10 text-emerald-500/50 mx-auto mb-3" />
            <p className="text-slate-300 font-mono text-sm font-semibold">Notification Queue Clear</p>
            <p className="text-slate-500 text-xs mt-1">No alerts match the active severity filter.</p>
          </Card>
        ) : (
          filtered.map(notif => (
            <Card
              key={notif.id}
              className={`p-4 transition-all duration-200 border ${getBorderColor(notif.type, notif.read)}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <div className="mt-0.5 p-1 rounded-md bg-slate-900 border border-slate-800">
                    {getIcon(notif.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="text-xs font-bold text-white font-mono">
                        {notif.title}
                      </span>
                      {notif.machine_code && (
                        <Link
                          to={`/machines/${notif.machine_code}`}
                          className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 font-mono text-[10px] text-cyan-400 hover:border-cyan-500 transition"
                        >
                          {notif.machine_code}
                        </Link>
                      )}
                      {!notif.read && (
                        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping inline-block" />
                      )}
                    </div>

                    <p className="text-xs text-slate-300 leading-relaxed">
                      {notif.message}
                    </p>

                    <div className="flex items-center gap-4 text-[10px] font-mono text-slate-500 mt-2.5">
                      <span>{new Date(notif.timestamp).toLocaleString()}</span>
                      <span className="uppercase text-slate-400">Severity: {notif.type}</span>
                    </div>
                  </div>
                </div>

                {/* Quick Actions */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  {notif.machine_code && (
                    <Link
                      to={`/machines/${notif.machine_code}`}
                      className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-cyan-400 transition"
                      title="Inspect Machine"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </Link>
                  )}
                  {!notif.read && (
                    <button
                      onClick={() => markAsRead(notif.id)}
                      className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono transition"
                    >
                      <Check className="w-3 h-3 text-emerald-400" />
                      <span>Ack</span>
                    </button>
                  )}
                </div>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
