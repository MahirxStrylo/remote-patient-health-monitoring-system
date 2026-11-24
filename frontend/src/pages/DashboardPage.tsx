import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Users, Cpu, Activity, Upload, AlertCircle, Clock, ChevronRight,
  Plus, FileText, Heart, ShieldCheck, Radio, CheckCircle, ArrowUpRight
} from 'lucide-react';
import { api } from '../services/api';
import { formatDistanceToNow, format } from 'date-fns';

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => api.getDashboardStats(),
    refetchInterval: 15_000,
  });

  const { data: patientsData } = useQuery({
    queryKey: ['dashboard-patients'],
    queryFn: () => api.getPatients({ size: 5 }),
    refetchInterval: 30_000,
  });

  const { data: prescriptionsData } = useQuery({
    queryKey: ['dashboard-prescriptions'],
    queryFn: () => api.getPrescriptions({ size: 5 }),
    refetchInterval: 15_000,
  });

  if (statsLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-slate-400 flex items-center gap-2.5 text-sm font-medium">
          <Activity className="w-5 h-5 text-cyan-400 animate-pulse" />
          Synchronizing clinical telemetry counters…
        </div>
      </div>
    );
  }

  if (statsError) {
    return (
      <div className="card border-rose-500/40 bg-rose-950/20 p-4 text-rose-300 flex items-center gap-3">
        <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
        <div>
          <div className="font-semibold text-sm">Failed to connect to backend telemetry stream.</div>
          <div className="text-xs text-rose-400/80 mt-0.5">Please ensure FastAPI server is running on localhost:8000.</div>
        </div>
      </div>
    );
  }

  const statCards = [
    {
      label: 'Registered Patients',
      value: stats?.total_patients ?? 0,
      icon: Users,
      color: 'text-cyan-400',
      bgGlow: 'bg-cyan-500/10 border-cyan-500/30',
      subtext: 'Rural Telehealth Registry',
      to: '/patients',
    },
    {
      label: 'Active IoT Nodes',
      value: `${stats?.active_devices ?? 0} / ${stats?.total_devices ?? 0}`,
      icon: Cpu,
      color: 'text-emerald-400',
      bgGlow: 'bg-emerald-500/10 border-emerald-500/30',
      subtext: 'ESP32 GPRS / Wi-Fi Nodes',
      to: '/devices',
    },
    {
      label: 'Telemetry Batches',
      value: stats?.latest_uploads_count ?? 0,
      icon: Upload,
      color: 'text-sky-400',
      bgGlow: 'bg-sky-500/10 border-sky-500/30',
      subtext: 'Idempotent 250 Hz Chunks',
      to: '/recordings',
    },
    {
      label: 'Active Directives',
      value: prescriptionsData?.total ?? 0,
      icon: FileText,
      color: 'text-amber-400',
      bgGlow: 'bg-amber-500/10 border-amber-500/30',
      subtext: 'Prescriptions on LCDs',
      to: '/prescriptions',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header with Quick Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-charcoal-700/60">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            Clinical Overview
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          </h1>
          <p className="text-slate-400 text-xs mt-0.5">
            Real-time multi-patient physiological status &amp; remote edge node operations
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link to="/prescriptions" className="btn-primary text-xs py-2 px-3">
            <Plus className="w-3.5 h-3.5" />
            Issue Prescription
          </Link>
          <Link to="/recordings" className="btn-secondary text-xs py-2 px-3">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            View ECG Waveforms
          </Link>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(({ label, value, icon: Icon, color, bgGlow, subtext, to }) => (
          <Link
            key={label}
            to={to}
            className={`stat-card border p-4.5 rounded-xl transition-all duration-200 hover:-translate-y-0.5 group ${bgGlow}`}
          >
            <div className="flex items-center justify-between">
              <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">{label}</span>
              <div className="w-8 h-8 rounded-lg bg-navy-950/60 border border-charcoal-700 flex items-center justify-center">
                <Icon className={`w-4 h-4 ${color}`} />
              </div>
            </div>
            <div className="my-2">
              <div className="text-2xl font-bold tracking-tight text-slate-100 font-mono">{value}</div>
              <div className="text-[11px] text-slate-400 mt-0.5 flex items-center justify-between">
                <span>{subtext}</span>
                <ChevronRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 transition-colors" />
              </div>
            </div>
          </Link>
        ))}
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Columns: Patients Quick-Access & Directives */}
        <div className="lg:col-span-2 space-y-6">
          {/* Active Patients Ribbon */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-semibold text-slate-100">Monitored Rural Patients</h2>
              </div>
              <Link to="/patients" className="text-xs text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1">
                View all patients <ChevronRight className="w-3 h-3" />
              </Link>
            </div>

            {!patientsData?.items.length ? (
              <div className="text-center py-8 text-slate-500 text-xs">
                No patients registered yet. Click &quot;Add Patient&quot; in the patient registry.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-charcoal-700/60 text-slate-400 text-left">
                      <th className="py-2.5 px-3 font-semibold uppercase tracking-wider">Patient Code</th>
                      <th className="py-2.5 px-3 font-semibold uppercase tracking-wider">Full Name</th>
                      <th className="py-2.5 px-3 font-semibold uppercase tracking-wider">Age</th>
                      <th className="py-2.5 px-3 font-semibold uppercase tracking-wider">Assigned Device</th>
                      <th className="py-2.5 px-3 font-semibold uppercase tracking-wider text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-charcoal-800/60">
                    {patientsData.items.map(p => (
                      <tr key={p.id} className="hover:bg-charcoal-800/30 transition-colors">
                        <td className="py-2.5 px-3 font-mono font-semibold text-cyan-400">
                          {p.patient_id}
                        </td>
                        <td className="py-2.5 px-3 font-medium text-slate-200">
                          {p.full_name}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">
                          {p.age ? `${p.age} yrs` : '—'}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="inline-flex items-center gap-1 font-mono text-[11px] text-slate-300 bg-charcoal-800/80 px-2 py-0.5 rounded border border-charcoal-700">
                            <Radio className="w-3 h-3 text-emerald-400" />
                            {p.patient_id === 'P001' ? 'ESP32-001' : 'Unassigned'}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <Link
                            to={`/patients/${p.patient_id}`}
                            className="inline-flex items-center gap-1 text-[11px] text-cyan-400 hover:text-cyan-300 font-medium"
                          >
                            Clinical Chart <ArrowUpRight className="w-3 h-3" />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Recent Directives Delivered to LCD */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-amber-400" />
                <h2 className="text-sm font-semibold text-slate-100">Recent Doctor Directives &amp; Prescriptions</h2>
              </div>
              <Link to="/prescriptions" className="text-xs text-amber-400 hover:text-amber-300 font-medium flex items-center gap-1">
                Prescriptions Hub <ChevronRight className="w-3 h-3" />
              </Link>
            </div>

            {!prescriptionsData?.items.length ? (
              <div className="text-center py-8 text-slate-500 text-xs">
                No active directives dispatched. Click &quot;Issue Prescription&quot; to author a directive.
              </div>
            ) : (
              <div className="space-y-2">
                {prescriptionsData.items.map(rx => (
                  <div
                    key={rx.id}
                    className="p-3 rounded-lg bg-navy-950/60 border border-charcoal-700/60 flex items-center justify-between gap-4"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-xs text-slate-200">
                          {rx.medication} ({rx.dosage})
                        </span>
                        <span className="text-[11px] text-slate-400">· {rx.frequency}</span>
                        <span
                          className={`inline-flex items-center px-2 py-0.2 rounded-full text-[10px] font-medium ${
                            rx.status === 'Acknowledged'
                              ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                              : rx.status === 'Delivered'
                              ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                              : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                          }`}
                        >
                          {rx.status}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400 mt-1 truncate">
                        Pt: {rx.patient_code || `P${rx.patient_id}`} — Dx: {rx.assessment}
                      </div>
                    </div>
                    <div className="text-right text-[11px] text-slate-500 font-mono flex-shrink-0">
                      {format(new Date(rx.created_at), 'MM/dd HH:mm')}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right 1 Column: Telemetry Audit Stream & System Status */}
        <div className="space-y-6">
          {/* Recent System Telemetry Events */}
          <div className="card">
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2 mb-3">
              <Clock className="w-4 h-4 text-cyan-400" />
              Live Ingestion Log
            </h2>

            {(!stats?.recent_events || stats.recent_events.length === 0) ? (
              <div className="text-slate-500 text-xs py-6 text-center">No recent telemetry events recorded.</div>
            ) : (
              <div className="space-y-2.5">
                {stats.recent_events.slice(0, 6).map((ev, i) => (
                  <div key={i} className="flex items-start gap-2.5 text-xs pb-2.5 border-b border-charcoal-800/80 last:border-0 last:pb-0">
                    <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5 flex-shrink-0 animate-ping" />
                    <div className="flex-1 min-w-0">
                      <div className="text-slate-200 font-medium truncate">{ev.detail ?? ev.event_type}</div>
                      <div className="text-slate-500 text-[10px] flex items-center justify-between mt-0.5">
                        <span className="font-mono text-cyan-400/80">{ev.actor_id || 'ESP32'}</span>
                        <span>{formatDistanceToNow(new Date(ev.created_at), { addSuffix: true })}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Operational Topology Info Card */}
          <div className="card bg-navy-900/80 border border-charcoal-700/60 p-4 space-y-3">
            <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 uppercase tracking-wider">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Edge Architecture Profile
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between text-slate-400">
                <span>Microcontroller:</span>
                <span className="font-mono text-slate-200">ESP32 DevKit V1</span>
              </div>
              <div className="flex items-center justify-between text-slate-400">
                <span>ECG Sampling:</span>
                <span className="font-mono text-cyan-400">250 Hz (AD8232)</span>
              </div>
              <div className="flex items-center justify-between text-slate-400">
                <span>Cellular Modem:</span>
                <span className="font-mono text-slate-200">SIM800L 2G GPRS</span>
              </div>
              <div className="flex items-center justify-between text-slate-400">
                <span>Local Display:</span>
                <span className="font-mono text-slate-200">20x4 I2C LCD</span>
              </div>
              <div className="flex items-center justify-between text-slate-400">
                <span>Database:</span>
                <span className="font-mono text-emerald-400">SQLite (Local) / Postgres</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
