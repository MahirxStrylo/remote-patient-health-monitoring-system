import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, Eye, EyeOff, AlertCircle, Shield, KeyRound, Sparkles } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const { login, isLoading, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  if (isAuthenticated) {
    navigate('/dashboard', { replace: true });
    return null;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await login(username, password);
      navigate('/dashboard');
    } catch {
      setError('Authentication failed. Please verify clinician credentials.');
    }
  };

  const fillDemoCredentials = () => {
    setUsername('admin');
    setPassword('admin123');
    setError('');
  };

  return (
    <div className="min-h-screen bg-navy-950 flex flex-col justify-center items-center p-4 relative overflow-hidden font-sans">
      {/* Background Subtle Medical Grid Glow */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-cyan-950/20 via-navy-950 to-navy-950 pointer-events-none" />

      <div className="w-full max-w-md relative z-10 space-y-6">
        {/* Brand & Platform Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-cyan-500/15 border border-cyan-500/40 rounded-2xl shadow-glow-cyan mb-2">
            <Activity className="w-7 h-7 text-cyan-400 animate-pulse" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">
            HealthMonitor <span className="text-cyan-400">Portal</span>
          </h1>
          <p className="text-slate-400 text-xs max-w-xs mx-auto">
            Remote Patient Physiological Telemetry & Two-Way Clinical Directive Interface
          </p>
        </div>

        {/* Authentication Card */}
        <div className="card shadow-2xl border border-charcoal-700/80 bg-navy-900/90 backdrop-blur-md">
          <div className="flex items-center justify-between pb-3 mb-4 border-b border-charcoal-700/60">
            <h2 className="text-slate-100 font-semibold text-sm flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-cyan-400" />
              Clinician Authentication
            </h2>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              JWT Secured
            </span>
          </div>

          {error && (
            <div className="flex items-center gap-2.5 bg-rose-950/40 border border-rose-500/40 text-rose-300 rounded-lg p-3 mb-4 text-xs animate-shake">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Clinician Username</label>
              <input
                type="text"
                className="input"
                placeholder="e.g. admin"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </div>

            <div>
              <label className="label">Access Password</label>
              <div className="relative">
                <input
                  type={showPwd ? 'text' : 'password'}
                  className="input pr-10"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 p-1"
                >
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full py-2.5 text-sm font-semibold tracking-wide"
            >
              {isLoading ? (
                <span className="flex items-center gap-2">
                  <Activity className="w-4 h-4 animate-spin text-white" />
                  Verifying Session…
                </span>
              ) : (
                'Access Clinical Dashboard'
              )}
            </button>
          </form>

          {/* Quick Demo Helper Button for Examiners / Teachers */}
          <div className="mt-5 pt-4 border-t border-charcoal-700/60 flex items-center justify-between text-xs">
            <span className="text-slate-500">Evaluation Demo:</span>
            <button
              type="button"
              onClick={fillDemoCredentials}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-charcoal-800 hover:bg-cyan-500/20 text-slate-300 hover:text-cyan-300 border border-charcoal-700 transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              Fill `admin` / `admin123`
            </button>
          </div>
        </div>

        {/* Security / Research Footer */}
        <div className="text-center space-y-1">
          <div className="flex items-center justify-center gap-1.5 text-slate-500 text-xs">
            <Shield className="w-3.5 h-3.5 text-slate-600" />
            End-to-End Cryptographic Ingestion &amp; Device Identity
          </div>
          <p className="text-[11px] text-slate-600">
            University Research Prototype · Rural Telehealth Network (2G GPRS)
          </p>
        </div>
      </div>
    </div>
  );
}
