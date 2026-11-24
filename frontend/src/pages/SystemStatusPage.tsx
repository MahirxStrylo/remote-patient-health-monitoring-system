import { useQuery } from '@tanstack/react-query';
import {
  Server, Database, Shield, Radio, CheckCircle, AlertCircle, RefreshCw, Cpu, Activity, Clock
} from 'lucide-react';
import { api } from '../services/api';
import { format } from 'date-fns';

export default function SystemStatusPage() {
  const { data: health, isLoading: healthLoading, refetch: refetchHealth, isFetching } = useQuery({
    queryKey: ['system-health'],
    queryFn: api.getHealth,
    refetchInterval: 15000,
  });

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats-system'],
    queryFn: api.getDashboardStats,
    refetchInterval: 15000,
  });

  const { data: settings } = useQuery({
    queryKey: ['system-settings'],
    queryFn: api.getSettings,
  });

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
            <Server className="w-6 h-6 text-cyan-600 dark:text-cyan-400" />
            System Status & Diagnostics
          </h1>
          <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">
            Server environment metrics, database storage telemetry, and security audit log
          </p>
        </div>

        <button
          onClick={() => refetchHealth()}
          disabled={isFetching}
          className="btn-secondary text-sm flex items-center gap-2 self-start sm:self-auto"
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin text-cyan-500' : ''}`} />
          Run Health Probe
        </button>
      </div>

      {/* Health Check Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-semibold uppercase">
            <span>FastAPI Server</span>
            <Server className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-lg font-bold text-slate-900 dark:text-slate-100">
              {health?.status === 'ok' || health?.status === 'healthy' ? 'Operational' : 'Degraded'}
            </span>
          </div>
          <div className="text-xs text-slate-500 mt-1">Uvicorn ASGI Backend</div>
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-semibold uppercase">
            <span>Database Storage</span>
            <Database className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="text-lg font-bold text-slate-900 dark:text-slate-100">
              {health?.database === 'connected' ? 'Connected' : 'Unavailable'}
            </span>
          </div>
          <div className="text-xs text-slate-500 mt-1">SQLAlchemy Async Engine</div>
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-semibold uppercase">
            <span>SIM800L GPRS Gateway</span>
            <Radio className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-500" />
            <span className="text-lg font-bold text-slate-900 dark:text-slate-100">TCP / HTTP Ingest</span>
          </div>
          <div className="text-xs text-slate-500 mt-1">2G Rural Cellular Interface</div>
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-semibold uppercase">
            <span>Device Security</span>
            <Shield className="w-4 h-4 text-violet-600 dark:text-violet-400" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="text-lg font-bold text-slate-900 dark:text-slate-100">O(1) Prefixed Keys</span>
          </div>
          <div className="text-xs text-slate-500 mt-1">Bcrypt Hash Verification</div>
        </div>
      </div>

      {/* Database Entity Row Counts */}
      <div className="card p-5">
        <h2 className="section-title flex items-center gap-2">
          <Database className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          Database Row Counts & Volume
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-3">
          <div className="bg-slate-50 dark:bg-navy-900/60 p-3 rounded-lg border border-slate-200 dark:border-charcoal-700">
            <span className="text-xs text-slate-500 dark:text-slate-400">Total Registered Patients</span>
            <div className="text-xl font-bold font-mono text-cyan-600 dark:text-cyan-400 mt-1">{stats?.total_patients ?? 0}</div>
          </div>
          <div className="bg-slate-50 dark:bg-navy-900/60 p-3 rounded-lg border border-slate-200 dark:border-charcoal-700">
            <span className="text-xs text-slate-500 dark:text-slate-400">Active Devices Reporting</span>
            <div className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">{stats?.active_devices ?? 0} / {stats?.total_devices ?? 0}</div>
          </div>
          <div className="bg-slate-50 dark:bg-navy-900/60 p-3 rounded-lg border border-slate-200 dark:border-charcoal-700">
            <span className="text-xs text-slate-500 dark:text-slate-400">ECG Recording Sessions</span>
            <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-200 mt-1">{stats?.recent_ecg_count ?? 0}</div>
          </div>
          <div className="bg-slate-50 dark:bg-navy-900/60 p-3 rounded-lg border border-slate-200 dark:border-charcoal-700">
            <span className="text-xs text-slate-500 dark:text-slate-400">Telemetry Ingest Batches</span>
            <div className="text-xl font-bold font-mono text-slate-900 dark:text-slate-200 mt-1">{stats?.latest_uploads_count ?? 0}</div>
          </div>
        </div>
      </div>

      {/* Security Audit Events Log */}
      <div className="card p-0 overflow-hidden">
        <div className="p-4 border-b border-slate-200 dark:border-charcoal-700 bg-slate-50 dark:bg-navy-900/40 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
            Live Security & Telemetry Audit Trail
          </h2>
          <span className="text-xs text-slate-500 font-mono">Immutable audit_events table</span>
        </div>

        {statsLoading ? (
          <div className="text-slate-500 text-sm text-center py-16 flex items-center justify-center gap-2">
            <Activity className="w-4 h-4 animate-pulse text-cyan-500" />
            Loading audit log…
          </div>
        ) : !stats?.recent_events?.length ? (
          <div className="text-center py-16 text-slate-500 text-sm">No audit events recorded yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-200 dark:border-charcoal-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase bg-slate-100/80 dark:bg-navy-950/60">
                  <th className="px-5 py-3">Timestamp (UTC)</th>
                  <th className="px-5 py-3">Event Type</th>
                  <th className="px-5 py-3">Actor</th>
                  <th className="px-5 py-3">Audit Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-charcoal-800 text-xs">
                {stats.recent_events.map((ev, i) => (
                  <tr key={i} className="hover:bg-slate-50 dark:hover:bg-charcoal-800/30 transition-colors">
                    <td className="px-5 py-3 font-mono text-slate-500 dark:text-slate-400">
                      {format(new Date(ev.created_at), 'yyyy-MM-dd HH:mm:ss')}
                    </td>
                    <td className="px-5 py-3">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-mono ${
                        ev.event_type.includes('error') || ev.event_type.includes('failed')
                          ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/30 dark:border-rose-800/40'
                          : ev.event_type.includes('login') || ev.event_type.includes('auth')
                          ? 'bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/30 dark:border-violet-800/40'
                          : 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/30 dark:border-cyan-800/40'
                      }`}>
                        {ev.event_type}
                      </span>
                    </td>
                    <td className="px-5 py-3 font-mono text-slate-700 dark:text-slate-300">
                      {ev.actor_type}: {ev.actor_id ?? 'system'}
                    </td>
                    <td className="px-5 py-3 text-slate-800 dark:text-slate-300">
                      {ev.detail ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Environment Diagnostics */}
      <div className="card p-5">
        <h2 className="section-title flex items-center gap-2">
          <Cpu className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          Environment & Server Configuration
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3 text-xs text-slate-600 dark:text-slate-400">
          <div className="flex justify-between py-1.5 border-b border-slate-200 dark:border-charcoal-800">
            <span className="text-slate-500">Application Version:</span>
            <span className="font-mono text-slate-900 dark:text-slate-200">{settings?.app_version ?? '2.0.0-PROD'}</span>
          </div>
          <div className="flex justify-between py-1.5 border-b border-slate-200 dark:border-charcoal-800">
            <span className="text-slate-500">Max ECG Samples Per Ingest Batch:</span>
            <span className="font-mono text-slate-900 dark:text-slate-200">{settings?.max_ecg_samples_per_batch ?? 10000} samples</span>
          </div>
          <div className="flex justify-between py-1.5 border-b border-slate-200 dark:border-charcoal-800">
            <span className="text-slate-500">Stale Telemetry Threshold:</span>
            <span className="font-mono text-slate-900 dark:text-slate-200">{settings?.stale_reading_threshold_minutes ?? 15} minutes</span>
          </div>
          <div className="flex justify-between py-1.5 border-b border-slate-200 dark:border-charcoal-800">
            <span className="text-slate-500">Database Driver:</span>
            <span className="font-mono text-slate-900 dark:text-slate-200">Async SQLAlchemy (Dual SQLite / PostgreSQL Engine)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
