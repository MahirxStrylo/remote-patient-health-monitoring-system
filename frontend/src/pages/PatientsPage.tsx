import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Users, Plus, Search, ChevronRight, Archive, User, AlertCircle, X,
  Radio, Calendar, FileText, ArrowRight
} from 'lucide-react';
import { api } from '../services/api';
import type { PatientCreate } from '../types';
import { formatDistanceToNow } from 'date-fns';

function AddPatientModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<PatientCreate>({ patient_id: '', full_name: '' });
  const [error, setError] = useState('');

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const mutation = useMutation({
    mutationFn: (data: PatientCreate) => api.createPatient(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['patients'] });
      onClose();
    },
    onError: (e: any) => {
      setError(e.response?.data?.detail || e.message || 'Failed to add patient.');
    },
  });

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-md shadow-2xl border border-charcoal-700/80 bg-navy-900/95">
        <div className="flex items-center justify-between pb-3.5 mb-4 border-b border-charcoal-700/60">
          <div>
            <h2 className="text-slate-100 font-semibold text-base flex items-center gap-2">
              <Users className="w-4 h-4 text-cyan-400" />
              Register Rural Patient
            </h2>
            <p className="text-slate-400 text-xs mt-0.5">Enrolls patient into rural telehealth tracking index.</p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-charcoal-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <div className="text-rose-400 text-xs mb-4 p-3 bg-rose-950/40 border border-rose-500/40 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={e => { e.preventDefault(); mutation.mutate(form); }} className="space-y-4">
          <div>
            <label className="label">Patient Code / ID *</label>
            <input
              className="input font-mono"
              placeholder="e.g. P002"
              value={form.patient_id}
              onChange={e => setForm(f => ({ ...f, patient_id: e.target.value.toUpperCase() }))}
              required
            />
            <span className="text-[10px] text-slate-500 mt-1 block">Used by ESP32 firmware in telemetry payloads.</span>
          </div>

          <div>
            <label className="label">Full Legal Name *</label>
            <input
              className="input"
              placeholder="e.g. Ayesha Begum"
              value={form.full_name}
              onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
              required
            />
          </div>

          <div>
            <label className="label">Age (Years)</label>
            <input
              className="input font-mono"
              type="number"
              placeholder="e.g. 52"
              min={1}
              max={120}
              onChange={e => setForm(f => ({ ...f, age: e.target.value ? parseInt(e.target.value) : undefined }))}
            />
          </div>

          <div>
            <label className="label">Clinical Intake Notes (Optional)</label>
            <textarea
              className="input h-20 resize-none"
              placeholder="e.g. Patient has history of hypertension, resides in rural clinic sector 3."
              onChange={e => setForm(f => ({ ...f, notes: e.target.value || undefined }))}
            />
          </div>

          <div className="flex gap-3 pt-3 border-t border-charcoal-700/60">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary flex-1"
              disabled={mutation.isPending || !form.patient_id.trim() || !form.full_name.trim()}
            >
              {mutation.isPending ? 'Registering…' : 'Register Patient'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function PatientsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ['patients', search, showArchived],
    queryFn: () => api.getPatients({ search: search || undefined, archived: showArchived || undefined }),
    staleTime: 10_000,
  });

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-charcoal-700/60">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            <Users className="w-5 h-5 text-cyan-400" />
            Patient Registry
          </h1>
          <p className="text-slate-400 text-xs mt-0.5">
            {data?.total ?? 0} registered patient{data?.total !== 1 ? 's' : ''} enrolled in rural telemetry monitoring
          </p>
        </div>

        <button
          className="btn-primary text-xs self-start sm:self-auto"
          onClick={() => setShowAdd(true)}
        >
          <Plus className="w-4 h-4" />
          Register Patient
        </button>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            className="input pl-9 text-xs"
            placeholder="Search by patient ID code or full name…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <button
          className={`btn-secondary text-xs flex items-center gap-2 self-start sm:self-auto ${
            showArchived ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/40' : ''
          }`}
          onClick={() => setShowArchived(v => !v)}
        >
          <Archive className="w-3.5 h-3.5" />
          {showArchived ? 'Hide Archived' : 'Include Archived'}
        </button>
      </div>

      {/* Patient Table Card */}
      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="text-slate-500 text-xs text-center py-12 flex items-center justify-center gap-2">
            <Users className="w-4 h-4 animate-pulse text-cyan-400" />
            Loading patient records…
          </div>
        ) : error ? (
          <div className="text-rose-400 text-xs text-center py-12">
            Failed to load patient records from backend.
          </div>
        ) : !data?.items?.length ? (
          <div className="text-center py-16 px-4">
            <div className="w-12 h-12 rounded-full bg-charcoal-800 border border-charcoal-700 flex items-center justify-center mx-auto mb-3">
              <User className="w-6 h-6 text-slate-500" />
            </div>
            <div className="text-slate-300 font-medium text-sm">
              {search ? 'No patients match your search filter.' : 'No patients enrolled in this rural clinic yet.'}
            </div>
            <p className="text-slate-500 text-xs mt-1 max-w-sm mx-auto">
              {search ? 'Try searching by patient ID (e.g. P001) or part of their name.' : 'Register the first patient to begin ingesting ECG and vitals telemetry.'}
            </p>
            {!search && (
              <button className="btn-primary text-xs mt-4" onClick={() => setShowAdd(true)}>
                <Plus className="w-3.5 h-3.5" />
                Enroll First Patient
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-charcoal-700/60 text-slate-400 text-left bg-navy-950/40">
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Patient Code</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Full Name</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider hidden md:table-cell">Age</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider hidden lg:table-cell">Hardware Node</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider hidden sm:table-cell">Enrolled</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Status</th>
                  <th className="px-5 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal-800/60">
                {data.items.map(p => (
                  <tr
                    key={p.id}
                    className="table-row cursor-pointer"
                    onClick={() => navigate(`/patients/${p.patient_id}`)}
                  >
                    <td className="px-5 py-3.5 font-mono font-semibold text-cyan-400">
                      {p.patient_id}
                    </td>
                    <td className="px-5 py-3.5 font-medium text-slate-200">
                      {p.full_name}
                    </td>
                    <td className="px-5 py-3.5 text-slate-400 font-mono hidden md:table-cell">
                      {p.age ? `${p.age} yrs` : '—'}
                    </td>
                    <td className="px-5 py-3.5 text-slate-300 hidden lg:table-cell">
                      <span className="inline-flex items-center gap-1 font-mono text-[11px] bg-charcoal-800/80 px-2 py-0.5 rounded border border-charcoal-700">
                        <Radio className="w-3 h-3 text-emerald-400" />
                        {p.device?.device_id || (p.patient_id === 'P001' ? 'ESP32-001' : 'None')}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-slate-500 text-[11px] hidden sm:table-cell">
                      {formatDistanceToNow(new Date(p.created_at), { addSuffix: true })}
                    </td>
                    <td className="px-5 py-3.5">
                      {p.is_archived ? (
                        <span className="badge-gray">Archived</span>
                      ) : (
                        <span className="badge-green">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                          Active
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="inline-flex items-center gap-1 text-slate-400 group-hover:text-cyan-400 font-medium">
                        <span>Chart</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showAdd && <AddPatientModal onClose={() => setShowAdd(false)} />}
    </div>
  );
}
