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
      <section className="relative rounded-3xl border border-slate-200 bg-white p-8 sm:p-12 overflow-hidden shadow-xs">
        {/* Soft background ambient gradient */}
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-96 h-96 rounded-full bg-indigo-50/60 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-96 h-96 rounded-full bg-blue-50/60 blur-3xl pointer-events-none" />

        <div className="relative z-10 max-w-3xl space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-indigo-200 bg-indigo-50 text-indigo-700 font-mono text-xs uppercase tracking-wider">
            <span className="w-2 h-2 rounded-full bg-indigo-600" />
            SIH 2026 • Problem SIH26104
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-slate-900 leading-tight">
            AI-Powered Real-Time Voice Cloning{' '}
            <span className="text-indigo-600">
              Impersonation Defense
            </span>
          </h1>

          <p className="text-base text-slate-600 leading-relaxed max-w-2xl">
            Analyze audio for potential synthetic-speech indicators using an extensible voice authenticity
            detection pipeline.
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-4">
            <Link href="/call-demo" className="flex items-center gap-2 px-6 py-3 rounded-xl border border-indigo-200 bg-indigo-50 text-indigo-700 font-semibold text-xs uppercase tracking-wider hover:bg-indigo-100 transition-colors shadow-xs">
              <ShieldAlert className="w-4 h-4 text-indigo-600" /> Try Scam Call Demo
            </Link>
            <Link
              href="/detect"
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs uppercase tracking-wider transition-all shadow-xs hover:scale-105 active:scale-95"
            >
              <UploadCloud className="w-4 h-4" /> Launch Audio Scanner
            </Link>

            <Link
              href="/detections"
              className="flex items-center gap-2 px-6 py-3 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 font-semibold text-xs uppercase tracking-wider transition-all shadow-xs"
            >
              <Radio className="w-4 h-4 text-slate-500" /> View Audit Logs
            </Link>
          </div>
        </div>
      </section>

      {/* Real-time System Metrics */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-2 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 font-mono text-xs uppercase">
            <span>Total Cases Logged</span>
            <Activity className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-3xl font-mono font-bold text-slate-900">
            {isLoading ? '--' : totalCount}
          </div>
          <p className="text-[11px] text-slate-500">Persisted in PostgreSQL database</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-2 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 font-mono text-xs uppercase">
            <span>Synthetic Cases</span>
            <ShieldAlert className="w-4 h-4 text-red-600" />
          </div>
          <div className="text-3xl font-mono font-bold text-red-600">
            {isLoading ? '--' : syntheticCount}
          </div>
          <p className="text-[11px] text-slate-500">Synthetic-speech detections</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-2 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 font-mono text-xs uppercase">
            <span>Real Voices Detected</span>
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-3xl font-mono font-bold text-emerald-600">
            {isLoading ? '--' : genuineCount}
          </div>
          <p className="text-[11px] text-slate-500">Organic voice detections</p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-2 shadow-xs">
          <div className="flex items-center justify-between text-slate-500 font-mono text-xs uppercase">
            <span>Inference Latency</span>
            <Cpu className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-3xl font-mono font-bold text-indigo-600">
            {isLoading ? (
              '--'
            ) : avgLatency !== null ? (
              <>
                {avgLatency} <span className="text-sm font-normal text-slate-500">ms</span>
              </>
            ) : (
              '—'
            )}
          </div>
          <p className="text-[11px] text-slate-500">
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
            <h2 className="text-lg font-bold text-slate-900 uppercase tracking-wide">
              Voice Authenticity Detection Pipeline
            </h2>
            <p className="text-xs text-slate-500">
              Acoustic feature analysis and statistical machine learning
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-3 shadow-xs">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-600">
              <Waves className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-slate-900">
              Acoustic Spectral Analysis
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Extracts 88-dimensional MFCC, delta, and spectral envelope descriptors from standardized
              16 kHz audio to capture short-term vocal tract characteristics.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-3 shadow-xs">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-600">
              <Layers className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-slate-900">
              Voice Authenticity Classification
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Supervised baseline classifier (StandardScaler + Logistic Regression) trained to estimate
              probabilities between organic human speech and synthetic audio.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-3 shadow-xs">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-600">
              <Lock className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-slate-900">
              Extensible Service Interface
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
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
            <h2 className="text-lg font-bold text-slate-900 uppercase tracking-wide">
              Recent Detection Incidents
            </h2>
            <p className="text-xs text-slate-500">
              Latest voice cloning inspection cases processed by the backend
            </p>
          </div>
          <button
            onClick={loadDashboardData}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-xs font-mono text-slate-700 shadow-xs transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>

        <RecentDetectionsTable cases={recentCases} isLoading={isLoading} />
      </section>
    </div>
  );
}
