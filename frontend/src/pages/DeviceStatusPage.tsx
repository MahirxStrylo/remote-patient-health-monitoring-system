import { useQuery } from '@tanstack/react-query';
import {
  Cpu, CheckCircle, Clock, WifiOff, RefreshCw, Key, AlertCircle, HardDrive, Radio, Activity
} from 'lucide-react';
import { api } from '../services/api';
import { differenceInMinutes, formatDistanceToNow } from 'date-fns';

export default function DeviceStatusPage() {
  const { data: devices, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['devices-status'],
    queryFn: api.getDevices,
    refetchInterval: 15000,
  });

  const allDevices = devices ?? [];
  const onlineCount = allDevices.filter(d => d.is_active && d.last_seen && differenceInMinutes(new Date(), new Date(d.last_seen)) < 10).length;
  const staleCount = allDevices.filter(d => d.is_active && d.last_seen && differenceInMinutes(new Date(), new Date(d.last_seen)) >= 10 && differenceInMinutes(new Date(), new Date(d.last_seen)) < 60).length;
  const offlineCount = allDevices.filter(d => !d.is_active || !d.last_seen || differenceInMinutes(new Date(), new Date(d.last_seen)) >= 60).length;

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
            <Cpu className="w-6 h-6 text-cyan-600 dark:text-cyan-400" />
            Device Telemetry & Health
          </h1>
          <p className="text-slate-600 dark:text-slate-400 text-sm mt-1">
            Real-time heartbeat monitoring, firmware versions, and cellular gateway connection state
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="btn-secondary text-sm flex items-center gap-2 self-start sm:self-auto"
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin text-cyan-500' : ''}`} />
          Refresh Status
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card bg-emerald-500/10 border-emerald-500/30 dark:bg-emerald-950/20 dark:border-emerald-800/40 p-4">
          <div className="flex items-center justify-between">
            <span className="text-slate-700 dark:text-slate-300 text-sm font-medium">Reporting (Online)</span>
            <CheckCircle className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div className="text-3xl font-bold text-emerald-600 dark:text-emerald-400 mt-2 font-mono">{onlineCount}</div>
          <div className="text-xs text-emerald-700/80 dark:text-emerald-400/80 mt-1">Heartbeat within last 10 minutes</div>
        </div>

        <div className="card bg-amber-500/10 border-amber-500/30 dark:bg-amber-950/20 dark:border-amber-800/40 p-4">
          <div className="flex items-center justify-between">
            <span className="text-slate-700 dark:text-slate-300 text-sm font-medium">Delayed (Stale)</span>
            <Clock className="w-5 h-5 text-amber-600 dark:text-amber-400" />
          </div>
          <div className="text-3xl font-bold text-amber-600 dark:text-amber-400 mt-2 font-mono">{staleCount}</div>
          <div className="text-xs text-amber-700/80 dark:text-amber-400/80 mt-1">No transmission for 10–60 min</div>
        </div>

        <div className="card bg-rose-500/10 border-rose-500/30 dark:bg-rose-950/20 dark:border-rose-800/40 p-4">
          <div className="flex items-center justify-between">
            <span className="text-slate-700 dark:text-slate-300 text-sm font-medium">Offline / Inactive</span>
            <WifiOff className="w-5 h-5 text-rose-600 dark:text-rose-400" />
          </div>
          <div className="text-3xl font-bold text-rose-600 dark:text-rose-400 mt-2 font-mono">{offlineCount}</div>
          <div className="text-xs text-rose-700/80 dark:text-rose-400/80 mt-1">&gt; 1 hour or revoked API key</div>
        </div>
      </div>

      {/* Grid of Devices */}
      <div className="card p-0 overflow-hidden">
        <div className="p-4 border-b border-slate-200 dark:border-charcoal-700 bg-slate-50 dark:bg-navy-900/40 flex items-center justify-between">
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">Monitored Hardware Endpoints</span>
          <span className="text-xs text-slate-500 font-mono">{allDevices.length} registered</span>
        </div>

        {isLoading ? (
          <div className="text-slate-500 text-sm text-center py-16 flex items-center justify-center gap-2">
            <Cpu className="w-5 h-5 animate-pulse text-cyan-500" />
            Scanning device endpoints…
          </div>
        ) : allDevices.length === 0 ? (
          <div className="text-center py-16">
            <AlertCircle className="w-10 h-10 text-slate-400 dark:text-slate-600 mx-auto mb-3" />
            <div className="text-slate-600 dark:text-slate-400 font-medium text-sm">No hardware endpoints detected.</div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-slate-200 dark:border-charcoal-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase bg-slate-100/80 dark:bg-navy-950/60">
                  <th className="px-5 py-3.5">Device Identifier</th>
                  <th className="px-5 py-3.5">Connection State</th>
                  <th className="px-5 py-3.5">Firmware</th>
                  <th className="px-5 py-3.5">Key Prefix</th>
                  <th className="px-5 py-3.5">Last Transmission</th>
                  <th className="px-5 py-3.5">Assigned Patient</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-charcoal-800">
                {allDevices.map(d => {
                  const mins = d.last_seen ? differenceInMinutes(new Date(), new Date(d.last_seen)) : null;
                  const isOnline = d.is_active && mins !== null && mins < 10;
                  const isStale = d.is_active && mins !== null && mins >= 10 && mins < 60;

                  return (
                    <tr key={d.device_id} className="hover:bg-slate-50 dark:hover:bg-charcoal-800/30 transition-colors">
                      <td className="px-5 py-4">
                        <div className="font-mono text-sm text-cyan-600 dark:text-cyan-400 font-medium">{d.device_id}</div>
                        {d.description && <div className="text-slate-500 text-xs mt-0.5">{d.description}</div>}
                      </td>

                      <td className="px-5 py-4">
                        {isOnline ? (
                          <span className="badge-green inline-flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            Live (GPRS)
                          </span>
                        ) : isStale ? (
                          <span className="badge-yellow inline-flex items-center gap-1.5">
                            <Clock className="w-3 h-3" />
                            Stale ({mins}m ago)
                          </span>
                        ) : (
                          <span className="badge-red inline-flex items-center gap-1.5">
                            <WifiOff className="w-3 h-3" />
                            Offline
                          </span>
                        )}
                        {!d.is_active && (
                          <span className="ml-2 badge-gray text-xs">Revoked</span>
                        )}
                      </td>

                      <td className="px-5 py-4 font-mono text-xs text-slate-700 dark:text-slate-300">
                        {d.firmware_version ?? 'ESP32-FW-1.0.4'}
                      </td>

                      <td className="px-5 py-4 font-mono text-xs text-slate-500 dark:text-slate-400">
                        {d.api_key_prefix ? (
                          <span className="flex items-center gap-1 text-slate-700 dark:text-slate-300">
                            <Key className="w-3 h-3 text-cyan-500" />
                            {d.api_key_prefix}
                          </span>
                        ) : (
                          <span className="text-slate-400 dark:text-slate-600">Legacy Key</span>
                        )}
                      </td>

                      <td className="px-5 py-4 text-xs">
                        <div className="text-slate-900 dark:text-slate-200">
                          {d.last_seen ? formatDistanceToNow(new Date(d.last_seen), { addSuffix: true }) : 'Never'}
                        </div>
                        {d.last_batch_id && (
                          <div className="font-mono text-slate-500 text-[11px] mt-0.5 truncate max-w-[180px]">
                            {d.last_batch_id}
                          </div>
                        )}
                      </td>

                      <td className="px-5 py-4 text-sm text-slate-700 dark:text-slate-300">
                        {d.patient_id ? (
                          <span className="text-cyan-600 dark:text-cyan-400 font-mono text-xs">Patient DB #{d.patient_id}</span>
                        ) : (
                          <span className="text-slate-400 dark:text-slate-600 text-xs italic">Unassigned</span>
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

      {/* Cellular Relay Protocol Guide */}
      <div className="card border-slate-200 dark:border-charcoal-700 bg-slate-50/60 dark:bg-navy-900/30">
        <h2 className="section-title flex items-center gap-2">
          <HardDrive className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
          SIM800L 2G/GPRS Connectivity Specifications
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-3 text-xs text-slate-600 dark:text-slate-400">
          <div className="space-y-1">
            <span className="font-semibold text-slate-800 dark:text-slate-200">Baud Rate & Modem:</span>
            <p>SIM800L UART communicating at 9600–115200 baud via HardwareSerial2 on ESP32 (GPIO16 RX, GPIO17 TX).</p>
          </div>
          <div className="space-y-1">
            <span className="font-semibold text-slate-800 dark:text-slate-200">TLS Encryption Note:</span>
            <p>SIM800 firmware only supports SSLv3/TLS1.0. Direct cloud HTTPS is proxied through our rural clinic gateway relay or reverse proxy.</p>
          </div>
          <div className="space-y-1">
            <span className="font-semibold text-slate-800 dark:text-slate-200">Idempotency Retry:</span>
            <p>ESP32 retains unacknowledged batch in flash and retransmits upon signal recovery with unchanged batch UUID.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
