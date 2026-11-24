import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Heart, Droplets, Thermometer, User, Filter, AlertTriangle, CheckCircle, Activity, Clock
} from 'lucide-react';
import { api } from '../services/api';
import { format } from 'date-fns';

export default function VitalsHistoryPage() {
  const [selectedPatientId, setSelectedPatientId] = useState<string>('');

  // 1. Fetch patients list for selector
  const { data: patientsData } = useQuery({
    queryKey: ['patients-list-vitals'],
    queryFn: () => api.getPatients({ size: 100 }),
  });

  const patients = patientsData?.items ?? [];
  const currentPatient = selectedPatientId || (patients.length > 0 ? patients[0].patient_id : '');

  // 2. Fetch vitals for current selected patient
  const { data: vitalsData, isLoading } = useQuery({
    queryKey: ['patient-vitals-history', currentPatient],
    queryFn: () => api.getPatientVitals(currentPatient, 100),
    enabled: !!currentPatient,
    refetchInterval: 10000,
  });

  const vitals = vitalsData ?? [];

  // Categorize readings (preserving 0 BPM for clinical alert tracking)
  const hrReadings = vitals.filter(v => v.heart_rate_bpm !== null);
  const spo2Readings = vitals.filter(v => v.spo2_percent !== null && v.spo2_percent > 0);
  const tempReadings = vitals.filter(v => v.temperature_c !== null && v.temperature_c > -50);

  const latestHR = hrReadings[0]?.heart_rate_bpm;
  const latestSpO2 = spo2Readings[0]?.spo2_percent;
  const latestTemp = tempReadings[0]?.temperature_c;

  // Stale reading detection (> 60 minutes)
  const latestRecordedAt = vitals[0]?.recorded_at;
  const isStale = latestRecordedAt ? (Date.now() - new Date(latestRecordedAt).getTime()) > 60 * 60 * 1000 : false;

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-charcoal-700/60">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            <Heart className="w-5 h-5 text-rose-500" />
            Longitudinal Vitals Trends
          </h1>
          <p className="text-slate-400 text-xs mt-0.5">
            Physiological vital sign histories with clinical reference ranges for Heart Rate, SpO₂, and Temperature
          </p>
        </div>

        {/* Patient Selector */}
        <div className="flex items-center gap-2 bg-navy-900 border border-charcoal-700 rounded-lg px-3 py-1.5 self-start sm:self-auto shadow-sm">
          <User className="w-4 h-4 text-cyan-400" />
          <select
            className="bg-transparent text-xs text-slate-200 outline-none cursor-pointer font-medium"
            value={currentPatient}
            onChange={e => setSelectedPatientId(e.target.value)}
          >
            {patients.map(p => (
              <option key={p.patient_id} value={p.patient_id} className="bg-navy-900 text-slate-200">
                {p.patient_id} — {p.full_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Latest Vitals Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Heart Rate */}
        <div className="card border-rose-500/30 bg-rose-950/15 p-4.5 rounded-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-rose-400 text-xs font-semibold uppercase tracking-wider">
              <Heart className="w-4 h-4" />
              Heart Rate (MAX30102)
            </div>
            <span className="text-[11px] font-mono text-slate-400">Normal: 60–100 bpm</span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="text-3xl font-bold font-mono tracking-tight text-slate-100">
              {latestHR != null ? latestHR.toFixed(0) : '—'}
            </span>
            <span className="text-xs text-slate-400 font-mono">BPM</span>
          </div>
          <div className="mt-2 text-xs">
            {latestHR == null ? (
              <span className="text-slate-500">No data received</span>
            ) : latestHR === 0 ? (
              <span className="text-rose-400 font-bold flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Alert: 0 BPM (Probe detachment / Asystole)
              </span>
            ) : latestHR < 60 ? (
              <span className="text-amber-400 font-medium flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Bradycardia alert (&lt; 60 bpm)
              </span>
            ) : latestHR > 100 ? (
              <span className="text-rose-400 font-medium flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Tachycardia alert (&gt; 100 bpm)
              </span>
            ) : (
              <span className="text-emerald-400 flex items-center gap-1 font-medium">
                <CheckCircle className="w-3.5 h-3.5" /> Normal sinus rhythm range
              </span>
            )}
          </div>
        </div>

        {/* SpO2 */}
        <div className="card border-cyan-500/30 bg-cyan-950/15 p-4.5 rounded-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-cyan-400 text-xs font-semibold uppercase tracking-wider">
              <Droplets className="w-4 h-4" />
              Blood Oxygen (SpO₂)
            </div>
            <span className="text-[11px] font-mono text-slate-400">Normal: ≥ 95%</span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="text-3xl font-bold font-mono tracking-tight text-slate-100">
              {latestSpO2 != null ? `${latestSpO2.toFixed(1)}` : '—'}
            </span>
            <span className="text-xs text-slate-400 font-mono">%</span>
          </div>
          <div className="mt-2 text-xs">
            {latestSpO2 == null ? (
              <span className="text-slate-500">No data received</span>
            ) : latestSpO2 < 90 ? (
              <span className="text-rose-400 font-bold flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Severe Hypoxemia (&lt; 90%)
              </span>
            ) : latestSpO2 < 95 ? (
              <span className="text-amber-400 font-medium flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Borderline Saturation (90–94%)
              </span>
            ) : (
              <span className="text-emerald-400 flex items-center gap-1 font-medium">
                <CheckCircle className="w-3.5 h-3.5" /> Normal saturation level
              </span>
            )}
          </div>
        </div>

        {/* Temperature */}
        <div className="card border-amber-500/30 bg-amber-950/15 p-4.5 rounded-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-amber-400 text-xs font-semibold uppercase tracking-wider">
              <Thermometer className="w-4 h-4" />
              Temperature (DS18B20)
            </div>
            <span className="text-[11px] font-mono text-slate-400">Normal: 36.1–37.2°C</span>
          </div>
          <div className="mt-3 flex items-baseline gap-1.5">
            <span className="text-3xl font-bold font-mono tracking-tight text-slate-100">
              {latestTemp != null ? `${latestTemp.toFixed(1)}` : '—'}
            </span>
            <span className="text-xs text-slate-400 font-mono">°C</span>
          </div>
          <div className="mt-2 text-xs">
            {latestTemp == null ? (
              <span className="text-slate-500">Sensor Disconnected</span>
            ) : latestTemp >= 38.0 ? (
              <span className="text-rose-400 font-bold flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Pyrexia High Fever (&ge; 38.0°C)
              </span>
            ) : latestTemp > 37.2 ? (
              <span className="text-amber-400 font-medium flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Low-grade Elevation (37.3–37.9°C)
              </span>
            ) : latestTemp < 35.5 ? (
              <span className="text-sky-400 font-medium flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Hypothermia Risk (&lt; 35.5°C)
              </span>
            ) : (
              <span className="text-emerald-400 flex items-center gap-1 font-medium">
                <CheckCircle className="w-3.5 h-3.5" /> Normothermic baseline
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Historical Telemetry Logs Table Card */}
      <div className="card p-0 overflow-hidden">
        <div className="p-4 border-b border-charcoal-700/60 bg-navy-950/40 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Clock className="w-4 h-4 text-cyan-400" />
            Telemetry Reading Log ({vitals.length} records)
          </h2>
          <span className="text-[11px] font-mono text-slate-500">Auto-refreshing every 10s</span>
        </div>

        {isLoading ? (
          <div className="text-slate-500 text-xs text-center py-16 flex items-center justify-center gap-2">
            <Activity className="w-4 h-4 animate-pulse text-cyan-400" />
            Loading historical vitals records…
          </div>
        ) : vitals.length === 0 ? (
          <div className="text-center py-16 text-slate-500 text-xs">
            No telemetry records logged for this patient yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-charcoal-700/60 text-slate-400 bg-navy-950/30">
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Timestamp (UTC)</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Heart Rate</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">SpO₂</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Temperature</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Ingest Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal-800/60">
                {vitals.map(v => {
                  const isCritical =
                    v.heart_rate_bpm === 0 ||
                    (v.spo2_percent !== null && v.spo2_percent < 90) ||
                    (v.temperature_c !== null && v.temperature_c >= 38.5);

                  return (
                    <tr
                      key={v.id}
                      className={`hover:bg-charcoal-800/30 transition-colors ${
                        isCritical ? 'bg-rose-950/15' : ''
                      }`}
                    >
                      <td className="px-5 py-3 font-mono text-slate-400">
                        {format(new Date(v.recorded_at), 'yyyy-MM-dd HH:mm:ss')}
                      </td>
                      <td className="px-5 py-3">
                        {v.heart_rate_bpm != null ? (
                          <span
                            className={`font-mono font-semibold ${
                              v.heart_rate_bpm === 0
                                ? 'text-rose-400 font-bold'
                                : v.heart_rate_bpm < 60 || v.heart_rate_bpm > 100
                                ? 'text-amber-400'
                                : 'text-slate-200'
                            }`}
                          >
                            {v.heart_rate_bpm.toFixed(0)} BPM
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        {v.spo2_percent != null ? (
                          <span
                            className={`font-mono font-semibold ${
                              v.spo2_percent < 90
                                ? 'text-rose-400 font-bold'
                                : v.spo2_percent < 95
                                ? 'text-amber-400'
                                : 'text-slate-200'
                            }`}
                          >
                            {v.spo2_percent.toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        {v.temperature_c != null ? (
                          <span
                            className={`font-mono font-semibold ${
                              v.temperature_c >= 38.0
                                ? 'text-rose-400 font-bold'
                                : v.temperature_c > 37.2
                                ? 'text-amber-400'
                                : 'text-slate-200'
                            }`}
                          >
                            {v.temperature_c.toFixed(1)}°C
                          </span>
                        ) : (
                          <span className="text-slate-500 italic">Disconnected</span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        {v.is_simulated ? (
                          <span className="badge-blue text-[10px]">Simulated Stream</span>
                        ) : (
                          <span className="badge-green text-[10px]">Physical Edge Node</span>
                        )}
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
