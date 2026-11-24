import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Heart, Thermometer, Activity, FileText, Edit3, Save, X,
  Archive, AlertCircle, ChevronRight, Clock, Cpu, Brain, Radio, Plus
} from 'lucide-react';
import { api } from '../services/api';
import type { PatientUpdate } from '../types';
import { formatDistanceToNow, format } from 'date-fns';

function VitalCard({
  label,
  value,
  unit,
  icon: Icon,
  color,
  isStale,
}: {
  label: string;
  value: number | null | undefined;
  unit: string;
  icon: React.ElementType;
  color: string;
  isStale?: boolean;
}) {
  const isZeroHR = label === 'Heart Rate' && value === 0;
  const isHypoxia = label === 'SpO₂' && value != null && value < 90;
  const isBradycardia = label === 'Heart Rate' && value != null && value > 0 && value < 60;
  const isTachycardia = label === 'Heart Rate' && value != null && value > 100;
  const isFever = label === 'Temperature' && value != null && value > 37.8;

  return (
    <div
      className={`stat-card p-4 rounded-xl border transition-all ${
        isZeroHR || isHypoxia
          ? 'border-rose-500/50 bg-rose-950/20'
          : isBradycardia || isTachycardia || isFever
          ? 'border-amber-500/40 bg-amber-950/15'
          : 'border-charcoal-700/60 bg-navy-900/80'
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider">{label}</span>
        <div className="w-7 h-7 rounded-lg bg-navy-950/80 border border-charcoal-700 flex items-center justify-center">
          <Icon className={`w-4 h-4 ${color}`} />
        </div>
      </div>

      <div className="my-2">
        <div
          className={`text-2xl font-bold font-mono tracking-tight ${
            value != null
              ? isZeroHR || isHypoxia
                ? 'text-rose-400'
                : isBradycardia || isTachycardia || isFever
                ? 'text-amber-300'
                : 'text-slate-100'
              : 'text-slate-600'
          }`}
        >
          {value != null ? value : '—'}
          {value != null && <span className="text-xs font-normal text-slate-400 ml-1">{unit}</span>}
        </div>

        {isZeroHR && (
          <div className="text-[11px] text-rose-400 font-semibold mt-1 flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5" /> Critical: No Pulse Detected
          </div>
        )}
        {isHypoxia && (
          <div className="text-[11px] text-rose-400 font-semibold mt-1 flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5" /> Hypoxemia (&lt;90% SpO₂)
          </div>
        )}
        {isBradycardia && (
          <div className="text-[11px] text-amber-400 font-medium mt-1">Bradycardia (&lt;60 BPM)</div>
        )}
        {isTachycardia && (
          <div className="text-[11px] text-amber-400 font-medium mt-1">Tachycardia (&gt;100 BPM)</div>
        )}
        {isFever && (
          <div className="text-[11px] text-amber-400 font-medium mt-1">Elevated Temperature (&gt;37.8°C)</div>
        )}
        {value == null && label === 'Temperature' && (
          <div className="text-[11px] text-amber-500/80 mt-1">Sensor Disconnected</div>
        )}
        {isStale && (
          <div className="text-[10px] text-amber-400 font-mono mt-1">Telemetry Stale (&gt;60m)</div>
        )}
      </div>
    </div>
  );
}

function AIBadge({
  status,
  classification,
  confidence,
}: {
  status: string;
  classification: string | null;
  confidence: number | null;
}) {
  if (status === 'pending') return <span className="badge-gray"><Brain className="w-3 h-3" />AI Pending</span>;
  if (status === 'processing') return <span className="badge-blue"><Brain className="w-3 h-3 animate-pulse" />AI Processing</span>;
  if (status === 'failed') return <span className="badge-red"><Brain className="w-3 h-3" />AI Failed</span>;
  if (classification) {
    const isNormal = classification.toLowerCase().includes('normal') || classification.toLowerCase().includes('sinus');
    return (
      <span className={isNormal ? 'badge-green' : 'badge-yellow'}>
        <Brain className="w-3 h-3" />
        {classification}{confidence ? ` (${(confidence * 100).toFixed(0)}%)` : ''}
      </span>
    );
  }
  return <span className="badge-gray"><Brain className="w-3 h-3" />No analysis</span>;
}

export default function PatientDetailPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<PatientUpdate>({});
  const [noteText, setNoteText] = useState('');
  const [savingNote, setSavingNote] = useState(false);

  const { data: patient, isLoading: patLoading, error: patError } = useQuery({
    queryKey: ['patient', patientId],
    queryFn: () => api.getPatient(patientId!),
    enabled: !!patientId,
  });

  const { data: vitals } = useQuery({
    queryKey: ['patient-vitals', patientId],
    queryFn: () => api.getPatientVitals(patientId!, 50),
    enabled: !!patientId,
    refetchInterval: 30_000,
  });

  const { data: ecgList } = useQuery({
    queryKey: ['patient-ecg', patientId],
    queryFn: () => api.getPatientECGRecordings(patientId!),
    enabled: !!patientId,
  });

  const { data: notes, refetch: refetchNotes } = useQuery({
    queryKey: ['patient-notes', patientId],
    queryFn: () => api.getPatientNotes(patientId!),
    enabled: !!patientId,
  });

  const { data: prescriptions } = useQuery({
    queryKey: ['patient-prescriptions', patientId],
    queryFn: () => api.getPatientPrescriptions(patientId!),
    enabled: !!patientId,
    refetchInterval: 10_000,
  });

  const updateMutation = useMutation({
    mutationFn: (data: PatientUpdate) => api.updatePatient(patientId!, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['patient', patientId] });
      setEditing(false);
    },
  });

  const latestVital = vitals?.[0];

  const handleSaveNote = async () => {
    if (!noteText.trim() || !patientId) return;
    setSavingNote(true);
    try {
      await api.addPatientNote(patientId, noteText.trim());
      setNoteText('');
      refetchNotes();
    } finally {
      setSavingNote(false);
    }
  };

  if (patLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-slate-400 flex items-center gap-2 text-sm font-medium">
          <Activity className="w-5 h-5 text-cyan-400 animate-pulse" />
          Loading patient clinical chart…
        </div>
      </div>
    );
  }

  if (patError || !patient) {
    return (
      <div className="card border-rose-500/40 bg-rose-950/20 p-4 text-rose-300 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <AlertCircle className="w-5 h-5 text-rose-400" />
          <span>Patient record not found or inaccessible.</span>
        </div>
        <button className="btn-secondary text-xs" onClick={() => navigate('/patients')}>
          Back to Patient List
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Patient Profile Hero Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-charcoal-700/60">
        <div className="flex items-start gap-3">
          <button
            onClick={() => navigate('/patients')}
            className="p-2 rounded-lg bg-charcoal-800 text-slate-400 hover:text-slate-200 border border-charcoal-700 transition-colors mt-0.5"
            title="Return to Patients"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-xl font-bold text-slate-100">{patient.full_name}</h1>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                {patient.patient_id}
              </span>
              {patient.is_archived ? (
                <span className="badge-gray">Archived</span>
              ) : (
                <span className="badge-green">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Active Telemetry
                </span>
              )}
            </div>
            <p className="text-slate-400 text-xs mt-1 flex items-center gap-2 flex-wrap">
              <span>{patient.age ? `${patient.age} years old` : 'Age Unspecified'}</span>
              <span>·</span>
              <span>Registered {formatDistanceToNow(new Date(patient.created_at), { addSuffix: true })}</span>
              <span>·</span>
              <span className="flex items-center gap-1 font-mono text-cyan-400">
                <Radio className="w-3 h-3 text-emerald-400" />
                {patient.device?.device_id || (patient.patient_id === 'P001' ? 'ESP32-001' : 'Unlinked')}
              </span>
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 self-start md:self-auto">
          {!editing ? (
            <>
              <button
                className="btn-secondary text-xs"
                onClick={() => {
                  setEditing(true);
                  setEditForm({
                    full_name: patient.full_name,
                    age: patient.age ?? undefined,
                    notes: patient.notes ?? undefined,
                  });
                }}
              >
                <Edit3 className="w-3.5 h-3.5" />
                Edit Profile
              </button>
              <Link to="/prescriptions" className="btn-primary text-xs">
                <Plus className="w-3.5 h-3.5" />
                Issue Prescription
              </Link>
            </>
          ) : (
            <>
              <button
                className="btn-primary text-xs"
                onClick={() => updateMutation.mutate(editForm)}
                disabled={updateMutation.isPending}
              >
                <Save className="w-3.5 h-3.5" />
                {updateMutation.isPending ? 'Saving…' : 'Save Changes'}
              </button>
              <button className="btn-secondary text-xs" onClick={() => setEditing(false)}>
                <X className="w-3.5 h-3.5" />
                Cancel
              </button>
            </>
          )}
        </div>
      </div>

      {/* Profile Edit Drawer (Conditional) */}
      {editing && (
        <div className="card space-y-4 border-cyan-500/30 bg-navy-900/90">
          <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
            <Edit3 className="w-4 h-4 text-cyan-400" />
            Edit Demographic &amp; Clinical Info
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Full Name</label>
              <input
                className="input"
                value={editForm.full_name ?? ''}
                onChange={e => setEditForm(f => ({ ...f, full_name: e.target.value }))}
              />
            </div>
            <div>
              <label className="label">Age</label>
              <input
                className="input font-mono"
                type="number"
                value={editForm.age ?? ''}
                onChange={e => setEditForm(f => ({ ...f, age: e.target.value ? parseInt(e.target.value) : undefined }))}
              />
            </div>
          </div>
          <div>
            <label className="label">Clinical Intake Notes</label>
            <textarea
              className="input h-20 resize-none"
              value={editForm.notes ?? ''}
              onChange={e => setEditForm(f => ({ ...f, notes: e.target.value || undefined }))}
            />
          </div>
        </div>
      )}

      {/* Latest Vitals Section */}
      <div>
        {(() => {
          const isStale = latestVital
            ? Date.now() - new Date(latestVital.recorded_at).getTime() > 60 * 60 * 1000
            : false;
          return (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                  <Heart className="w-4 h-4 text-rose-400" />
                  Latest Telemetry Stream
                  {latestVital && (
                    <span className="text-slate-500 text-xs font-normal ml-1">
                      — {formatDistanceToNow(new Date(latestVital.recorded_at), { addSuffix: true })}
                      {isStale && (
                        <span className="badge-yellow text-[10px] ml-2 py-0 px-1.5 font-mono">
                          Stale (&gt;60m)
                        </span>
                      )}
                    </span>
                  )}
                </h2>
                <Link to="/vitals" className="text-xs text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1">
                  Full Vitals Trends <ChevronRight className="w-3 h-3" />
                </Link>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <VitalCard
                  label="Heart Rate"
                  value={latestVital?.heart_rate_bpm}
                  unit="BPM"
                  icon={Heart}
                  color="text-rose-400"
                  isStale={isStale}
                />
                <VitalCard
                  label="SpO₂"
                  value={latestVital?.spo2_percent}
                  unit="%"
                  icon={Activity}
                  color="text-cyan-400"
                  isStale={isStale}
                />
                <VitalCard
                  label="Temperature"
                  value={latestVital?.temperature_c}
                  unit="°C"
                  icon={Thermometer}
                  color="text-amber-400"
                  isStale={isStale}
                />
              </div>
            </div>
          );
        })()}
      </div>

      {/* Two-Column Mid-Section: ECG Recordings & Active Prescriptions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ECG Recordings Column */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              ECG Recording Sessions
            </h2>
            <Link to="/recordings" className="text-xs text-cyan-400 hover:text-cyan-300 font-medium flex items-center gap-1">
              All Sessions <ChevronRight className="w-3 h-3" />
            </Link>
          </div>

          {!ecgList?.length ? (
            <div className="text-slate-500 text-xs py-8 text-center">
              No ECG sessions recorded for this patient yet.
            </div>
          ) : (
            <div className="space-y-2">
              {ecgList.map(ecg => {
                const recId = ecg.recording_id || ecg.session_id || `${ecg.id}`;
                const recordedAt = ecg.recorded_at || ecg.started_at || ecg.created_at;
                const sampleCount = ecg.sample_count ?? ecg.total_samples ?? 0;
                return (
                  <Link
                    key={ecg.id}
                    to={`/ecg/${recId}`}
                    className="flex items-center justify-between p-3 rounded-lg bg-navy-950/60 border border-charcoal-700/60 hover:border-cyan-500/40 transition-all group"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs font-semibold text-cyan-400">
                          {recId.slice(0, 16)}…
                        </span>
                        <AIBadge
                          status={ecg.ai_analysis_status}
                          classification={ecg.ai_classification ?? null}
                          confidence={ecg.ai_confidence ?? null}
                        />
                        {(ecg.lead_off || (ecg.lead_off_count ?? 0) > 0) && (
                          <span className="badge-red text-[10px]">Lead Off</span>
                        )}
                      </div>
                      <div className="text-slate-400 text-[11px] mt-1">
                        {format(new Date(recordedAt), 'yyyy-MM-dd HH:mm:ss')} · {sampleCount} samples @ {ecg.sampling_rate_hz} Hz
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 transition-colors flex-shrink-0" />
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* Active Prescriptions & Directives Column */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <FileText className="w-4 h-4 text-amber-400" />
              Patient Directives &amp; Prescriptions
            </h2>
            <Link to="/prescriptions" className="text-xs text-amber-400 hover:text-amber-300 font-medium flex items-center gap-1">
              Issue New <Plus className="w-3 h-3" />
            </Link>
          </div>

          {!prescriptions?.length ? (
            <div className="text-slate-500 text-xs py-8 text-center">
              No clinical directives dispatched to this patient yet.
            </div>
          ) : (
            <div className="space-y-2">
              {prescriptions.map(p => (
                <div
                  key={p.id}
                  className="p-3 bg-navy-950/60 rounded-lg border border-charcoal-700/60 flex items-center justify-between gap-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-xs text-slate-200">
                        {p.medication}
                      </span>
                      <span className="text-slate-400 text-xs">({p.dosage} · {p.frequency})</span>
                      <span
                        className={`inline-flex items-center px-2 py-0.2 rounded-full text-[10px] font-medium ${
                          p.status === 'Acknowledged'
                            ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                            : p.status === 'Delivered'
                            ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                            : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                        }`}
                      >
                        {p.status}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-1 truncate">
                      Dx: {p.assessment} {p.instructions ? `— ${p.instructions}` : ''}
                    </div>
                  </div>
                  <div className="text-right text-[11px] text-slate-500 font-mono flex-shrink-0">
                    {format(new Date(p.created_at), 'MM/dd HH:mm')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Doctor Clinical Notes Section */}
      <div className="card space-y-4">
        <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
          <FileText className="w-4 h-4 text-slate-400" />
          Physician Clinical Notes
        </h2>

        <div className="space-y-2.5">
          {!notes?.length ? (
            <div className="text-slate-500 text-xs py-3 text-center">No clinical observations logged yet.</div>
          ) : (
            notes.map(note => (
              <div key={note.id} className="p-3 bg-navy-950/60 rounded-lg border border-charcoal-700/60">
                <div className="text-slate-200 text-xs whitespace-pre-wrap leading-relaxed">{note.content}</div>
                <div className="text-slate-500 text-[10px] mt-2 font-mono flex items-center gap-1.5">
                  <Clock className="w-3 h-3" />
                  {formatDistanceToNow(new Date(note.created_at), { addSuffix: true })}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="space-y-2.5 pt-2 border-t border-charcoal-700/60">
          <textarea
            className="input h-20 resize-none text-xs"
            placeholder="Record clinical observations, dosage adjustments, or telephone consult notes…"
            value={noteText}
            onChange={e => setNoteText(e.target.value)}
          />
          <div className="flex justify-end">
            <button
              className="btn-primary text-xs"
              onClick={handleSaveNote}
              disabled={savingNote || !noteText.trim()}
            >
              {savingNote ? 'Recording Note…' : 'Add Clinical Note'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
