'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Activity,
  Lock,
  AlertOctagon,
  FileText,
  Download,
  Copy,
  Check,
  Cpu,
  Fingerprint,
  Info,
} from 'lucide-react';
import { api } from '../../../lib/api';
import { AudioQuality, DetectionCaseDetail, DetectionEvidenceReport } from '../../../lib/types';

/** Shape of the AASIST multi-window metadata stored in metadata_json.multi_window */
interface MultiWindowMeta {
  analysis_mode?: string;
  window_count?: number;
  eligible_window_count?: number;
  excluded_low_energy_window_count?: number;
  suspicious_segments?: Array<{
    start_seconds: number;
    end_seconds: number;
    peak_synthetic_probability: number;
  }>;
}
import { ThreatBadge } from '../../../components/ThreatBadge';
import { ConfidenceGauge } from '../../../components/ConfidenceGauge';
import { AudioWaveformVisualizer } from '../../../components/AudioWaveformVisualizer';
import { formatModelDisplayName } from '@/lib/formatters';

export default function DetectionDetailPage() {
  const params = useParams();

  // Safely extract and decode dynamic route param
  const rawId = params?.id;
  const id =
    typeof rawId === 'string'
      ? decodeURIComponent(rawId)
      : Array.isArray(rawId)
      ? decodeURIComponent(rawId[0])
      : '';

  const [caseDetail, setCaseDetail] = useState<DetectionCaseDetail | null>(null);
  const [evidenceReport, setEvidenceReport] = useState<DetectionEvidenceReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'telemetry' | 'report' | 'raw_json'>('overview');
  const [copiedReport, setCopiedReport] = useState(false);

  useEffect(() => {
    const fetchDetail = async () => {
      if (!id || id === '[id]' || id === '%5Bid%5D') {
        setIsLoading(false);
        setError('Detection case ID is invalid or not specified.');
        return;
      }

      setIsLoading(true);
      setError(null);
      try {
        const [caseData, reportData] = await Promise.all([
          api.getDetection(id),
          api.getDetectionReport(id).catch(() => null),
        ]);
        setCaseDetail(caseData);
        setEvidenceReport(reportData);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to load detection details.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchDetail();
  }, [id]);

  const handleCopyReportJson = () => {
    if (evidenceReport) {
      navigator.clipboard.writeText(JSON.stringify(evidenceReport, null, 2));
      setCopiedReport(true);
      setTimeout(() => setCopiedReport(false), 2000);
    }
  };

  const handleDownloadReportJson = () => {
    if (!evidenceReport) return;
    const blob = new Blob([JSON.stringify(evidenceReport, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `detection_evidence_report_${id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="h-8 w-48 bg-slate-900 rounded-lg animate-pulse" />
        <div className="h-44 bg-slate-900/60 rounded-3xl animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-64 bg-slate-900/60 rounded-2xl animate-pulse" />
          <div className="h-64 bg-slate-900/60 rounded-2xl animate-pulse" />
        </div>
      </div>
    );
  }

  if (error || !caseDetail) {
    return (
      <div className="max-w-xl mx-auto my-12 rounded-3xl border border-red-500/30 bg-red-950/20 p-8 text-center space-y-4">
        <AlertOctagon className="w-12 h-12 text-red-400 mx-auto" />
        <h2 className="text-lg font-bold text-white">Detection Case Not Found</h2>
        <p className="text-xs text-slate-300 font-mono">
          {error || `Detection case '${id}' could not be located.`}
        </p>
        <Link
          href="/detections"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Return to Case History
        </Link>
      </div>
    );
  }

  const res = caseDetail.result;
  const audioQual: AudioQuality | null | undefined =
    res?.audio_quality ??
    (res?.metadata_json?.audio_quality as AudioQuality | undefined);
  const reliability = res?.analysis_reliability ?? res?.decision?.analysis_reliability ?? audioQual?.analysis_reliability;
  const qualityFlags = res?.quality_flags ?? res?.decision?.quality_flags ?? audioQual?.quality_flags ?? [];

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Navigation Breadcrumb & Back */}
      <div className="flex items-center justify-between">
        <Link
          href="/detections"
          className="flex items-center gap-2 text-xs font-mono text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Back to History
        </Link>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-slate-500">Case ID:</span>
          <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
            {caseDetail.id}
          </span>
        </div>
      </div>

      {/* Primary Threat Verdict Banner */}
      <div
        className={`relative rounded-3xl border p-6 sm:p-8 backdrop-blur-xl shadow-2xl overflow-hidden ${
          res?.prediction === 'synthetic'
            ? 'border-red-500/30 bg-gradient-to-b from-red-950/30 via-slate-950/80 to-slate-950'
            : res?.prediction === 'replay'
            ? 'border-amber-500/30 bg-gradient-to-b from-amber-950/30 via-slate-950/80 to-slate-950'
            : res?.prediction === 'unknown'
            ? 'border-slate-700 bg-gradient-to-b from-slate-900/60 via-slate-950/80 to-slate-950'
            : 'border-emerald-500/30 bg-gradient-to-b from-emerald-950/30 via-slate-950/80 to-slate-950'
        }`}
      >
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-3 max-w-xl">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono uppercase tracking-widest text-slate-400">
                Detection Result
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              {res && <ThreatBadge prediction={res.prediction} size="lg" />}
              {res && (
                <ThreatBadge
                  riskLevel={
                    res.prediction === 'unknown' || res.raw_ml_action === 'NOT_EVALUATED' || res.analysis_status === 'inconclusive'
                      ? 'not_assessed'
                      : res.risk_level
                  }
                  size="md"
                />
              )}
              {res?.action && <ThreatBadge action={res.action} size="md" />}
              {(res?.input_source || res?.decision?.input_source) && (
                <ThreatBadge
                  inputSource={res?.input_source || res?.decision?.input_source || undefined}
                  captureDomainReliability={res?.capture_domain_reliability || res?.decision?.capture_domain_reliability || undefined}
                  size="md"
                />
              )}
              {reliability && (
                <ThreatBadge
                  reliability={reliability}
                  inputSource={res?.input_source || res?.decision?.input_source || undefined}
                  captureDomainReliability={res?.capture_domain_reliability || res?.decision?.capture_domain_reliability || undefined}
                  size="md"
                />
              )}
            </div>

            <h1 className="text-xl sm:text-2xl font-bold text-slate-100">
              {caseDetail.filename}
            </h1>

            <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-slate-400">
              <span>Size: {(caseDetail.file_size_bytes / 1024).toFixed(1)} KB</span>
              <span>•</span>
              <span>Format: {caseDetail.mime_type}</span>
              <span>•</span>
              <span>Created: {new Date(caseDetail.created_at).toLocaleString()}</span>
            </div>
          </div>

          {res && (
            <div className="bg-slate-950/60 p-4 rounded-2xl border border-slate-800/80">
              <ConfidenceGauge
                confidence={res.confidence}
                riskLevel={res.risk_level}
                prediction={res.prediction}
                size="lg"
              />
            </div>
          )}
        </div>

        {/* Quality Degradation Advisory Callout */}
        {reliability === 'degraded' && (
          <div className="mt-6 p-3.5 rounded-2xl bg-amber-950/40 border border-amber-500/40 text-amber-300 text-xs font-mono flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
            <div>
              <span className="font-bold block uppercase tracking-wider text-amber-200">
                Acoustic Quality Advisory: Degraded Channel ({qualityFlags.join(', ')})
              </span>
              <span className="mt-0.5 block leading-relaxed text-amber-300/90 text-[11px]">
                Raw model score ({res?.raw_ml_action || res?.prediction}) is preserved in forensic telemetry, but final operational recommendation is VERIFY because acoustic channel degradation reduces automated classification reliability.
              </span>
            </div>
          </div>
        )}

        {reliability === 'insufficient_speech' && (
          <div className="mt-6 p-3.5 rounded-2xl bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs font-mono flex items-start gap-3">
            <AlertOctagon className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
            <div>
              <span className="font-bold block uppercase tracking-wider text-rose-200">
                Inconclusive Assessment: Insufficient Active Speech
              </span>
              <span className="mt-0.5 block leading-relaxed text-rose-300/90 text-[11px]">
                Voice authenticity could not be assessed due to absence of continuous active speech frames. Voice authorization is deferred and secondary identity verification is required.
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2 rounded-xl text-xs font-mono font-medium transition-all ${
            activeTab === 'overview'
              ? 'bg-slate-800 text-cyan-400 border border-slate-700'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Detection Overview
        </button>
        <button
          onClick={() => setActiveTab('telemetry')}
          className={`px-4 py-2 rounded-xl text-xs font-mono font-medium transition-all ${
            activeTab === 'telemetry'
              ? 'bg-slate-800 text-cyan-400 border border-slate-700'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Acoustic Telemetry
        </button>
        <button
          onClick={() => setActiveTab('report')}
          className={`px-4 py-2 rounded-xl text-xs font-mono font-medium transition-all flex items-center gap-1.5 ${
            activeTab === 'report'
              ? 'bg-slate-800 text-cyan-400 border border-slate-700'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Evidence & Audit Report</span>
        </button>
        <button
          onClick={() => setActiveTab('raw_json')}
          className={`px-4 py-2 rounded-xl text-xs font-mono font-medium transition-all ${
            activeTab === 'raw_json'
              ? 'bg-slate-800 text-cyan-400 border border-slate-700'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Contract JSON
        </button>
      </div>

      {/* Tab 1: Overview */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Audio Player and Waveform */}
          <AudioWaveformVisualizer
            audioUrl={caseDetail.audio_url}
            filename={caseDetail.filename}
            durationSeconds={caseDetail.duration_seconds}
            prediction={res?.prediction}
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Reasoning & Attack Classification */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6 space-y-4">
              <div className="flex items-center gap-2 text-slate-300 font-mono text-xs uppercase tracking-wider">
                <Activity className="w-4 h-4 text-cyan-400" />
                <span>Model Analysis & Multi-Window</span>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 text-xs text-slate-300 leading-relaxed">
                {res?.explanation ||
                  'Deep neural network voice cloning detection. The model estimates the probability that this recording belongs to the synthetic speech class.'}
              </div>

              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between py-2 border-b border-slate-800/60">
                  <span className="text-slate-400">Attack Classification:</span>
                  <span className="font-semibold text-slate-200">
                    {res?.attack_type || 'Not classified'}
                  </span>
                </div>
                <div className="flex justify-between py-2 border-b border-slate-800/60">
                  <span className="text-slate-400">Inference Engine:</span>
                  <span className="text-cyan-400">
                    {formatModelDisplayName(res?.model_version, res?.engine_type)}
                  </span>
                </div>
                {(res?.metadata_json?.multi_window as MultiWindowMeta | undefined)?.analysis_mode === 'multi_window' && (() => {
                  const mw = res!.metadata_json!.multi_window as MultiWindowMeta;
                  return (
                    <>
                      <div className="flex justify-between py-2 border-b border-slate-800/60">
                        <span className="text-slate-400">Analysis Mode:</span>
                        <span className="text-cyan-300 font-semibold">Multi-window AASIST (75% Overlap)</span>
                      </div>
                      <div className="flex justify-between py-2 border-b border-slate-800/60">
                        <span className="text-slate-400">Windows Evaluated:</span>
                        <span className="text-slate-200">
                          {mw.eligible_window_count ?? mw.window_count} active / {mw.window_count} total
                        </span>
                      </div>
                      {(mw.excluded_low_energy_window_count ?? 0) > 0 && (
                        <div className="flex justify-between py-2 border-b border-slate-800/60">
                          <span className="text-slate-400">Excluded Silence Windows:</span>
                          <span className="text-amber-400">{mw.excluded_low_energy_window_count} non-speech</span>
                        </div>
                      )}
                      <div className="flex justify-between py-2 border-b border-slate-800/60">
                        <span className="text-slate-400">Aggregation Strategy:</span>
                        <span className="text-slate-300">Conservative maximum (max_v1)</span>
                      </div>
                    </>
                  );
                })()}
                <div className="flex justify-between py-2">
                  <span className="text-slate-400">Analysis Latency:</span>
                  <span className="text-slate-200">{res?.processing_time_ms} ms</span>
                </div>
              </div>

              {/* Multi-Window Suspicious Activity Box */}
              {(res?.metadata_json?.multi_window as MultiWindowMeta | undefined)?.analysis_mode === 'multi_window' && (() => {
                const mw = res!.metadata_json!.multi_window as MultiWindowMeta;
                return (
                <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-mono font-bold text-slate-300 uppercase tracking-wider">
                      Approximate Suspicious Model Activity
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">
                      {(mw.suspicious_segments?.length || 0)} segment(s)
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 font-mono leading-relaxed">
                    Approximate suspicious model activity localized within temporal windows. Not an exact AI timestamp boundary.
                  </p>
                  {mw.suspicious_segments && mw.suspicious_segments.length > 0 ? (
                    <div className="space-y-1.5 pt-1">
                      {mw.suspicious_segments.map((seg, sIdx: number) => (
                        <div
                          key={sIdx}
                          className="flex items-center justify-between p-2 rounded-lg bg-red-950/30 border border-red-500/30 text-xs font-mono text-slate-200"
                        >
                          <span className="text-red-400 font-semibold">
                            approx. {seg.start_seconds.toFixed(1)}s – {seg.end_seconds.toFixed(1)}s
                          </span>
                          <span className="text-rose-300">
                            P(synth): {(seg.peak_synthetic_probability * 100).toFixed(1)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-2 rounded-lg bg-slate-950/60 border border-slate-800 text-[11px] font-mono text-emerald-400">
                      No suspicious segments localized across windows.
                    </div>
                  )}
                </div>
                );
              })()}
            </div>

            {/* Countermeasure & Action Plan */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-slate-300 font-mono text-xs uppercase tracking-wider">
                  <Lock className="w-4 h-4 text-cyan-400" />
                  <span>Security Directive & Response</span>
                </div>
                <span className="text-[10px] font-mono text-slate-500">
                  Policy {res?.decision?.policy_version || 'v1.0'}
                </span>
              </div>

              {res?.action === 'BLOCK' ? (
                <div className="space-y-3">
                  <div className="p-3.5 rounded-xl bg-red-950/40 border border-red-500/30 text-red-400 text-xs flex items-start gap-3">
                    <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold block uppercase tracking-wider">BLOCK: Voice-Only Authorization Denied</span>
                      <span className="mt-0.5 block leading-relaxed">
                        {res?.decision_message || res?.decision?.decision_message || "Strong synthetic voice indicators detected. Do not trust voice-only authorization."}
                      </span>
                    </div>
                  </div>

                  <ul className="text-xs text-slate-300 space-y-1.5 font-mono list-disc list-inside">
                    {(res?.decision?.recommended_steps && res.decision.recommended_steps.length > 0
                      ? res.decision.recommended_steps
                      : [
                          "Do not approve sensitive actions based only on this voice recording.",
                          "Require out-of-band identity verification.",
                          "Escalate the event to Fraud/Security Operations.",
                          "Preserve the recording and detection metadata for review."
                        ]
                    ).map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
                </div>
              ) : res?.action === 'VERIFY' ? (
                <div className="space-y-3">
                  <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-500/30 text-amber-400 text-xs flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold block uppercase tracking-wider">VERIFY: Step-Up Verification Required</span>
                      <span className="mt-0.5 block leading-relaxed">
                        {res?.decision_message || res?.decision?.decision_message || "Suspicious voice characteristics or degraded audio quality detected. Perform secondary verification."}
                      </span>
                    </div>
                  </div>

                  <ul className="text-xs text-slate-300 space-y-1.5 font-mono list-disc list-inside">
                    {(res?.decision?.recommended_steps && res.decision.recommended_steps.length > 0
                      ? res.decision.recommended_steps
                      : [
                          "Trigger out-of-band step-up authentication (SMS/TOTP/Push challenge).",
                          "Request secondary knowledge-based verification.",
                          "Defer high-value transaction approvals.",
                          "Preserve the recording and detection metadata for review."
                        ]
                    ).map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 text-xs flex items-start gap-3">
                    <ShieldCheck className="w-5 h-5 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold block uppercase tracking-wider">ALLOW: Standard Authorization Permitted</span>
                      <span className="mt-0.5 block leading-relaxed">
                        {res?.decision_message || res?.decision?.decision_message || "No strong synthetic voice indicators detected under nominal input-quality conditions."}
                      </span>
                    </div>
                  </div>

                  <ul className="text-xs text-slate-300 space-y-1.5 font-mono list-disc list-inside">
                    {(res?.decision?.recommended_steps && res.decision.recommended_steps.length > 0
                      ? res.decision.recommended_steps
                      : [
                          "No strong synthetic voice indicators detected under nominal input-quality conditions. Continue according to standard authorization policy.",
                          "Maintain standard transaction monitoring."
                        ]
                    ).map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Input Quality & Reliability Card */}
              {audioQual && (
                <div className="mt-4 pt-4 border-t border-slate-800/80 space-y-2 text-xs font-mono">
                  <div className="flex flex-wrap items-center justify-between gap-2 pb-1">
                    <span className="text-slate-400 font-bold uppercase tracking-wider text-[11px]">Signal Quality & Capture Domain</span>
                    <div className="flex items-center gap-1.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        (res?.capture_domain_reliability || res?.decision?.capture_domain_reliability) === 'unvalidated' || (res?.input_source || res?.decision?.input_source) === 'browser_microphone'
                          ? 'bg-amber-950 text-amber-300 border border-amber-700'
                          : 'bg-blue-950 text-blue-300 border border-blue-800'
                      }`}>
                        {(res?.capture_domain_reliability || res?.decision?.capture_domain_reliability) === 'unvalidated' || (res?.input_source || res?.decision?.input_source) === 'browser_microphone'
                          ? 'Mic Domain: Unvalidated'
                          : 'Standard File Domain'}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        reliability === 'reliable' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                        reliability === 'degraded' ? 'bg-amber-950 text-amber-300 border border-amber-700' :
                        'bg-rose-950 text-rose-300 border border-rose-800'
                      }`}>
                        {((res?.capture_domain_reliability || res?.decision?.capture_domain_reliability) === 'unvalidated' || (res?.input_source || res?.decision?.input_source) === 'browser_microphone') && reliability === 'reliable'
                          ? 'Signal Quality: Good'
                          : `Signal Quality: ${reliability}`}
                      </span>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-300">
                    <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
                      <span className="text-slate-500 block">Bandwidth:</span>
                      <span className="text-slate-200">{audioQual.native_sample_rate_hz} Hz ({audioQual.effective_bandwidth_class})</span>
                    </div>
                    <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
                      <span className="text-slate-500 block">Active Speech:</span>
                      <span className="text-slate-200">{(audioQual.active_speech_fraction * 100).toFixed(1)}% density</span>
                    </div>
                    <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
                      <span className="text-slate-500 block">Clipping:</span>
                      <span className="text-slate-200">{(audioQual.clipped_sample_fraction * 100).toFixed(2)}% samples</span>
                    </div>
                    <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
                      <span className="text-slate-500 block">Signal RMS:</span>
                      <span className="text-slate-200">{audioQual.rms_dbfs} dBFS</span>
                    </div>
                  </div>
                  {qualityFlags.length > 0 && (
                    <div className="pt-1 flex flex-wrap gap-1">
                      {qualityFlags.map((flag: string, fIdx: number) => (
                        <span key={fIdx} className="px-1.5 py-0.5 rounded text-[10px] bg-slate-900 border border-amber-500/40 text-amber-300">
                          {flag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Telemetry */}
      {activeTab === 'telemetry' && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6 space-y-4">
            <h3 className="text-sm font-semibold text-slate-200 uppercase font-mono tracking-wider">
              Acoustic & Spectral Artifact Metrics
            </h3>

            {res?.spectral_artifacts ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {Object.entries(res.spectral_artifacts).map(([key, val]) => (
                  <div
                    key={key}
                    className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex justify-between items-center"
                  >
                    <span className="font-mono text-xs text-slate-400 capitalize">
                      {key.replace(/_/g, ' ')}
                    </span>
                    <span className="font-mono text-xs font-bold text-cyan-400">
                      {typeof val === 'number' ? val.toFixed(3) : String(val)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 font-mono">No spectral artifact breakdown provided.</p>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Evidence & Audit Report */}
      {activeTab === 'report' && (
        <div className="space-y-6">
          {/* Report Action Header */}
          <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-2xl border border-slate-800 bg-slate-950/70">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-cyan-950/50 border border-cyan-500/30 text-cyan-400">
                <FileText className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                  <span>Detection Evidence & Audit Summary</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-cyan-950 border border-cyan-800 text-cyan-400">
                    {evidenceReport?.report_version || 'v1.0'}
                  </span>
                </h3>
                <p className="text-xs text-slate-400 font-mono">
                  Machine-generated deterministic security analysis report
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleCopyReportJson}
                disabled={!evidenceReport}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700 hover:border-slate-600 text-slate-200 text-xs font-mono transition-all disabled:opacity-50"
              >
                {copiedReport ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-slate-400" />}
                <span>{copiedReport ? 'Copied JSON' : 'Copy JSON'}</span>
              </button>
              <button
                onClick={handleDownloadReportJson}
                disabled={!evidenceReport}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-semibold text-xs font-mono transition-all disabled:opacity-50"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download Report</span>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 1. Identification & Provenance */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-3">
              <div className="flex items-center gap-2 text-slate-300 font-mono text-xs uppercase tracking-wider pb-2 border-b border-slate-800">
                <Cpu className="w-4 h-4 text-cyan-400" />
                <span>Case Identification & Provenance</span>
              </div>
              <div className="space-y-2 text-xs font-mono text-slate-300">
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Case ID:</span>
                  <span className="text-slate-200 truncate max-w-[200px]">{evidenceReport?.case?.case_id || caseDetail.id}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Result ID:</span>
                  <span className="text-slate-200 truncate max-w-[200px]">{evidenceReport?.case?.result_id || res?.id || 'N/A'}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Status:</span>
                  <span className="text-emerald-400 font-semibold">{evidenceReport?.case?.status || caseDetail.status}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Audit Provenance:</span>
                  <span className={`font-semibold ${evidenceReport?.audit?.provenance === 'policy_evaluated' ? 'text-cyan-400' : 'text-amber-400'}`}>
                    {evidenceReport?.audit?.provenance || (res?.decision ? 'policy_evaluated' : 'legacy_unprocessed')}
                  </span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Inference Device:</span>
                  <span className="text-slate-300">{evidenceReport?.audit?.device_used || 'cuda:0'}</span>
                </div>
              </div>
            </div>

            {/* 2. Audio Evidence & Quality */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-3">
              <div className="flex items-center gap-2 text-slate-300 font-mono text-xs uppercase tracking-wider pb-2 border-b border-slate-800">
                <Fingerprint className="w-4 h-4 text-cyan-400" />
                <span>Audio Forensics & Signal Quality</span>
              </div>
              <div className="space-y-2 text-xs font-mono text-slate-300">
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">File Size:</span>
                  <span>{((evidenceReport?.audio_evidence?.file_size_bytes || caseDetail.file_size_bytes) / 1024).toFixed(1)} KB</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">MIME Format:</span>
                  <span>{evidenceReport?.audio_evidence?.mime_type || caseDetail.mime_type}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Duration:</span>
                  <span>{(evidenceReport?.audio_evidence?.duration_seconds || caseDetail.duration_seconds || 0).toFixed(2)}s</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Sample Rate:</span>
                  <span>{evidenceReport?.audio_evidence?.sample_rate_hz || caseDetail.sample_rate || 16000} Hz</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Input Source:</span>
                  <span className="font-semibold text-slate-200">{evidenceReport?.audio_evidence?.input_source || res?.input_source || 'uploaded_file'}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Capture Domain:</span>
                  <span className="font-semibold text-slate-200">{evidenceReport?.audio_evidence?.capture_domain || res?.capture_domain || 'file_audio'}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Domain Reliability:</span>
                  <span className={`font-bold ${
                    (evidenceReport?.audio_evidence?.capture_domain_reliability || res?.capture_domain_reliability) === 'unvalidated' ? 'text-amber-400' : 'text-blue-400'
                  }`}>
                    {((evidenceReport?.audio_evidence?.capture_domain_reliability || res?.capture_domain_reliability) || 'validated').toUpperCase()}
                  </span>
                </div>
                {evidenceReport?.audio_evidence?.analysis_reliability && (
                  <div className="flex justify-between py-1">
                    <span className="text-slate-400">Quality Reliability:</span>
                    <span className={`font-bold ${
                      evidenceReport.audio_evidence.analysis_reliability === 'reliable' ? 'text-emerald-400' :
                      evidenceReport.audio_evidence.analysis_reliability === 'degraded' ? 'text-amber-400' :
                      'text-rose-400'
                    }`}>
                      {evidenceReport.audio_evidence.analysis_reliability.toUpperCase()}
                    </span>
                  </div>
                )}
                {evidenceReport?.audio_evidence?.quality_flags && evidenceReport.audio_evidence.quality_flags.length > 0 && (
                  <div className="py-1">
                    <span className="text-slate-400 block mb-1">Quality Flags:</span>
                    <span className="text-[10px] text-amber-300 bg-slate-900 p-1 rounded border border-slate-800 block">
                      {evidenceReport.audio_evidence.quality_flags.join(', ')}
                    </span>
                  </div>
                )}
                <div className="py-1">
                  <span className="text-slate-400 block mb-1">Audio File SHA-256:</span>
                  <span className="text-[11px] text-cyan-400 break-all bg-slate-900/80 p-1.5 rounded-lg border border-slate-800/80 block">
                    {evidenceReport?.audio_evidence?.file_sha256 || caseDetail.file_hash || 'SHA-256 unavailable'}
                  </span>
                </div>
              </div>
            </div>

            {/* 3. Model & Acoustic Telemetry */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-3">
              <div className="flex items-center gap-2 text-slate-300 font-mono text-xs uppercase tracking-wider pb-2 border-b border-slate-800">
                <Activity className="w-4 h-4 text-cyan-400" />
                <span>Model Evidence & Forensics</span>
              </div>
              <div className="space-y-2 text-xs font-mono text-slate-300">
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Engine / Model:</span>
                  <span className="text-cyan-400">{formatModelDisplayName(res?.model_version, res?.engine_type)}</span>
                </div>
                {evidenceReport?.model_evidence?.checkpoint_sha256 && (
                  <div className="py-1">
                    <span className="text-slate-400 block mb-1">Checkpoint SHA-256:</span>
                    <span className="text-[10px] text-slate-300 break-all bg-slate-900/80 p-1.5 rounded-lg border border-slate-800/80 block">
                      {evidenceReport.model_evidence.checkpoint_sha256}
                    </span>
                  </div>
                )}
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">CM Score:</span>
                  <span className="text-slate-200 font-bold">{evidenceReport?.model_evidence?.cm_score !== null && evidenceReport?.model_evidence?.cm_score !== undefined ? evidenceReport.model_evidence.cm_score.toFixed(4) : 'N/A'}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">P(synthetic):</span>
                  <span className="text-rose-400 font-bold">{evidenceReport?.model_evidence?.synthetic_probability !== null && evidenceReport?.model_evidence?.synthetic_probability !== undefined ? evidenceReport.model_evidence.synthetic_probability.toFixed(4) : (res?.prediction === 'synthetic' ? res.confidence.toFixed(4) : (1 - (res?.confidence || 0)).toFixed(4))}</span>
                </div>
                {evidenceReport?.model_evidence?.raw_ml_action && (
                  <div className="flex justify-between py-1">
                    <span className="text-slate-400">Raw Model Action:</span>
                    <span className="text-slate-200 font-bold">{evidenceReport.model_evidence.raw_ml_action}</span>
                  </div>
                )}
                {evidenceReport?.model_evidence?.final_operational_action && (
                  <div className="flex justify-between py-1">
                    <span className="text-slate-400">Operational Action:</span>
                    <span className="text-cyan-300 font-bold">{evidenceReport.model_evidence.final_operational_action}</span>
                  </div>
                )}
                {evidenceReport?.model_evidence?.analysis_mode === 'multi_window' && (
                  <>
                    <div className="flex justify-between py-1">
                      <span className="text-slate-400">Analysis Mode:</span>
                      <span className="text-cyan-300 font-semibold">Multi-window AASIST</span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-slate-400">Windows Analyzed:</span>
                      <span className="text-slate-200">
                        {evidenceReport.model_evidence.eligible_window_count ?? evidenceReport.model_evidence.window_count} active / {evidenceReport.model_evidence.window_count} total (
                        {evidenceReport.model_evidence.window_length_seconds?.toFixed(2)}s window, ~
                        {evidenceReport.model_evidence.hop_seconds?.toFixed(2)}s hop)
                      </span>
                    </div>
                    {evidenceReport.model_evidence.excluded_low_energy_window_count !== null && evidenceReport.model_evidence.excluded_low_energy_window_count !== undefined && evidenceReport.model_evidence.excluded_low_energy_window_count > 0 && (
                      <div className="flex justify-between py-1">
                        <span className="text-slate-400">Excluded Silence:</span>
                        <span className="text-amber-400">{evidenceReport.model_evidence.excluded_low_energy_window_count} windows</span>
                      </div>
                    )}
                    <div className="flex justify-between py-1">
                      <span className="text-slate-400">Aggregation Strategy:</span>
                      <span className="text-slate-300">
                        {evidenceReport.model_evidence.aggregation_method || 'max_v1'} ({evidenceReport.model_evidence.aggregation_version || 'v1.0'})
                      </span>
                    </div>
                  </>
                )}
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Latency:</span>
                  <span>{res?.processing_time_ms} ms</span>
                </div>
              </div>
            </div>

            {/* 4. Security Decision Directive */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <div className="flex items-center gap-2 text-slate-300 font-mono text-xs uppercase tracking-wider">
                  <Lock className="w-4 h-4 text-cyan-400" />
                  <span>Security Decision</span>
                </div>
                {res?.action && <ThreatBadge action={res.action} size="sm" />}
              </div>
              <div className="space-y-2 text-xs font-mono text-slate-300">
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Operational Directive:</span>
                  <span className="font-bold text-slate-200">{evidenceReport?.security_decision?.final_operational_action || evidenceReport?.security_decision?.action || res?.action || 'N/A (Legacy)'}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Policy Version:</span>
                  <span>{evidenceReport?.security_decision?.policy_version || 'v1.0'}</span>
                </div>
                <div className="py-1">
                  <span className="text-slate-400 block mb-1">Directive Message:</span>
                  <span className="p-2 rounded-lg bg-slate-900/90 border border-slate-800 block text-slate-200">
                    {evidenceReport?.security_decision?.decision_message || res?.decision_message || 'No decision metadata available for this historical record.'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Limitations Box */}
          <div className="p-4 rounded-2xl border border-slate-800/80 bg-slate-950/40 space-y-2">
            <div className="flex items-center gap-2 text-slate-400 text-xs font-mono uppercase tracking-wider">
              <Info className="w-4 h-4 text-cyan-400" />
              <span>Report Disclaimers & Limitations</span>
            </div>
            <ul className="text-xs text-slate-400 font-mono space-y-1 list-disc list-inside">
              {(evidenceReport?.limitations || [
                "This report is a machine-generated automated security assessment, not a legal guarantee.",
                "Probability scores represent model output estimates (uncalibrated) and do not reflect definitive biometric identification.",
                "Performance may vary under acoustic noise, lossy codecs, telephony bandwidth limits, and unseen attack vectors."
              ]).map((limitation, idx) => (
                <li key={idx}>{limitation}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Tab 4: Contract JSON Payload */}
      {activeTab === 'raw_json' && (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-6 space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <span className="text-slate-400">API Contract Serialization</span>
            <button
              onClick={() => navigator.clipboard.writeText(JSON.stringify(caseDetail, null, 2))}
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px]"
            >
              Copy JSON
            </button>
          </div>
          <pre className="p-4 rounded-xl bg-slate-900 border border-slate-800 overflow-x-auto text-cyan-300 text-xs">
            {JSON.stringify(caseDetail, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
