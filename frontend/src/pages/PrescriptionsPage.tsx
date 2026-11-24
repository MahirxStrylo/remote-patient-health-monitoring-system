import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FileText, Plus, Search, CheckCircle, Clock, AlertCircle, X,
  Radio, Send, Monitor, Eye
} from 'lucide-react';
import { api } from '../services/api';
import type { Prescription, PrescriptionCreate } from '../types';
import { format } from 'date-fns';

function StatusBadge({ status }: {
  status: Prescription['status'];
  deliveredAt?: string | null;
  acknowledgedAt?: string | null;
}) {
  switch (status) {
    case 'Pending':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 dark:border-amber-500/30">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
          Pending Delivery
        </span>
      );
    case 'Delivered':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20 dark:border-cyan-500/30">
          <Radio className="w-3 h-3 text-cyan-500 animate-pulse" />
          Delivered to LCD
        </span>
      );
    case 'Acknowledged':
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 dark:border-emerald-500/30">
          <CheckCircle className="w-3 h-3" />
          Acknowledged
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20 dark:border-slate-500/30">
          <Clock className="w-3 h-3" />
          {status}
        </span>
      );
  }
}

// 20x4 LCD Screen Simulator Component
function LCDScreen({ page, prescription }: { page: number; prescription: Partial<Prescription> }) {
  const pad = (s: string) => s.slice(0, 20).padEnd(20, ' ');
  let l1 = '', l2 = '', l3 = '', l4 = '';

  if (page === 1) {
    l1 = pad(`* DOCTOR ADVICE 1/4 *`);
    l2 = pad(`Pt: ${prescription.patient_code || 'P001'}`);
    l3 = pad(`Rx: ${prescription.assessment || 'Under Review'}`);
    l4 = pad(`[NEXT:btn1 CONF:btn2]`);
  } else if (page === 2) {
    l1 = pad(`* MEDICINE 2/4 *`);
    l2 = pad(`Med: ${prescription.medication || 'None'}`);
    l3 = pad(`Dosage: ${prescription.dosage || 'None'}`);
    l4 = pad(`[NEXT:btn1 CONF:btn2]`);
  } else if (page === 3) {
    l1 = pad(`* SCHEDULE 3/4 *`);
    l2 = pad(`Freq: ${prescription.frequency || 'None'}`);
    l3 = pad(`Dur: ${prescription.duration || 'None'}`);
    l4 = pad(`[NEXT:btn1 CONF:btn2]`);
  } else if (page === 4) {
    l1 = pad(`* DIRECTIVE 4/4 *`);
    l2 = pad(`Ins:${(prescription.instructions || 'Follow regimen').slice(0, 16)}`);
    l3 = pad(`F/U:${prescription.follow_up_date || 'As scheduled'}`);
    l4 = pad(`PRESS CONFIRM TO ACK`);
  }

  return (
    <div className="bg-[#12281b] border-4 border-[#08150d] rounded-lg p-3 font-mono text-[#3df47b] shadow-inner select-none">
      <div className="text-[11px] leading-snug tracking-wider whitespace-pre">{l1}</div>
      <div className="text-[11px] leading-snug tracking-wider whitespace-pre">{l2}</div>
      <div className="text-[11px] leading-snug tracking-wider whitespace-pre">{l3}</div>
      <div className="text-[11px] leading-snug tracking-wider whitespace-pre">{l4}</div>
    </div>
  );
}

function CreatePrescriptionModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [selectedPatientId, setSelectedPatientId] = useState<string>('');
  const [form, setForm] = useState<PrescriptionCreate>({
    assessment: '',
    medication: '',
    dosage: '',
    frequency: '',
    duration: '',
    instructions: '',
    follow_up_date: '',
  });
  const [error, setError] = useState('');
  const [previewPage, setPreviewPage] = useState<number>(1);

  const { data: patientsData } = useQuery({
    queryKey: ['patients-list'],
    queryFn: () => api.getPatients({ size: 100 }),
  });

  const { data: devicesData } = useQuery({
    queryKey: ['devices-list'],
    queryFn: () => api.getDevices(),
  });

  const selectedPatient = useMemo(() => {
    return patientsData?.items.find(p => `${p.id}` === selectedPatientId || p.patient_id === selectedPatientId);
  }, [patientsData, selectedPatientId]);

  const assignedDevice = useMemo(() => {
    if (!selectedPatient || !devicesData) return null;
    return devicesData.find(d => d.patient_id === selectedPatient.id);
  }, [selectedPatient, devicesData]);

  const mutation = useMutation({
    mutationFn: (data: PrescriptionCreate) => {
      const pid = selectedPatient?.patient_id || selectedPatientId;
      return api.createPrescription(pid, {
        ...data,
        device_id: assignedDevice?.id || null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['prescriptions'] });
      onClose();
    },
    onError: (e: any) => {
      setError(e.response?.data?.detail || e.message || 'Failed to dispatch prescription');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId) {
      setError('Please select a patient.');
      return;
    }
    setError('');
    mutation.mutate(form);
  };

  return (
    <div className="fixed inset-0 bg-black/60 dark:bg-black/75 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="card w-full max-w-3xl my-8">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-charcoal-700">
          <div>
            <h2 className="text-slate-900 dark:text-slate-100 font-semibold text-lg flex items-center gap-2">
              <FileText className="w-5 h-5 text-cyan-600 dark:text-cyan-400" />
              Issue Doctor-to-Patient Directive
            </h2>
            <p className="text-slate-600 dark:text-slate-400 text-xs mt-0.5">
              Dispatched remotely to the rural patient&apos;s IoT device 20x4 LCD display.
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-600 dark:text-red-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Target Patient *</label>
              <select
                className="input"
                value={selectedPatientId}
                onChange={e => setSelectedPatientId(e.target.value)}
                required
              >
                <option value="">Select registered patient…</option>
                {patientsData?.items.map(p => (
                  <option key={p.id} value={p.patient_id}>
                    {p.patient_id} — {p.full_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="label">Connected IoT Device</label>
              <div className="input flex items-center justify-between bg-slate-50 dark:bg-charcoal-800/60 text-slate-700 dark:text-slate-300">
                <span className="text-xs truncate">{assignedDevice ? `${assignedDevice.device_id}${assignedDevice.description ? ` (${assignedDevice.description})` : ''}` : (selectedPatient ? 'No assigned device (Unlinked)' : 'Select patient first')}</span>
                <Radio className={`w-4 h-4 flex-shrink-0 ${assignedDevice ? 'text-emerald-500' : 'text-slate-400'}`} />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Clinical Assessment / Diagnosis *</label>
              <input
                className="input"
                placeholder="e.g. Mild Bradycardia / Viral Fever"
                value={form.assessment}
                onChange={e => setForm(f => ({ ...f, assessment: e.target.value }))}
                required
                maxLength={80}
              />
            </div>
            <div>
              <label className="label">Prescribed Medication *</label>
              <input
                className="input"
                placeholder="e.g. Paracetamol 500mg"
                value={form.medication}
                onChange={e => setForm(f => ({ ...f, medication: e.target.value }))}
                required
                maxLength={60}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="label">Dosage *</label>
              <input
                className="input"
                placeholder="e.g. 1 Tablet"
                value={form.dosage}
                onChange={e => setForm(f => ({ ...f, dosage: e.target.value }))}
                required
                maxLength={30}
              />
            </div>
            <div>
              <label className="label">Frequency *</label>
              <input
                className="input"
                placeholder="e.g. 3 times daily (8h)"
                value={form.frequency}
                onChange={e => setForm(f => ({ ...f, frequency: e.target.value }))}
                required
                maxLength={30}
              />
            </div>
            <div>
              <label className="label">Duration *</label>
              <input
                className="input"
                placeholder="e.g. 5 days"
                value={form.duration}
                onChange={e => setForm(f => ({ ...f, duration: e.target.value }))}
                required
                maxLength={30}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Special Instructions (Optional)</label>
              <input
                className="input"
                placeholder="e.g. Take after meal with plenty of water"
                value={form.instructions}
                onChange={e => setForm(f => ({ ...f, instructions: e.target.value }))}
                maxLength={100}
              />
            </div>
            <div>
              <label className="label">Follow-up Date (Optional)</label>
              <input
                className="input"
                type="date"
                value={form.follow_up_date}
                onChange={e => setForm(f => ({ ...f, follow_up_date: e.target.value }))}
              />
            </div>
          </div>

          {/* 20x4 LCD Preview */}
          <div className="pt-2">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                <Monitor className="w-3.5 h-3.5 text-emerald-500" />
                Live 20x4 LCD Display Simulation (Patient Device View)
              </span>
              <div className="flex gap-1">
                {[1, 2, 3, 4].map(p => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPreviewPage(p)}
                    className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors ${
                      previewPage === p
                        ? 'bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/40'
                        : 'bg-slate-100 dark:bg-charcoal-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                    }`}
                  >
                    Pg {p}
                  </button>
                ))}
              </div>
            </div>
            <LCDScreen
              page={previewPage}
              prescription={{
                ...form,
                patient_code: selectedPatient?.patient_id || 'P001',
              }}
            />
          </div>

          <div className="flex gap-3 pt-3 border-t border-slate-200 dark:border-charcoal-700">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary flex-1 flex items-center justify-center gap-2"
              disabled={mutation.isPending}
            >
              <Send className="w-4 h-4" />
              {mutation.isPending ? 'Transmitting…' : 'Transmit to Device'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PrescriptionDetailModal({
  prescription,
  onClose,
}: {
  prescription: Prescription;
  onClose: () => void;
}) {
  const [activePage, setActivePage] = useState<number>(1);

  return (
    <div className="fixed inset-0 bg-black/60 dark:bg-black/75 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="card w-full max-w-2xl my-8">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-charcoal-700">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-slate-900 dark:text-slate-100 font-semibold text-lg">Prescription #{prescription.id}</h2>
              <StatusBadge
                status={prescription.status}
                deliveredAt={prescription.delivered_at}
                acknowledgedAt={prescription.acknowledged_at}
              />
            </div>
            <p className="text-slate-600 dark:text-slate-400 text-xs mt-0.5">
              Transmitted for Patient {prescription.patient_code || prescription.patient_id} via Device {prescription.device_code || 'Unlinked'}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 dark:bg-charcoal-800/40 p-3 rounded-lg border border-slate-200 dark:border-charcoal-700">
            <div>
              <div className="text-[11px] text-slate-500 font-medium">PATIENT</div>
              <div className="text-xs text-slate-800 dark:text-slate-200 font-semibold mt-0.5">
                {prescription.patient_name || prescription.patient_code || `ID ${prescription.patient_id}`}
              </div>
            </div>
            <div>
              <div className="text-[11px] text-slate-500 font-medium">DEVICE</div>
              <div className="text-xs text-cyan-600 dark:text-cyan-400 font-mono mt-0.5">
                {prescription.device_code || 'ESP32-001'}
              </div>
            </div>
            <div>
              <div className="text-[11px] text-slate-500 font-medium">ISSUED AT</div>
              <div className="text-xs text-slate-700 dark:text-slate-300 mt-0.5">
                {format(new Date(prescription.created_at), 'MM/dd HH:mm')}
              </div>
            </div>
            <div>
              <div className="text-[11px] text-slate-500 font-medium">STATUS</div>
              <div className="text-xs font-semibold mt-0.5 text-slate-800 dark:text-slate-200">
                {prescription.status}
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <div className="p-3 bg-slate-50 dark:bg-charcoal-800/20 rounded-lg border border-slate-200 dark:border-charcoal-700/60">
              <div className="text-xs font-semibold text-cyan-600 dark:text-cyan-400 uppercase tracking-wider mb-1">Clinical Assessment</div>
              <div className="text-slate-900 dark:text-slate-100 text-sm font-medium">{prescription.assessment}</div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3 bg-slate-50 dark:bg-charcoal-800/20 rounded-lg border border-slate-200 dark:border-charcoal-700/60">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Medication</div>
                <div className="text-slate-900 dark:text-slate-100 text-sm">{prescription.medication}</div>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-charcoal-800/20 rounded-lg border border-slate-200 dark:border-charcoal-700/60">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Dosage</div>
                <div className="text-slate-900 dark:text-slate-100 text-sm">{prescription.dosage}</div>
              </div>
              <div className="p-3 bg-slate-50 dark:bg-charcoal-800/20 rounded-lg border border-slate-200 dark:border-charcoal-700/60">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Schedule</div>
                <div className="text-slate-900 dark:text-slate-100 text-sm">{prescription.frequency} ({prescription.duration})</div>
              </div>
            </div>

            {(prescription.instructions || prescription.follow_up_date) && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {prescription.instructions && (
                  <div className="p-3 bg-slate-50 dark:bg-charcoal-800/20 rounded-lg border border-slate-200 dark:border-charcoal-700/60">
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Instructions</div>
                    <div className="text-slate-800 dark:text-slate-200 text-xs">{prescription.instructions}</div>
                  </div>
                )}
                {prescription.follow_up_date && (
                  <div className="p-3 bg-slate-50 dark:bg-charcoal-800/20 rounded-lg border border-slate-200 dark:border-charcoal-700/60">
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Follow-up Date</div>
                    <div className="text-slate-800 dark:text-slate-200 text-xs font-mono">{prescription.follow_up_date}</div>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="p-3 bg-slate-50 dark:bg-charcoal-800/30 rounded-lg border border-slate-200 dark:border-charcoal-700">
            <div className="text-xs font-semibold text-slate-500 mb-2 uppercase">Telemetry Timeline</div>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between text-slate-700 dark:text-slate-300">
                <span>1. Issued by Doctor:</span>
                <span className="font-mono text-slate-500">{format(new Date(prescription.created_at), 'yyyy-MM-dd HH:mm:ss')}</span>
              </div>
              <div className="flex items-center justify-between text-slate-700 dark:text-slate-300">
                <span>2. Delivered to Device LCD:</span>
                <span className="font-mono">
                  {prescription.delivered_at ? (
                    <span className="text-cyan-600 dark:text-cyan-400 font-semibold">{format(new Date(prescription.delivered_at), 'yyyy-MM-dd HH:mm:ss')}</span>
                  ) : (
                    <span className="text-amber-600 dark:text-amber-400 italic">Awaiting device poll…</span>
                  )}
                </span>
              </div>
              <div className="flex items-center justify-between text-slate-700 dark:text-slate-300">
                <span>3. Patient Confirmed (Hardware Button):</span>
                <span className="font-mono">
                  {prescription.acknowledged_at ? (
                    <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{format(new Date(prescription.acknowledged_at), 'yyyy-MM-dd HH:mm:ss')}</span>
                  ) : (
                    <span className="text-slate-400 dark:text-slate-500 italic">Pending patient confirmation…</span>
                  )}
                </span>
              </div>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                <Monitor className="w-3.5 h-3.5 text-emerald-500" />
                20x4 LCD Display Simulator (Patient View)
              </span>
              <div className="flex gap-1">
                {[1, 2, 3, 4].map(p => (
                  <button
                    key={p}
                    onClick={() => setActivePage(p)}
                    className={`px-2.5 py-0.5 rounded text-[11px] font-mono transition-colors ${
                      activePage === p
                        ? 'bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/40'
                        : 'bg-slate-100 dark:bg-charcoal-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                    }`}
                  >
                    Page {p}
                  </button>
                ))}
              </div>
            </div>
            <LCDScreen page={activePage} prescription={prescription} />
          </div>

          <div className="pt-2 flex justify-end">
            <button className="btn-secondary text-xs" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PrescriptionsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('All');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedPrescription, setSelectedPrescription] = useState<Prescription | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['prescriptions', statusFilter],
    queryFn: () => api.getPrescriptions({
      status: statusFilter === 'All' ? undefined : statusFilter,
      size: 100,
    }),
    refetchInterval: 6000,
  });

  const prescriptions = data?.items ?? [];

  const filteredPrescriptions = useMemo(() => {
    if (!searchTerm) return prescriptions;
    const term = searchTerm.toLowerCase();
    return prescriptions.filter(p =>
      p.assessment.toLowerCase().includes(term) ||
      p.medication.toLowerCase().includes(term) ||
      (p.patient_code && p.patient_code.toLowerCase().includes(term)) ||
      (p.patient_name && p.patient_name.toLowerCase().includes(term)) ||
      (p.device_code && p.device_code.toLowerCase().includes(term))
    );
  }, [prescriptions, searchTerm]);

  const stats = useMemo(() => {
    return {
      total: prescriptions.length,
      pending: prescriptions.filter(p => p.status === 'Pending').length,
      delivered: prescriptions.filter(p => p.status === 'Delivered').length,
      acknowledged: prescriptions.filter(p => p.status === 'Acknowledged').length,
    };
  }, [prescriptions]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
            <FileText className="w-6 h-6 text-cyan-600 dark:text-cyan-400" />
            Doctor-to-Patient Prescriptions
          </h1>
          <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">
            Issue remote clinical directives delivered directly to the patient&apos;s IoT device LCD screen with hardware confirmation.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center gap-2 self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          Issue Prescription
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="stat-card">
          <div className="text-slate-500 text-xs font-medium">Total Issued</div>
          <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{stats.total}</div>
        </div>
        <div className="stat-card border-amber-500/20 bg-amber-500/10">
          <div className="text-amber-600 dark:text-amber-400 text-xs font-medium flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
            Pending Delivery
          </div>
          <div className="text-2xl font-bold text-amber-700 dark:text-amber-300 mt-1">{stats.pending}</div>
        </div>
        <div className="stat-card border-cyan-500/20 bg-cyan-500/10">
          <div className="text-cyan-600 dark:text-cyan-400 text-xs font-medium flex items-center gap-1.5">
            <Radio className="w-3.5 h-3.5 text-cyan-500" />
            Delivered to LCD
          </div>
          <div className="text-2xl font-bold text-cyan-700 dark:text-cyan-300 mt-1">{stats.delivered}</div>
        </div>
        <div className="stat-card border-emerald-500/20 bg-emerald-500/10">
          <div className="text-emerald-600 dark:text-emerald-400 text-xs font-medium flex items-center gap-1.5">
            <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
            Patient Acknowledged
          </div>
          <div className="text-2xl font-bold text-emerald-700 dark:text-emerald-300 mt-1">{stats.acknowledged}</div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-50 dark:bg-navy-900/60 p-3 rounded-lg border border-slate-200 dark:border-charcoal-700">
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            className="input pl-9 py-1.5 text-xs"
            placeholder="Search patient, medication, diagnosis…"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="flex gap-1 w-full sm:w-auto overflow-x-auto">
          {['All', 'Pending', 'Delivered', 'Acknowledged'].map(status => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                statusFilter === status
                  ? 'bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 border border-cyan-500/40'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-charcoal-800'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      <div className="card overflow-hidden p-0">
        {isLoading ? (
          <div className="text-center py-12 text-slate-500 text-sm">
            <Clock className="w-5 h-5 animate-spin mx-auto mb-2 text-cyan-500" />
            Loading prescriptions…
          </div>
        ) : filteredPrescriptions.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-sm">
            No prescriptions found. Click &quot;Issue Prescription&quot; to send clinical directives.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-charcoal-700 text-left bg-slate-100/70 dark:bg-navy-950/60">
                  <th className="py-3 px-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">ID / Date</th>
                  <th className="py-3 px-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Patient</th>
                  <th className="py-3 px-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Device</th>
                  <th className="py-3 px-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Assessment</th>
                  <th className="py-3 px-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Medication & Regimen</th>
                  <th className="py-3 px-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Status</th>
                  <th className="py-3 px-4 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-charcoal-800">
                {filteredPrescriptions.map(p => (
                  <tr key={p.id} className="hover:bg-slate-50 dark:hover:bg-charcoal-800/40 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-mono text-xs text-slate-800 dark:text-slate-300 font-semibold">#{p.id}</div>
                      <div className="text-[11px] text-slate-500">
                        {format(new Date(p.created_at), 'MM/dd HH:mm')}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-xs font-semibold text-slate-900 dark:text-slate-200">
                        {p.patient_name || p.patient_code || `P${p.patient_id}`}
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono">
                        {p.patient_code}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-xs text-cyan-600 dark:text-cyan-400">
                        {p.device_code || 'ESP32-001'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-xs text-slate-900 dark:text-slate-200 font-medium max-w-[200px] truncate" title={p.assessment}>
                        {p.assessment}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-xs text-slate-900 dark:text-slate-200 font-medium">
                        {p.medication}
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400">
                        {p.dosage} · {p.frequency} ({p.duration})
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge
                        status={p.status}
                        deliveredAt={p.delivered_at}
                        acknowledgedAt={p.acknowledged_at}
                      />
                      {p.acknowledged_at && (
                        <div className="text-[10px] text-emerald-600 dark:text-emerald-400/80 font-mono mt-0.5">
                          Ack: {format(new Date(p.acknowledged_at), 'HH:mm:ss')}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setSelectedPrescription(p)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded bg-slate-100 dark:bg-charcoal-700/60 hover:bg-cyan-500/20 text-slate-700 dark:text-slate-300 hover:text-cyan-600 dark:hover:text-cyan-300 border border-slate-300 dark:border-charcoal-600 transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        View & LCD
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showCreateModal && <CreatePrescriptionModal onClose={() => setShowCreateModal(false)} />}
      {selectedPrescription && (
        <PrescriptionDetailModal
          prescription={selectedPrescription}
          onClose={() => setSelectedPrescription(null)}
        />
      )}
    </div>
  );
}
