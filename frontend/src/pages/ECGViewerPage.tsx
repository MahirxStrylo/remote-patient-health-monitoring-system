import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Download, AlertCircle, Activity, Brain, Info, Zap,
  CheckCircle, Sliders, AlertTriangle, Grid, Eye, RefreshCw, ZoomIn
} from 'lucide-react';
import { api } from '../services/api';
import { format } from 'date-fns';
import Plot from 'react-plotly.js';

function AIInsightCard({
  status,
  classification,
  confidence,
}: {
  status: string;
  classification: string | null;
  confidence: number | null;
}) {
  const isNormal =
    classification?.toLowerCase().includes('normal') ||
    classification?.toLowerCase().includes('sinus');

  return (
    <div className={`card ${status === 'completed' && !isNormal ? 'border-amber-500/40 bg-amber-950/15' : ''}`}>
      <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2 mb-3">
        <Brain className="w-4 h-4 text-cyan-400" />
        Automated Rhythm Analysis (Research Classifier)
      </h2>
      {status === 'pending' && <p className="text-slate-500 text-xs">Analysis queued…</p>}
      {status === 'processing' && (
        <p className="text-cyan-400 text-xs flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 animate-pulse" />
          Evaluating rhythm morphology…
        </p>
      )}
      {status === 'failed' && <p className="text-rose-400 text-xs">Automated evaluation failed.</p>}
      {status === 'completed' && classification && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-200">{classification}</span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                isNormal
                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                  : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
              }`}
            >
              {isNormal ? 'Normal Sinus Rhythm' : 'Aberrant Waveform'}
            </span>
          </div>

          {confidence != null && (
            <div className="space-y-1">
              <div className="flex justify-between text-[11px] text-slate-400">
                <span>Confidence Index:</span>
                <span className="font-mono text-cyan-400">{(confidence * 100).toFixed(1)}%</span>
              </div>
              <div className="w-full bg-navy-950 rounded-full h-1.5 overflow-hidden border border-charcoal-700">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    isNormal ? 'bg-emerald-400' : 'bg-amber-400'
                  }`}
                  style={{ width: `${(confidence * 100).toFixed(0)}%` }}
                />
              </div>
            </div>
          )}

          <div className="p-2.5 rounded-lg bg-navy-950/60 border border-charcoal-700/60 text-[11px] text-slate-400 flex items-center gap-2">
            <Info className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <span>Academic classifier verification: Non-diagnostic prototype advisory.</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ECGViewerPage() {
  const { recordingId } = useParams<{ recordingId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [filterMode, setFilterMode] = useState<'filtered' | 'raw'>('filtered');
  const [gridTheme, setGridTheme] = useState<'oscilloscope' | 'paper'>('oscilloscope');
  const [downloadingCSV, setDownloadingCSV] = useState(false);
  const [downloadingPNG, setDownloadingPNG] = useState(false);

  const { data: recording, isLoading: recLoading, error: recError } = useQuery({
    queryKey: ['ecg-recording', recordingId],
    queryFn: () => api.getECGRecording(recordingId!),
    enabled: !!recordingId,
  });

  const { data: samples, isLoading: samplesLoading } = useQuery({
    queryKey: ['ecg-samples', recordingId, filterMode],
    queryFn: () => api.getECGSamples(recordingId!, filterMode === 'filtered' ? 'bandpass' : 'none'),
    enabled: !!recordingId,
  });

  const completeMutation = useMutation({
    mutationFn: () => api.completeECGSession(recordingId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ecg-recording', recordingId] });
      qc.invalidateQueries({ queryKey: ['ecg-sessions'] });
    },
  });

  const displayedSamples = useMemo(() => {
    if (filterMode === 'filtered' && samples?.filtered_samples) {
      return samples.filtered_samples;
    }
    return samples?.samples ?? [];
  }, [filterMode, samples]);

  const timeAxis = useMemo(() => {
    if (samples?.time_axis && samples.time_axis.length === displayedSamples.length) {
      return samples.time_axis;
    }
    if (samples && displayedSamples.length > 0) {
      const fs = samples.sampling_rate_hz || 250;
      return displayedSamples.map((_, i) => i / fs);
    }
    return [];
  }, [samples, displayedSamples]);

  const recId = recording?.recording_id || recording?.session_id || recordingId || '';

  const handleDownloadCSV = async () => {
    setDownloadingCSV(true);
    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch(api.getECGExportCSVUrl(recId), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error('Failed to export CSV');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ecg_${recId.slice(0, 12)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Error downloading CSV file');
    } finally {
      setDownloadingCSV(false);
    }
  };

  const handleDownloadPNG = async () => {
    setDownloadingPNG(true);
    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch(api.getECGExportPNGUrl(recId), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error('Failed to export PNG');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ecg_${recId.slice(0, 12)}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Error generating clinical ECG plot PNG');
    } finally {
      setDownloadingPNG(false);
    }
  };

  if (recLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-slate-400 flex items-center gap-2.5 text-sm font-medium">
          <Activity className="w-5 h-5 text-cyan-400 animate-pulse" />
          Reconstructing multi-batch ECG waveform timeline…
        </div>
      </div>
    );
  }

  if (recError || !recording) {
    return (
      <div className="card border-rose-500/40 bg-rose-950/20 p-4 text-rose-300 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <span>ECG session recording was not found or failed to load.</span>
        </div>
        <button className="btn-secondary text-xs" onClick={() => navigate('/recordings')}>
          Return to Sessions
        </button>
      </div>
    );
  }

  // Plotly Color Scheme Configuration based on selected grid theme
  const isPaper = gridTheme === 'paper';
  const paperBgColor = isPaper ? '#fff9f9' : '#060a12';
  const plotBgColor = isPaper ? '#fff9f9' : '#060a12';
  const gridColorMajor = isPaper ? 'rgba(239, 68, 68, 0.28)' : 'rgba(14, 165, 233, 0.15)';
  const gridColorMinor = isPaper ? 'rgba(239, 68, 68, 0.12)' : 'rgba(14, 165, 233, 0.06)';
  const traceLineColor = isPaper ? '#b91c1c' : '#22d3ee'; // Medical crimson trace on paper vs cyan on oscilloscope
  const textColor = isPaper ? '#7f1d1d' : '#94a3b8';

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-charcoal-700/60">
        <div className="flex items-start gap-3">
          <button
            onClick={() => navigate('/recordings')}
            className="p-2 rounded-lg bg-charcoal-800 text-slate-400 hover:text-slate-200 border border-charcoal-700 transition-colors mt-0.5"
            title="Return to ECG Sessions"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
                <Zap className="w-5 h-5 text-cyan-400" />
                ECG Waveform Analysis
              </h1>
              <span className="font-mono text-xs px-2.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                {recording.session_id || recording.recording_id}
              </span>
              {recording.is_simulated && (
                <span className="badge-blue text-[11px]">Simulated Data</span>
              )}
              {((recording.lead_off_count ?? 0) > 0 || recording.lead_off) && (
                <span className="badge-red text-[11px]">Lead-Off Event</span>
              )}
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                  recording.status === 'Completed'
                    ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                    : recording.status === 'Incomplete'
                    ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                    : 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30'
                }`}
              >
                {recording.status}
              </span>
            </div>
            <p className="text-slate-400 text-xs mt-1">
              Started {format(new Date(recording.started_at || recording.recorded_at || recording.created_at), 'MMMM d, yyyy HH:mm:ss')} ·{' '}
              <span className="font-mono text-slate-300 font-semibold">{recording.total_samples || recording.sample_count || 0}</span> samples @ {recording.sampling_rate_hz} Hz ·{' '}
              {samples ? <span className="font-mono text-cyan-400">{samples.duration_seconds.toFixed(2)}s duration</span> : '…'}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 self-start md:self-auto flex-wrap">
          {recording.status === 'Recording' && (
            <button
              onClick={() => completeMutation.mutate()}
              disabled={completeMutation.isPending}
              className="btn-primary text-xs"
            >
              <CheckCircle className="w-3.5 h-3.5" />
              {completeMutation.isPending ? 'Finalizing…' : 'Finalize Session'}
            </button>
          )}

          <button
            onClick={handleDownloadCSV}
            disabled={downloadingCSV}
            className="btn-secondary text-xs"
          >
            <Download className="w-3.5 h-3.5" />
            {downloadingCSV ? 'Exporting…' : 'CSV Export'}
          </button>

          <button
            onClick={handleDownloadPNG}
            disabled={downloadingPNG}
            className="btn-secondary text-xs"
          >
            <Download className="w-3.5 h-3.5" />
            {downloadingPNG ? 'Rendering…' : 'Strip Plot PNG'}
          </button>
        </div>
      </div>

      {/* Signal Controls & Filter Toggle Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 bg-navy-900/90 border border-charcoal-700/70 p-3 rounded-xl">
        {/* Left: Filter Toggle */}
        <div className="flex items-center gap-2.5">
          <Sliders className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-semibold text-slate-300">Filter Engine:</span>
          <div className="inline-flex rounded-lg p-0.5 bg-navy-950 border border-charcoal-700">
            <button
              type="button"
              onClick={() => setFilterMode('filtered')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                filterMode === 'filtered'
                  ? 'bg-cyan-500 text-slate-950 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              0.5–40 Hz Zero-Phase SOS Bandpass
            </button>
            <button
              type="button"
              onClick={() => setFilterMode('raw')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                filterMode === 'raw'
                  ? 'bg-cyan-500 text-slate-950 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Raw ADC Counts
            </button>
          </div>
        </div>

        {/* Right: Grid Theme Switcher (Medical Paper vs Oscilloscope) */}
        <div className="flex items-center gap-2.5">
          <Grid className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-300">Chart Grid:</span>
          <div className="inline-flex rounded-lg p-0.5 bg-navy-950 border border-charcoal-700">
            <button
              type="button"
              onClick={() => setGridTheme('oscilloscope')}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                gridTheme === 'oscilloscope'
                  ? 'bg-charcoal-700 text-cyan-300 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Dark Oscilloscope
            </button>
            <button
              type="button"
              onClick={() => setGridTheme('paper')}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                gridTheme === 'paper'
                  ? 'bg-rose-950 text-rose-300 border border-rose-500/40 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Clinical ECG Paper
            </button>
          </div>
        </div>
      </div>

      {/* Sequence Gap Alert Banner */}
      {samples?.has_gaps && (
        <div className="card border-amber-500/40 bg-amber-950/20 p-3.5 flex items-center gap-3 text-amber-300 text-xs">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-amber-400" />
          <div>
            <span className="font-semibold text-amber-200">Missing Batch Disconnects Detected:</span> Sequences [
            {samples.missing_sequences?.join(', ') || 'N/A'}] were dropped or delayed by cellular transmission.
            The waveform explicitly breaks with a blank interval to prevent diagnostic artifacts.
          </div>
        </div>
      )}

      {/* High-Resolution Interactive Plotly Canvas */}
      <div className={`card p-0 overflow-hidden border ${isPaper ? 'border-rose-200' : 'border-charcoal-700/80 shadow-2xl'}`}>
        {samplesLoading ? (
          <div className="h-96 flex items-center justify-center text-slate-400 text-xs gap-2">
            <Activity className="w-4 h-4 animate-pulse text-cyan-400" />
            Loading 250 Hz sample array…
          </div>
        ) : samples && displayedSamples.length > 0 ? (
          <Plot
            data={[{
              x: timeAxis,
              y: displayedSamples as (number | null)[],
              type: 'scatter',
              mode: 'lines',
              line: {
                color: traceLineColor,
                width: 1.6,
              },
              name: filterMode === 'filtered' ? 'Filtered ECG' : 'Raw ADC',
              hovertemplate: '%{x:.3f}s: %{y:.1f} ' + (recording.unit || recording.ecg_unit || 'adc_counts') + '<extra></extra>',
              connectgaps: false, // Never interpolate across dropped telemetry batches!
            }]}
            layout={{
              paper_bgcolor: paperBgColor,
              plot_bgcolor: plotBgColor,
              margin: { t: 30, b: 50, l: 65, r: 25 },
              xaxis: {
                title: { text: 'Time (seconds)', font: { color: textColor, size: 12, family: 'Inter' } },
                gridcolor: gridColorMinor,
                linecolor: textColor,
                tickfont: { color: textColor, size: 11, family: 'JetBrains Mono' },
                zeroline: false,
                dtick: 0.2, // Standard ECG major grid spacing (0.2s = 5 small boxes)
              },
              yaxis: {
                title: {
                  text: filterMode === 'filtered' ? 'Signal Amplitude (Normalized)' : 'Raw ADC Counts (0–4095)',
                  font: { color: textColor, size: 12, family: 'Inter' }
                },
                gridcolor: gridColorMinor,
                linecolor: textColor,
                tickfont: { color: textColor, size: 11, family: 'JetBrains Mono' },
                zeroline: true,
                zerolinecolor: gridColorMajor,
              },
              showlegend: false,
              dragmode: 'zoom',
              height: 400,
              autosize: true,
            }}
            config={{
              displayModeBar: true,
              displaylogo: false,
              responsive: true,
              scrollZoom: true,
              modeBarButtonsToRemove: ['lasso2d', 'select2d'],
            }}
            style={{ width: '100%', height: '400px' }}
            useResizeHandler
          />
        ) : (
          <div className="h-96 flex items-center justify-center text-slate-500 text-xs">
            No ECG waveform samples available for this recording session.
          </div>
        )}
      </div>

      {/* Diagnostics Grid & AI Rhythm Classification */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Technical Diagnostics */}
        <div className="card space-y-3">
          <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
            <Info className="w-4 h-4 text-cyan-400" />
            Signal &amp; Telemetry Diagnostics
          </h2>
          <div className="divide-y divide-charcoal-800/60 text-xs">
            {[
              { label: 'Session Identifier', value: recording.session_id || recording.recording_id || '—', mono: true },
              { label: 'Hardware Sensor', value: 'AD8232 Single-Lead ECG', mono: false },
              { label: 'Sampling Rate', value: `${recording.sampling_rate_hz} Hz (4 ms per sample)`, mono: true },
              { label: 'Total Ingested Samples', value: `${recording.total_samples ?? recording.sample_count ?? 0} samples`, mono: true },
              { label: 'Batch Sequence Count', value: `${recording.total_batches ?? 1} batch(es)`, mono: true },
              { label: 'Signal Amplitude Unit', value: recording.unit || recording.ecg_unit || 'adc_counts', mono: true },
              { label: 'Electrode Detachments', value: `${recording.lead_off_count ?? (recording.lead_off ? 1 : 0)} event(s)`, mono: true },
            ].map(({ label, value, mono }) => (
              <div key={label} className="py-2.5 flex items-center justify-between">
                <span className="text-slate-400">{label}</span>
                <span className={`text-slate-200 ${mono ? 'font-mono' : 'font-medium'}`}>{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* AI Rhythm Classifier Insight */}
        <AIInsightCard
          status={recording.ai_analysis_status}
          classification={recording.ai_classification ?? null}
          confidence={recording.ai_confidence ?? null}
        />
      </div>
    </div>
  );
}
