import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Activity, Search, Filter, Eye, AlertTriangle, CheckCircle, Clock, Zap,
  Radio, Brain, ChevronRight
} from 'lucide-react';
import { api } from '../services/api';
import { format } from 'date-fns';

function SessionStatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'Recording':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          Live Recording
        </span>
      );
    case 'Completed':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
          <CheckCircle className="w-3.5 h-3.5" />
          Completed
        </span>
      );
    case 'Incomplete':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/15 text-amber-300 border border-amber-500/30">
          <AlertTriangle className="w-3.5 h-3.5" />
          Cellular Gaps
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-500/15 text-slate-400 border border-slate-500/30">
          <Clock className="w-3.5 h-3.5" />
          {status}
        </span>
      );
  }
}

export default function RecordingsPage() {
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const { data, isLoading } = useQuery({
    queryKey: ['ecg-sessions', statusFilter],
    queryFn: () => api.getECGSessions({ status: statusFilter || undefined, size: 100 }),
    refetchInterval: 10000,
  });

  const sessions = data?.items ?? [];
  const filteredSessions = sessions.filter(s => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      s.session_id.toLowerCase().includes(term) ||
      (s.patient_code && s.patient_code.toLowerCase().includes(term)) ||
      (s.patient_name && s.patient_name.toLowerCase().includes(term)) ||
      (s.device_code && s.device_code.toLowerCase().includes(term))
    );
  });

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-charcoal-700/60">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            <Activity className="w-5 h-5 text-cyan-400" />
            ECG Recording Sessions
          </h1>
          <p className="text-slate-400 text-xs mt-0.5">
            Chronological multi-batch physiological recordings grouped by patient edge node session
          </p>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-navy-900/80 p-3 rounded-xl border border-charcoal-700/70">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            className="input pl-10 text-xs w-full"
            placeholder="Search by session UUID, patient code, or device ID..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-slate-400 flex-shrink-0" />
          <select
            className="input py-1.5 text-xs font-medium w-full sm:w-auto"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="Recording">Recording (Active)</option>
            <option value="Completed">Completed (Clean)</option>
            <option value="Incomplete">Incomplete (Cellular Gaps)</option>
          </select>
        </div>
      </div>

      {/* Sessions Table Card */}
      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="text-slate-500 text-xs text-center py-16 flex items-center justify-center gap-2">
            <Activity className="w-4 h-4 animate-pulse text-cyan-400" />
            Synchronizing ECG session registry…
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="text-center py-16 px-4">
            <div className="w-12 h-12 rounded-full bg-charcoal-800 border border-charcoal-700 flex items-center justify-center mx-auto mb-3">
              <Zap className="w-6 h-6 text-slate-500" />
            </div>
            <div className="text-slate-300 font-medium text-sm">No ECG sessions match the current criteria.</div>
            <p className="text-slate-500 text-xs mt-1">Run Wokwi or physical ESP32 to upload telemetry batches.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-charcoal-700/60 bg-navy-950/40 text-slate-400">
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Session Identifier</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Patient</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Status</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Batches / Samples</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider hidden md:table-cell">Started</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal-800/60">
                {filteredSessions.map(s => {
                  const durationSec = s.sampling_rate_hz > 0 ? (s.total_samples / s.sampling_rate_hz).toFixed(1) : '—';
                  return (
                    <tr key={s.session_id} className="hover:bg-charcoal-800/30 transition-colors">
                      <td className="px-5 py-3.5">
                        <div className="font-mono font-semibold text-cyan-400 text-xs">
                          {s.session_id}
                        </div>
                        <div className="text-slate-400 text-[11px] mt-0.5">
                          {s.sampling_rate_hz} Hz · {s.unit || 'adc_counts'}
                          {s.is_simulated && <span className="ml-2 text-cyan-400/80 font-mono">(Simulated)</span>}
                        </div>
                      </td>

                      <td className="px-5 py-3.5">
                        <div className="text-slate-200 font-medium">
                          {s.patient_name || s.patient_code || `P${s.patient_id}`}
                        </div>
                        <div className="text-slate-500 text-[11px] font-mono flex items-center gap-1.5 mt-0.5">
                          <span>{s.patient_code || 'P001'}</span>
                          <span>·</span>
                          <span className="text-slate-400">{s.device_code || 'ESP32-001'}</span>
                        </div>
                      </td>

                      <td className="px-5 py-3.5">
                        <SessionStatusBadge status={s.status} />
                      </td>

                      <td className="px-5 py-3.5">
                        <div className="font-mono text-slate-200 font-medium">
                          {s.total_batches} batch(es) · {s.total_samples} samples
                        </div>
                        <div className="text-slate-500 text-[11px] font-mono mt-0.5">
                          ~{durationSec}s signal duration
                        </div>
                      </td>

                      <td className="px-5 py-3.5 text-slate-400 text-[11px] hidden md:table-cell font-mono">
                        {format(new Date(s.started_at), 'yyyy-MM-dd HH:mm:ss')}
                      </td>

                      <td className="px-5 py-3.5 text-right">
                        <Link
                          to={`/ecg/${s.session_id}`}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded bg-charcoal-800 hover:bg-cyan-500/20 text-slate-300 hover:text-cyan-300 border border-charcoal-700 transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>View Waveform</span>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
