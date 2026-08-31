'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  ShieldAlert,
  ShieldCheck,
  Cpu,
  UploadCloud,
  Radio,
  Activity,
  Waves,
  Layers,
  Lock,
  RefreshCw,
} from 'lucide-react';
import { api } from '../lib/api';
import { DetectionCaseSummary, HealthStatus } from '../lib/types';
import { RecentDetectionsTable } from '../components/RecentDetectionsTable';
import { formatNavbarEngineLabel } from '@/lib/formatters';

export default function DashboardPage() {
  const [recentCases, setRecentCases] = useState<DetectionCaseSummary[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      const [listRes, healthRes] = await Promise.all([
        api.listDetections({ limit: 5 }),
        api.getHealth(),
      ]);
      setRecentCases(listRes.items);
      setTotalCount(listRes.total);
      setHealth(healthRes);
    } catch {
      // Handled gracefully
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const [listRes, healthRes] = await Promise.all([
          api.listDetections({ limit: 5 }),
          api.getHealth(),
        ]);
        setRecentCases(listRes.items);
        setTotalCount(listRes.total);
        setHealth(healthRes);
      } catch {
        // Handled gracefully
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  // Compute real metrics from loaded cases
  const syntheticCount = recentCases.filter((c) => c.result?.prediction === 'synthetic').length;
  const genuineCount = recentCases.filter((c) => c.result?.prediction === 'real').length;
  const avgLatency =
    recentCases.length > 0
      ? Math.round(
          recentCases.reduce((acc, c) => acc + (c.result?.processing_time_ms || 0), 0) /
            recentCases.length
        )
      : null;

  return (
    <div className="space-y-12">
      {/* Hero Section */}
      <section className="relative rounded-3xl border border-slate-800/80 bg-gradient-to-b from-slate-900/80 via-slate-950/70 to-slate-950 p-8 sm:p-12 overflow-hidden shadow-2xl backdrop-blur-xl">
        {/* Glow accent */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-96 h-96 rounded-full bg-cyan-500/10 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-96 h-96 rounded-full bg-blue-500/10 blur-3xl pointer-events-none" />

        <div className="relative z-10 max-w-3xl space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 font-mono text-xs uppercase tracking-wider">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            SIH 2026 • Problem SIH26104
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-white leading-tight">
            AI-Powered Real-Time Voice Cloning{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-teal-300 to-blue-500">
              Impersonation Defense
            </span>
          </h1>

          <p className="text-base text-slate-300 leading-relaxed max-w-2xl">
            Analyze audio for potential synthetic-speech indicators using an extensible voice authenticity
            detection pipeline.
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-4">
            <Link
              href="/detect"
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs uppercase tracking-wider transition-all shadow-[0_0_20px_rgba(6,182,212,0.4)] hover:scale-105 active:scale-95"
            >
              <UploadCloud className="w-4 h-4" /> Launch Audio Scanner
            </Link>

            <Link
              href="/detections"
              className="flex items-center gap-2 px-6 py-3 rounded-xl border border-slate-700 bg-slate-900/80 hover:bg-slate-800 text-slate-200 font-semibold text-xs uppercase tracking-wider transition-all"
            >
              <Radio className="w-4 h-4 text-slate-400" /> View Audit Logs
            </Link>
          </div>
        </div>
      </section>

      {/* Real-time System Metrics */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/60 p-5 space-y-2 backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 font-mono text-xs uppercase">
            <span>Total Cases Logged</span>
            <Activity className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-3xl font-mono font-bold text-slate-100">
            {isLoading ? '--' : totalCount}
          </div>
          <p className="text-[11px] text-slate-400">Persisted in PostgreSQL database</p>
        </div>

        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/60 p-5 space-y-2 backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 font-mono text-xs uppercase">
            <span>Synthetic Cases</span>
            <ShieldAlert className="w-4 h-4 text-red-400" />
          </div>
          <div className="text-3xl font-mono font-bold text-red-400">
            {isLoading ? '--' : syntheticCount}
          </div>
          <p className="text-[11px] text-slate-400">Synthetic-speech detections</p>
        </div>

        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/60 p-5 space-y-2 backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 font-mono text-xs uppercase">
            <span>Real Voices Detected</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-mono font-bold text-emerald-400">
            {isLoading ? '--' : genuineCount}
          </div>
          <p className="text-[11px] text-slate-400">Organic voice detections</p>
        </div>

        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/60 p-5 space-y-2 backdrop-blur-md">
          <div className="flex items-center justify-between text-slate-400 font-mono text-xs uppercase">
            <span>Inference Latency</span>
            <Cpu className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-3xl font-mono font-bold text-cyan-400">
            {isLoading ? (
              '--'
            ) : avgLatency !== null ? (
              <>
                {avgLatency} <span className="text-sm font-normal text-slate-400">ms</span>
              </>
            ) : (
              '—'
            )}
          </div>
          <p className="text-[11px] text-slate-400">
            {avgLatency !== null
              ? `Active engine: ${formatNavbarEngineLabel(health?.detection_engine, health?.model_version)}`
              : 'No analyses yet'}
          </p>
        </div>
      </section>

      {/* Forensic Architecture & Capabilities */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide">
              Voice Authenticity Detection Pipeline
            </h2>
            <p className="text-xs text-slate-400">
              Acoustic feature analysis and statistical machine learning
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-6 space-y-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <Waves className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-slate-200">
              Acoustic Spectral Analysis
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Extracts 88-dimensional MFCC, delta, and spectral envelope descriptors from standardized
              16 kHz audio to capture short-term vocal tract characteristics.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-6 space-y-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <Layers className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-slate-200">
              Voice Authenticity Classification
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Supervised baseline classifier (StandardScaler + Logistic Regression) trained to estimate
              probabilities between organic human speech and synthetic audio.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-6 space-y-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <Lock className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-slate-200">
              Extensible Service Interface
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Decoupled BaseDetectionService interface allowing seamless drop-in integration of advanced
              neural architectures (Wav2Vec2, RawNet2, AASIST).
            </p>
          </div>
        </div>
      </section>

      {/* Recent Incident Log Table */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide">
              Recent Detection Incidents
            </h2>
            <p className="text-xs text-slate-400">
              Latest voice cloning inspection cases processed by the backend
            </p>
          </div>
          <button
            onClick={loadDashboardData}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/60 hover:bg-slate-800 text-xs font-mono text-slate-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>

        <RecentDetectionsTable cases={recentCases} isLoading={isLoading} />
      </section>
    </div>
  );
}
