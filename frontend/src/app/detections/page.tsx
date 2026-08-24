'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Radio,
  Search,
  Filter,
  ArrowRight,
  FileAudio,
  RefreshCw,
  SlidersHorizontal,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { api } from '../../lib/api';
import { DetectionCaseSummary } from '../../lib/types';
import { ThreatBadge } from '../../components/ThreatBadge';

export default function DetectionsHistoryPage() {
  const [cases, setCases] = useState<DetectionCaseSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [predictionFilter, setPredictionFilter] = useState('all');
  const [riskFilter, setRiskFilter] = useState('all');
  const [page, setPage] = useState(0);
  const limit = 15;

  const loadData = async () => {
    setIsLoading(true);
    try {
      const res = await api.listDetections({
        skip: page * limit,
        limit,
        search: search.trim() || undefined,
        prediction: predictionFilter !== 'all' ? predictionFilter : undefined,
        risk_level: riskFilter !== 'all' ? riskFilter : undefined,
      });
      setCases(res.items);
      setTotal(res.total);
    } catch {
      // Graceful error
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [page, predictionFilter, riskFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    loadData();
  };

  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 font-mono text-xs uppercase tracking-wider mb-2">
            <Radio className="w-3.5 h-3.5" /> Audit & Forensic Logs
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Detection Case History
          </h1>
          <p className="text-xs text-slate-400">
            Audit record of voice cloning detection scans and impersonation risk assessments
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/detect"
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs uppercase tracking-wider transition-all shadow-[0_0_12px_rgba(6,182,212,0.3)]"
          >
            + Scan New Audio
          </Link>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 backdrop-blur-md space-y-4">
        <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by audio filename..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-900/80 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Prediction Filter */}
            <div className="flex items-center gap-1.5 bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-300">
              <SlidersHorizontal className="w-3.5 h-3.5 text-slate-400" />
              <label className="text-slate-400 text-[11px] font-mono">Verdict:</label>
              <select
                value={predictionFilter}
                onChange={(e) => {
                  setPredictionFilter(e.target.value);
                  setPage(0);
                }}
                className="bg-transparent text-xs text-cyan-400 focus:outline-none cursor-pointer"
              >
                <option value="all">All Verdicts</option>
                <option value="synthetic">Synthetic</option>
                <option value="real">Real Speech</option>
                <option value="replay">Replay (Planned)</option>
              </select>
            </div>

            {/* Risk Filter */}
            <div className="flex items-center gap-1.5 bg-slate-900/80 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-300">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <label className="text-slate-400 text-[11px] font-mono">Risk:</label>
              <select
                value={riskFilter}
                onChange={(e) => {
                  setRiskFilter(e.target.value);
                  setPage(0);
                }}
                className="bg-transparent text-xs text-cyan-400 focus:outline-none cursor-pointer"
              >
                <option value="all">All Risks</option>
                <option value="high">High Risk</option>
                <option value="medium">Medium Risk</option>
                <option value="low">Low Risk</option>
              </select>
            </div>

            <button
              type="submit"
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 rounded-xl transition-colors"
            >
              Apply Filter
            </button>

            <button
              type="button"
              onClick={() => {
                setSearch('');
                setPredictionFilter('all');
                setRiskFilter('all');
                setPage(0);
              }}
              className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl transition-colors"
              title="Reset Filters"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </form>
      </div>

      {/* History Table */}
      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 backdrop-blur-sm overflow-hidden shadow-xl">
        {isLoading ? (
          <div className="p-8 space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 bg-slate-900/50 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : cases.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-slate-900 border border-slate-800 text-slate-500 mx-auto">
              <FileAudio className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-slate-300">No detection cases yet</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              {search || predictionFilter !== 'all' || riskFilter !== 'all'
                ? 'No cases match your filter criteria. Try resetting the filters.'
                : 'Upload an audio recording to create the first detection case.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800/80 bg-slate-900/50 text-[11px] font-mono uppercase tracking-wider text-slate-400">
                  <th className="py-3.5 px-4">Case File & ID</th>
                  <th className="py-3.5 px-4">Verdict</th>
                  <th className="py-3.5 px-4">Probability</th>
                  <th className="py-3.5 px-4">Risk Level</th>
                  <th className="py-3.5 px-4">Attack Type</th>
                  <th className="py-3.5 px-4">Date / Time</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50 text-xs">
                {cases.map((c) => {
                  const res = c.result;
                  const dateStr = new Date(c.created_at).toLocaleString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  });

                  return (
                    <tr
                      key={c.id}
                      className="hover:bg-slate-900/40 transition-colors group"
                    >
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-3">
                          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 group-hover:text-cyan-400 transition-colors">
                            <FileAudio className="w-4 h-4" />
                          </div>
                          <div>
                            <span className="font-semibold text-slate-200 block truncate max-w-[200px]">
                              {c.filename}
                            </span>
                            <span className="text-[10px] font-mono text-slate-500">
                              ID: {c.id.slice(0, 8)}... • {(c.file_size_bytes / 1024).toFixed(1)} KB
                            </span>
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 px-4">
                        {res ? (
                          <ThreatBadge prediction={res.prediction} size="sm" />
                        ) : (
                          <span className="font-mono text-xs text-slate-400">{c.status}</span>
                        )}
                      </td>

                      <td className="py-3.5 px-4 font-mono font-medium">
                        {res ? (
                          <span
                            className={
                              res.prediction === 'synthetic'
                                ? 'text-red-400'
                                : res.prediction === 'replay'
                                ? 'text-amber-400'
                                : 'text-emerald-400'
                            }
                            title="Uncalibrated model probability estimate"
                          >
                            {Math.round(res.confidence * 100)}%
                          </span>
                        ) : (
                          '--'
                        )}
                      </td>

                      <td className="py-3.5 px-4">
                        {res ? (
                          <ThreatBadge riskLevel={res.risk_level} size="sm" />
                        ) : (
                          '--'
                        )}
                      </td>

                      <td className="py-3.5 px-4 font-mono text-[11px] text-slate-400 max-w-[180px] truncate">
                        {res?.attack_type || 'Not classified'}
                      </td>

                      <td className="py-3.5 px-4 font-mono text-[11px] text-slate-400 whitespace-nowrap">
                        {dateStr}
                      </td>

                      <td className="py-3.5 px-4 text-right">
                        <Link
                          href={`/detections/${c.id}`}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors"
                        >
                          Details <ArrowRight className="w-3 h-3" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {total > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800/80 bg-slate-900/40 text-xs font-mono text-slate-400">
            <div>
              Showing {page * limit + 1} - {Math.min((page + 1) * limit, total)} of {total} cases
            </div>

            <div className="flex items-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed text-slate-300"
              >
                <ChevronLeft className="w-3.5 h-3.5" /> Previous
              </button>
              <span className="px-2 text-slate-400">
                Page {page + 1} of {totalPages}
              </span>
              <button
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed text-slate-300"
              >
                Next <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
