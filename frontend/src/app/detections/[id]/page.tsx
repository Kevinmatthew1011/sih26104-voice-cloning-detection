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
} from 'lucide-react';
import { api } from '../../../lib/api';
import { DetectionCaseDetail } from '../../../lib/types';
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
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'telemetry' | 'raw_json'>('overview');

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
        const data = await api.getDetection(id);
        setCaseDetail(data);
      } catch (err: any) {
        setError(err.message || 'Failed to load detection details.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchDetail();
  }, [id]);

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
          onClick={() => setActiveTab('raw_json')}
          className={`px-4 py-2 rounded-xl text-xs font-mono font-medium transition-all ${
            activeTab === 'raw_json'
              ? 'bg-slate-800 text-cyan-400 border border-slate-700'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Contract JSON Payload
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
                  'Baseline ML classification using MFCC and spectral features. The model estimates the probability that this recording belongs to the synthetic speech class. This baseline does not identify a specific voice-cloning architecture.'}
              </div>

              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between py-2 border-b border-slate-800/60">
                  <span className="text-slate-400">Attack Classification:</span>
                  <span className="font-semibold text-slate-200">
                    {res?.attack_type || 'Not classified by baseline'}
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
              <div className="flex items-center gap-2 text-slate-300 font-mono text-xs uppercase tracking-wider">
                <Lock className="w-4 h-4 text-cyan-400" />
                <span>Recommended Response Protocol</span>
              </div>

              {res?.risk_level === 'high' ? (
                <div className="space-y-3">
                  <div className="p-3.5 rounded-xl bg-red-950/40 border border-red-500/30 text-red-400 text-xs flex items-start gap-3">
                    <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold block">HIGH RISK: Potential Synthetic Speech</span>
                      <span>Recommended action: Request secondary verification before relying on this recording.</span>
                    </div>
                  </div>

                  <ul className="text-xs text-slate-300 space-y-2 font-mono list-disc list-inside">
                    <li>Request out-of-band identity confirmation from the caller.</li>
                    <li>Conduct secondary challenge question or video verification.</li>
                    <li>Flag recording for manual supervisor security review.</li>
                  </ul>
                </div>
              ) : res?.risk_level === 'medium' ? (
                <div className="space-y-3">
                  <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-500/30 text-amber-400 text-xs flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold block">MEDIUM RISK: Inconclusive Signal</span>
                      <span>Recommended action: Verify speaker identity via an alternate communication channel.</span>
                    </div>
                  </div>

                  <ul className="text-xs text-slate-300 space-y-2 font-mono list-disc list-inside">
                    <li>Prompt caller with dynamic randomized challenge phrase.</li>
                    <li>Re-record audio with improved microphone signal-to-noise ratio.</li>
                  </ul>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 text-xs flex items-start gap-3">
                    <ShieldCheck className="w-5 h-5 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold block">LOW RISK: Organic Speech Indicators</span>
                      <span>Signal features are consistent with organic speech baseline parameters.</span>
                    </div>
                  </div>

                  <p className="text-xs text-slate-400 font-mono">
                    Standard processing may proceed according to policy.
                  </p>
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

      {/* Tab 3: Contract JSON Payload */}
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
