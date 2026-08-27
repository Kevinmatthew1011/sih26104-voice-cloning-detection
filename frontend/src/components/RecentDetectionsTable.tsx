'use client';

import React from 'react';
import Link from 'next/link';
import { ThreatBadge } from './ThreatBadge';
import { DetectionCaseSummary } from '../lib/types';
import { ArrowRight, FileAudio } from 'lucide-react';

interface RecentDetectionsTableProps {
  cases: DetectionCaseSummary[];
  isLoading?: boolean;
}

export const RecentDetectionsTable: React.FC<RecentDetectionsTableProps> = ({
  cases,
  isLoading = false,
}) => {
  if (isLoading) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6 space-y-3">
        {[1, 2, 3].map((n) => (
          <div key={n} className="h-14 bg-slate-900/50 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (!cases || cases.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-800/80 bg-slate-950/40 p-10 text-center space-y-3">
        <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-slate-900 border border-slate-800 text-slate-500 mx-auto">
          <FileAudio className="w-6 h-6" />
        </div>
        <h4 className="text-sm font-semibold text-slate-300">No detection cases recorded yet</h4>
        <p className="text-xs text-slate-400 max-w-sm mx-auto">
          Upload or record an audio file to run your first voice cloning threat assessment.
        </p>
        <Link
          href="/detect"
          className="inline-flex items-center gap-1.5 px-4 py-2 mt-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-semibold uppercase tracking-wider transition-all"
        >
          Scan First Audio Sample <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 backdrop-blur-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800/80 bg-slate-900/40 text-[11px] font-mono uppercase tracking-wider text-slate-400">
              <th className="py-3.5 px-4">Case File</th>
              <th className="py-3.5 px-4">Verdict</th>
              <th className="py-3.5 px-4">Probability</th>
              <th className="py-3.5 px-4">Risk Level</th>
              <th className="py-3.5 px-4">Timestamp</th>
              <th className="py-3.5 px-4 text-right">Action</th>
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
                    <div className="flex items-center gap-2.5">
                      <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 group-hover:text-cyan-400 transition-colors">
                        <FileAudio className="w-4 h-4" />
                      </div>
                      <div>
                        <span className="font-semibold text-slate-200 block truncate max-w-[200px]">
                          {c.filename}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400">
                          {(c.file_size_bytes / 1024).toFixed(1)} KB • {c.mime_type.split('/')[1] || 'audio'}
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
                      res.prediction === 'unknown' || res.confidence === 0 ? (
                        <span className="text-slate-400">N/A</span>
                      ) : (
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
                      )
                    ) : (
                      '--'
                    )}
                  </td>

                  <td className="py-3.5 px-4">
                    {res ? (
                      <ThreatBadge
                        riskLevel={
                          res.prediction === 'unknown' || res.raw_ml_action === 'NOT_EVALUATED' || res.analysis_status === 'inconclusive'
                            ? 'not_assessed'
                            : res.risk_level
                        }
                        size="sm"
                      />
                    ) : (
                      '--'
                    )}
                  </td>

                  <td className="py-3.5 px-4 text-slate-400 font-mono text-[11px] whitespace-nowrap">
                    {dateStr}
                  </td>

                  <td className="py-3.5 px-4 text-right">
                    <Link
                      href={`/detections/${c.id}`}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors hover:border-slate-600"
                    >
                      Inspect <ArrowRight className="w-3 h-3" />
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
