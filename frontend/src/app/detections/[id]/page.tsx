'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
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
import { DetectionCaseDetail, DetectionEvidenceReport } from '../../../lib/types';
import { ThreatBadge } from '../../../components/ThreatBadge';
import { ConfidenceGauge } from '../../../components/ConfidenceGauge';
import { AudioWaveformVisualizer } from '../../../components/AudioWaveformVisualizer';
import { formatModelDisplayName } from '@/lib/formatters';

export default function DetectionDetailPage() {
  const params = useParams();
  const router = useRouter();

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
    if (!id || id === '[id]' || id === '%5Bid%5D') {
      setIsLoading(false);
      setError('Detection case ID is invalid or not specified.');
      return;
    }

    const fetchDetail = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [caseData, reportData] = await Promise.all([
          api.getDetection(id),
          api.getDetectionReport(id).catch(() => null),
        ]);
        setCaseDetail(caseData);
        setEvidenceReport(reportData);
      } catch (err: any) {
        setError(err.message || 'Failed to load detection details.');
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

            <div className="flex flex-wrap items-center gap-3">
              {res && <ThreatBadge prediction={res.prediction} size="lg" />}
              {res && <ThreatBadge riskLevel={res.risk_level} size="md" />}
              {res?.action && <ThreatBadge action={res.action} size="md" />}
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
                <span>Model Analysis</span>
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
                <div className="flex justify-between py-2">
                  <span className="text-slate-400">Analysis Latency:</span>
                  <span className="text-slate-200">{res?.processing_time_ms} ms</span>
                </div>
              </div>
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

              {res?.action === 'BLOCK' || res?.risk_level === 'high' ? (
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
              ) : res?.action === 'VERIFY' || res?.risk_level === 'medium' ? (
                <div className="space-y-3">
                  <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-500/30 text-amber-400 text-xs flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold block uppercase tracking-wider">VERIFY: Step-Up Verification Required</span>
                      <span className="mt-0.5 block leading-relaxed">
                        {res?.decision_message || res?.decision?.decision_message || "Suspicious voice characteristics detected. Perform additional identity verification."}
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
                        {res?.decision_message || res?.decision?.decision_message || "No strong synthetic voice indicators detected."}
                      </span>
                    </div>
                  </div>

                  <ul className="text-xs text-slate-300 space-y-1.5 font-mono list-disc list-inside">
                    {(res?.decision?.recommended_steps && res.decision.recommended_steps.length > 0
                      ? res.decision.recommended_steps
                      : [
                          "No strong synthetic voice indicators detected. Continue according to standard authorization policy.",
                          "Maintain standard transaction monitoring."
                        ]
                    ).map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
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
                  Machine-generated security analysis report
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

            {/* 2. Audio Evidence */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5 space-y-3">
              <div className="flex items-center gap-2 text-slate-300 font-mono text-xs uppercase tracking-wider pb-2 border-b border-slate-800">
                <Fingerprint className="w-4 h-4 text-cyan-400" />
                <span>Audio Evidence & Integrity</span>
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
                  <span className="text-slate-400">Action:</span>
                  <span className="font-bold text-slate-200">{evidenceReport?.security_decision?.action || res?.action || 'N/A (Legacy)'}</span>
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
