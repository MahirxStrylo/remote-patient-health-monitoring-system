import { useQuery } from '@tanstack/react-query';
import {
  Settings, Server, Database, Info, Activity, Radio, Cpu, Shield, Heart, Thermometer, Droplet
} from 'lucide-react';
import { api } from '../services/api';

export default function SettingsPage() {
  const { data: settings, isLoading } = useQuery({ queryKey: ['settings'], queryFn: api.getSettings });
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: api.getHealth, refetchInterval: 60_000 });

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
          <Settings className="w-6 h-6 text-cyan-600 dark:text-cyan-400" />
          System Settings & Clinical Configuration
        </h1>
        <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">
          Server runtime parameters, clinical alarm thresholds, and IoT hardware sensor profile
        </p>
      </div>

      {/* Grid of Settings Categories */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Server & Runtime Environment */}
        <div className="card space-y-4">
          <h2 className="section-title flex items-center gap-2">
            <Server className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
            Server Runtime & Environment
          </h2>
          {isLoading ? (
            <div className="text-slate-500 text-sm py-4">Loading server parameters…</div>
          ) : (
            <div className="space-y-2.5 text-xs">
              {[
                { label: 'Application Version', value: settings?.app_version ?? '2.0.0-PROD' },
                { label: 'Backend Framework', value: 'FastAPI (Python 3.12+ ASGI)' },
                { label: 'Database Health', value: health?.database === 'connected' ? 'Connected (Operational)' : 'Unavailable' },
                { label: 'Server Time (UTC)', value: settings?.server_time ? new Date(settings.server_time).toUTCString() : '—' },
                { label: 'Total Ingested Records', value: settings?.total_records?.toLocaleString() ?? '—' },
                { label: 'Max ECG Samples / Batch', value: `${settings?.max_ecg_samples_per_batch ?? 10000} samples` },
                { label: 'Stale Telemetry Threshold', value: `${settings?.stale_reading_threshold_minutes ?? 15} minutes` },
              ].map(({ label, value }) => (
                <div key={label} className="flex items-center justify-between py-1.5 border-b border-slate-200 dark:border-charcoal-700/60 last:border-0">
                  <span className="text-slate-600 dark:text-slate-400 font-medium">{label}</span>
                  <span className="text-slate-900 dark:text-slate-200 font-mono font-medium">{value}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Clinical Alert Boundaries */}
        <div className="card space-y-4">
          <h2 className="section-title flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            Clinical Vital Reference Ranges
          </h2>
          <div className="space-y-3 text-xs">
            <div className="p-3 rounded-lg border border-slate-200 dark:border-charcoal-700 bg-slate-50/70 dark:bg-navy-900/40">
              <div className="flex items-center justify-between font-semibold text-slate-800 dark:text-slate-200 mb-1">
                <span className="flex items-center gap-1.5 text-rose-600 dark:text-rose-400">
                  <Heart className="w-3.5 h-3.5" />
                  Heart Rate (BPM)
                </span>
                <span className="font-mono text-cyan-600 dark:text-cyan-400">60 – 100 BPM</span>
              </div>
              <p className="text-slate-600 dark:text-slate-400 text-[11px]">
                Values &lt; 60 trigger <strong>Bradycardia</strong> alarm. Values &gt; 100 trigger <strong>Tachycardia</strong> alarm.
              </p>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 dark:border-charcoal-700 bg-slate-50/70 dark:bg-navy-900/40">
              <div className="flex items-center justify-between font-semibold text-slate-800 dark:text-slate-200 mb-1">
                <span className="flex items-center gap-1.5 text-cyan-600 dark:text-cyan-400">
                  <Droplet className="w-3.5 h-3.5" />
                  Blood Oxygen Saturation (SpO₂)
                </span>
                <span className="font-mono text-cyan-600 dark:text-cyan-400">&ge; 95%</span>
              </div>
              <p className="text-slate-600 dark:text-slate-400 text-[11px]">
                Values &lt; 95% trigger <strong>Hypoxia Warning</strong>. Values &lt; 90% trigger <strong>Critical Hypoxemia</strong>.
              </p>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 dark:border-charcoal-700 bg-slate-50/70 dark:bg-navy-900/40">
              <div className="flex items-center justify-between font-semibold text-slate-800 dark:text-slate-200 mb-1">
                <span className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                  <Thermometer className="w-3.5 h-3.5" />
                  Body Temperature (°C)
                </span>
                <span className="font-mono text-cyan-600 dark:text-cyan-400">36.1 – 37.2 °C</span>
              </div>
              <p className="text-slate-600 dark:text-slate-400 text-[11px]">
                Values &gt; 37.5°C trigger <strong>Fever Alert</strong>. Values &lt; 35.0°C trigger <strong>Hypothermia</strong>.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Hardware Sensor & SIM800L Specifications */}
      <div className="card space-y-4">
        <h2 className="section-title flex items-center gap-2">
          <Cpu className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          Hardware Acquisition & Cellular Telemetry Profile
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="p-3.5 rounded-lg border border-slate-200 dark:border-charcoal-700 bg-slate-50/50 dark:bg-navy-900/30">
            <div className="font-semibold text-slate-800 dark:text-slate-200 mb-1">AD8232 ECG Sensor</div>
            <ul className="text-slate-600 dark:text-slate-400 space-y-1 text-[11px]">
              <li>• Sampling rate: <strong>250 Hz</strong> (4 ms interval)</li>
              <li>• Unit: <strong>ADC Counts</strong> (0–4095, 12-bit)</li>
              <li>• Filter: 0.5–40 Hz 4th-order SOS Butterworth</li>
              <li>• Leads: RA, LA, RL (Right Leg Drive)</li>
            </ul>
          </div>

          <div className="p-3.5 rounded-lg border border-slate-200 dark:border-charcoal-700 bg-slate-50/50 dark:bg-navy-900/30">
            <div className="font-semibold text-slate-800 dark:text-slate-200 mb-1">MAX30102 & DS18B20</div>
            <ul className="text-slate-600 dark:text-slate-400 space-y-1 text-[11px]">
              <li>• SpO₂ calculation: Red & IR ratio-of-ratios</li>
              <li>• HR detection: Peak-to-peak interval</li>
              <li>• Temp bus: 1-Wire Dallas on GPIO 4</li>
              <li>• Disconnect detection: null returned on open</li>
            </ul>
          </div>

          <div className="p-3.5 rounded-lg border border-slate-200 dark:border-charcoal-700 bg-slate-50/50 dark:bg-navy-900/30">
            <div className="font-semibold text-slate-800 dark:text-slate-200 mb-1">SIM800L GPRS & Auth</div>
            <ul className="text-slate-600 dark:text-slate-400 space-y-1 text-[11px]">
              <li>• Connection: Quad-band GSM 850/900/1800/1900</li>
              <li>• Protocol: HTTP POST /api/v1/ingest</li>
              <li>• Security: X-Device-API-Key with SHA256/Bcrypt</li>
              <li>• Reliability: Flash batch buffer & auto-retry</li>
            </ul>
          </div>
        </div>
      </div>

      {/* University Research Prototype Disclaimer */}
      <div className="card border-amber-500/30 bg-amber-500/10 dark:border-amber-800/30 dark:bg-amber-900/10">
        <h2 className="section-title flex items-center gap-2 text-amber-700 dark:text-amber-400">
          <Info className="w-4 h-4" />
          University Engineering Prototype Disclaimer
        </h2>
        <p className="text-amber-800/90 dark:text-amber-300/80 text-xs leading-relaxed mt-2">
          This system is an <strong>educational engineering prototype</strong> developed for university research, demonstration, and evaluation of low-cost rural telehealth telemetry. It is not an FDA-cleared, CE-marked, or certified medical device. All measurements, ECG waveforms, and automated classification flags are for academic validation only and <strong>must not be used</strong> for clinical diagnosis, life-critical decision making, or emergency patient monitoring.
        </p>
      </div>
    </div>
  );
}
