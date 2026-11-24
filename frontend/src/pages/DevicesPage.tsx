import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Cpu, Plus, AlertCircle, X, CheckCircle, Clock, WifiOff, Copy, Eye, EyeOff, RotateCw, ShieldAlert, Key, Radio
} from 'lucide-react';
import { api } from '../services/api';
import type { Device, DeviceCreate, DeviceKeyRotateResponse } from '../types';
import { formatDistanceToNow, differenceInMinutes } from 'date-fns';

function DeviceStatusBadge({ lastSeen, isActive }: { lastSeen: string | null; isActive: boolean }) {
  if (!isActive) return <span className="badge-red"><ShieldAlert className="w-3 h-3" />Revoked</span>;
  if (!lastSeen) return <span className="badge-gray"><WifiOff className="w-3 h-3" />Never Seen</span>;
  const mins = differenceInMinutes(new Date(), new Date(lastSeen));
  if (mins < 10) return (
    <span className="badge-green">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
      Online
    </span>
  );
  if (mins < 60) return <span className="badge-yellow"><Clock className="w-3 h-3" />Stale (&lt;60m)</span>;
  return <span className="badge-red"><WifiOff className="w-3 h-3" />Offline</span>;
}

function ApiKeyDisplay({ apiKey, title = "New Device API Key" }: { apiKey: string; title?: string }) {
  const [visible, setVisible] = useState(false);
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };
  return (
    <div className="bg-navy-950/90 border border-charcoal-700 rounded-xl p-4 mt-3">
      <div className="text-xs text-amber-300 font-semibold mb-2 flex items-center gap-1.5">
        <Key className="w-4 h-4 text-amber-400" />
        {title} — Copy into ESP32 firmware now. It cannot be shown again.
      </div>
      <div className="flex items-center gap-2">
        <code className="flex-1 font-mono text-xs text-emerald-400 break-all bg-navy-900 px-3 py-2 rounded-lg border border-charcoal-800">
          {visible ? apiKey : '•'.repeat(40)}
        </code>
        <button
          onClick={() => setVisible(v => !v)}
          className="btn-secondary text-xs p-2"
          title={visible ? 'Hide secret' : 'Reveal secret'}
        >
          {visible ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
        </button>
        <button
          onClick={copy}
          className="btn-primary text-xs px-3 py-2"
          title="Copy key"
        >
          <Copy className="w-3.5 h-3.5" />
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      {copied && <div className="text-xs text-emerald-400 mt-2 font-mono">✓ Secret copied to clipboard successfully!</div>}
    </div>
  );
}

