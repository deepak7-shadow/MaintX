import { BarChart3, TrendingUp, Activity, Shield } from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, RadarChart,
  PolarGrid, PolarAngleAxis, Radar
} from 'recharts';
import { RISK_TREND_DATA, CATEGORY_DISTRIBUTION, MACHINE_RISK_DATA, VERIFICATION_HISTORY } from '../lib/mockData';
import { Card, SectionHeader } from '../components/ui';

const RADAR_DATA = [
  { subject: 'PARAMETERS', A: 85, fullMark: 100 },
  { subject: 'PLC LOGIC', A: 72, fullMark: 100 },
  { subject: 'NETWORK', A: 55, fullMark: 100 },
  { subject: 'FIRMWARE', A: 88, fullMark: 100 },
  { subject: 'FIREWALL', A: 90, fullMark: 100 },
  { subject: 'SAFETY', A: 70, fullMark: 100 },
];

export function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <SectionHeader
        icon={<BarChart3 className="w-5 h-5" />}
        title="Security Analytics"
        subtitle="Change risk distribution, verification outcomes, and compliance posture"
      />

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Total Changes (MTD)', value: '34', delta: '+6 today', color: 'text-cyan-400' },
          { label: 'Avg Risk Score', value: '41', delta: '↑ from 38', color: 'text-amber-400' },
          { label: 'Verification Rate', value: '87%', delta: '7/8 sessions', color: 'text-emerald-400' },
          { label: 'Unauthorized Rate', value: '6%', delta: '2 of 34 changes', color: 'text-rose-400' },
        ].map((k, i) => (
          <Card key={i} className="p-4">
            <p className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">{k.label}</p>
            <p className={`text-3xl font-bold font-mono mt-1 ${k.color}`}>{k.value}</p>
            <p className="text-[10px] text-slate-500 mt-1">{k.delta}</p>
          </Card>
        ))}
      </div>

      {/* Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Risk Trend Area */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-cyan-400" />
            <span className="text-sm font-semibold text-white">7-Day Risk Trend by Level</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={RISK_TREND_DATA} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <defs>
                {[
                  { id: 'critical', color: '#f43f5e' },
                  { id: 'high', color: '#f59e0b' },
                  { id: 'medium', color: '#eab308' },
                  { id: 'low', color: '#10b981' },
                ].map(({ id, color }) => (
                  <linearGradient key={id} id={`g-${id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={color} stopOpacity={0.35} />
                    <stop offset="95%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, fontSize: 11 }} />
              <Area type="monotone" dataKey="critical" stroke="#f43f5e" fill="url(#g-critical)" strokeWidth={2} name="CRITICAL" />
              <Area type="monotone" dataKey="high" stroke="#f59e0b" fill="url(#g-high)" strokeWidth={2} name="HIGH" />
              <Area type="monotone" dataKey="medium" stroke="#eab308" fill="url(#g-medium)" strokeWidth={1.5} name="MEDIUM" />
              <Area type="monotone" dataKey="low" stroke="#10b981" fill="url(#g-low)" strokeWidth={1.5} name="LOW" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        {/* Verification History Stacked Bar */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-semibold text-white">Verification Outcomes (6 Months)</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={VERIFICATION_HISTORY} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="month" tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, fontSize: 11 }} />
              <Bar dataKey="verified" stackId="a" fill="#10b981" name="VERIFIED" radius={[0, 0, 0, 0]} />
              <Bar dataKey="review" stackId="a" fill="#f59e0b" name="REVIEW" />
              <Bar dataKey="failed" stackId="a" fill="#f43f5e" name="FAILED" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Machine Risk Bar */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-amber-400" />
            <span className="text-sm font-semibold text-white">Machine Risk Scores</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={MACHINE_RISK_DATA} layout="vertical" margin={{ top: 0, right: 10, left: 20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
              <XAxis type="number" domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis dataKey="machine" type="category" tick={{ fill: '#94a3b8', fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, fontSize: 11 }} />
              <Bar dataKey="score" name="Risk Score" radius={[0, 4, 4, 0]}>
                {MACHINE_RISK_DATA.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.score >= 85 ? '#f43f5e' : entry.score >= 60 ? '#f59e0b' : entry.score >= 30 ? '#eab308' : '#10b981'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Change Category Pie */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-4 h-4 text-indigo-400" />
            <span className="text-sm font-semibold text-white">Changes by Category</span>
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie
                data={CATEGORY_DISTRIBUTION}
                innerRadius={45}
                outerRadius={75}
                dataKey="value"
                paddingAngle={3}
              >
                {CATEGORY_DISTRIBUTION.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1 mt-2">
            {CATEGORY_DISTRIBUTION.map(cat => (
              <div key={cat.name} className="flex items-center justify-between text-[10px] font-mono">
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: cat.color }} />
                  <span className="text-slate-400">{cat.name}</span>
                </span>
                <span className="text-slate-300">{cat.value}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Security Posture Radar */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-4 h-4 text-cyan-400" />
            <span className="text-sm font-semibold text-white">Security Posture Radar</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={RADAR_DATA}>
              <PolarGrid stroke="#1e293b" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: '#64748b', fontSize: 9 }} />
              <Radar
                name="Compliance"
                dataKey="A"
                stroke="#06b6d4"
                fill="#06b6d4"
                fillOpacity={0.2}
                strokeWidth={2}
              />
              <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: 8, fontSize: 11 }} />
            </RadarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