function AddDeviceModal({ onClose, onCreated }: { onClose: () => void; onCreated: (d: Device) => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<DeviceCreate>({ device_id: '' });
  const [error, setError] = useState('');

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const mutation = useMutation({
    mutationFn: (data: DeviceCreate) => api.createDevice(data),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['devices'] });
      onCreated(d);
    },
    onError: (e: any) => setError(e.response?.data?.detail || e.message || 'Failed to create device.'),
  });

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-md shadow-2xl border border-charcoal-700/80 bg-navy-900/95">
        <div className="flex items-center justify-between pb-3.5 mb-4 border-b border-charcoal-700/60">
          <div>
            <h2 className="text-slate-100 font-semibold text-base flex items-center gap-2">
              <Cpu className="w-4 h-4 text-cyan-400" />
              Provision Edge IoT Device
            </h2>
            <p className="text-slate-400 text-xs mt-0.5">Generates cryptographic device identity and API key.</p>
          </div>
          <button onClick={onClose} className="p-1 rounded text-slate-400 hover:text-slate-200">
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
            <label className="label">Device Hardware Identifier *</label>
            <input
              className="input font-mono"
              placeholder="e.g. ESP32-002"
              value={form.device_id}
              onChange={e => setForm(f => ({ ...f, device_id: e.target.value.toUpperCase() }))}
              required
            />
            <span className="text-[10px] text-slate-500 mt-1 block">Must match `DEVICE_ID` defined in ESP32 firmware.</span>
          </div>

          <div>
            <label className="label">Location / Deployment Note</label>
            <input
              className="input"
              placeholder="e.g. Ward 2, Rural Health Post Sylhet"
              onChange={e => setForm(f => ({ ...f, description: e.target.value || undefined }))}
            />
          </div>

          <div className="flex gap-3 pt-3 border-t border-charcoal-700/60">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancel</button>
            <button
              type="submit"
              className="btn-primary flex-1"
              disabled={mutation.isPending || !form.device_id.trim()}
            >
              {mutation.isPending ? 'Provisioning…' : 'Generate Identity'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function DevicesPage() {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [newDeviceKey, setNewDeviceKey] = useState<{ deviceId: string; plainKey: string } | null>(null);
  const [rotatedKey, setRotatedKey] = useState<DeviceKeyRotateResponse | null>(null);

  const { data: devices, isLoading } = useQuery({
    queryKey: ['devices'],
    queryFn: () => api.getDevices(),
  });

  const rotateMutation = useMutation({
    mutationFn: (deviceId: string) => api.rotateDeviceKey(deviceId),
    onSuccess: (data) => {
      setRotatedKey(data);
      qc.invalidateQueries({ queryKey: ['devices'] });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (deviceId: string) => api.revokeDeviceKey(deviceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['devices'] });
    },
  });

  const handleRotate = (d: Device) => {
    if (confirm(`Rotate API key for ${d.device_id}? The previous key will stop working immediately.`)) {
      rotateMutation.mutate(d.device_id);
    }
  };

  const handleRevoke = (d: Device) => {
    if (confirm(`Revoke API key for ${d.device_id}? All telemetry ingestion from this device will be blocked.`)) {
      revokeMutation.mutate(d.device_id);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-charcoal-700/60">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            <Cpu className="w-5 h-5 text-cyan-400" />
            Edge Device Registry
          </h1>
          <p className="text-slate-400 text-xs mt-0.5">
            Cryptographic key management, node heartbeat status, and cellular gateway authentication
          </p>
        </div>

        <button className="btn-primary text-xs self-start sm:self-auto" onClick={() => setShowAdd(true)}>
          <Plus className="w-4 h-4" />
          Provision New Node
        </button>
      </div>

      {/* Secret Display Banner (Newly Provisioned Key) */}
      {newDeviceKey && (
        <div className="p-4 rounded-xl border border-emerald-500/40 bg-emerald-950/20 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-xs text-emerald-300">
              ✓ Hardware Node {newDeviceKey.deviceId} Provisioned
            </span>
            <button onClick={() => setNewDeviceKey(null)} className="text-slate-400 hover:text-slate-200">
              <X className="w-4 h-4" />
            </button>
          </div>
          <ApiKeyDisplay apiKey={newDeviceKey.plainKey} title={`Device ${newDeviceKey.deviceId} Secret`} />
        </div>
      )}

      {/* Secret Display Banner (Rotated Key) */}
      {rotatedKey && (
        <div className="p-4 rounded-xl border border-cyan-500/40 bg-cyan-950/20 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-xs text-cyan-300">
              ✓ API Key Rotated for {rotatedKey.device_id}
            </span>
            <button onClick={() => setRotatedKey(null)} className="text-slate-400 hover:text-slate-200">
              <X className="w-4 h-4" />
            </button>
          </div>
          <ApiKeyDisplay apiKey={rotatedKey.plain_api_key} title="New Rotated API Key" />
        </div>
      )}

      {/* Devices Table Card */}
      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="text-slate-500 text-xs text-center py-16 flex items-center justify-center gap-2">
            <Cpu className="w-4 h-4 animate-pulse text-cyan-400" />
            Scanning edge hardware nodes…
          </div>
        ) : !devices?.length ? (
          <div className="text-center py-16 px-4">
            <Cpu className="w-10 h-10 text-slate-700 mx-auto mb-3" />
            <div className="text-slate-300 font-medium text-sm">No hardware devices provisioned yet.</div>
            <p className="text-slate-500 text-xs mt-1">Register your first ESP32 node to generate an ingestion key.</p>
            <button className="btn-primary text-xs mt-4" onClick={() => setShowAdd(true)}>
              Provision First Device
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-charcoal-700/60 bg-navy-950/40 text-slate-400">
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Device ID</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">Heartbeat</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider">API Key Index</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider hidden md:table-cell">Assigned Patient</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider hidden lg:table-cell">Last Seen</th>
                  <th className="px-5 py-3 font-semibold uppercase tracking-wider text-right">Security Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal-800/60">
                {devices.map(d => (
                  <tr key={d.id} className="hover:bg-charcoal-800/30 transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="font-mono font-semibold text-cyan-400 text-xs">{d.device_id}</div>
                      {d.description && <div className="text-slate-400 text-[11px] mt-0.5">{d.description}</div>}
                    </td>

                    <td className="px-5 py-3.5">
                      <DeviceStatusBadge lastSeen={d.last_seen} isActive={d.is_active} />
                    </td>

                    <td className="px-5 py-3.5 font-mono text-xs">
                      {d.api_key_prefix ? (
                        <span className="flex items-center gap-1.5 text-slate-300">
                          <Key className="w-3.5 h-3.5 text-cyan-400" />
                          {d.api_key_prefix}…
                        </span>
                      ) : (
                        <span className="text-slate-500">Legacy Hash</span>
                      )}
                    </td>

                    <td className="px-5 py-3.5 text-slate-300 hidden md:table-cell">
                      {d.patient_id ? (
                        <span className="font-mono text-cyan-400 font-medium">Patient #{d.patient_id}</span>
                      ) : (
                        <span className="text-slate-500 italic">Unassigned</span>
                      )}
                    </td>

                    <td className="px-5 py-3.5 text-slate-400 text-[11px] hidden lg:table-cell font-mono">
                      {d.last_seen ? formatDistanceToNow(new Date(d.last_seen), { addSuffix: true }) : 'Never'}
                    </td>

                    <td className="px-5 py-3.5 text-right space-x-2">
                      <button
                        onClick={() => handleRotate(d)}
                        className="btn-secondary text-xs py-1 px-2.5 inline-flex items-center gap-1"
                        title="Rotate device secret"
                      >
                        <RotateCw className="w-3 h-3 text-cyan-400" />
                        Rotate
                      </button>

                      {d.is_active && (
                        <button
                          onClick={() => handleRevoke(d)}
                          className="btn-secondary text-xs py-1 px-2.5 inline-flex items-center gap-1 text-rose-400 hover:text-rose-300 border-rose-900/40 hover:bg-rose-950/20"
                          title="Revoke device access"
                        >
                          <ShieldAlert className="w-3 h-3" />
                          Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showAdd && (
        <AddDeviceModal
          onClose={() => setShowAdd(false)}
          onCreated={d => {
            if (d.plain_api_key) {
              setNewDeviceKey({ deviceId: d.device_id, plainKey: d.plain_api_key });
            }
            setShowAdd(false);
          }}
        />
      )}
    </div>
  );
}
