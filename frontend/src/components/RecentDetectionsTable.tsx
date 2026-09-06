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
      <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-3 shadow-xs">
        {[1, 2, 3].map((n) => (
          <div key={n} className="h-14 bg-slate-100 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (!cases || cases.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center space-y-3 shadow-xs">
        <div className="flex items-center justify-center w-12 h-12 rounded-2xl bg-slate-100 border border-slate-200 text-slate-500 mx-auto">
          <FileAudio className="w-6 h-6" />
        </div>
        <h4 className="text-sm font-semibold text-slate-800">No detection cases recorded yet</h4>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">
          Upload or record an audio file to run your first voice cloning threat assessment.
        </p>
        <Link
          href="/detect"
          className="inline-flex items-center gap-1.5 px-4 py-2 mt-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold uppercase tracking-wider transition-all shadow-xs"
        >
          Scan First Audio Sample <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-xs overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-[11px] font-mono uppercase tracking-wider text-slate-600">
              <th className="py-3.5 px-4">Case File</th>
              <th className="py-3.5 px-4">Verdict</th>
              <th className="py-3.5 px-4">Probability</th>
              <th className="py-3.5 px-4">Risk Level</th>
              <th className="py-3.5 px-4">Timestamp</th>
              <th className="py-3.5 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-xs">
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
                  className="hover:bg-slate-50/80 transition-colors group"
                >
                  <td className="py-3.5 px-4">
                    <div className="flex items-center gap-2.5">
                      <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-100 border border-slate-200 text-slate-500 group-hover:text-indigo-600 group-hover:border-indigo-200 transition-colors">
                        <FileAudio className="w-4 h-4" />
                      </div>
                      <div>
                        <span className="font-semibold text-slate-900 block truncate max-w-[200px]">
                          {c.filename}
                        </span>
                        <span className="text-[10px] font-mono text-slate-500">
                          {(c.file_size_bytes / 1024).toFixed(1)} KB • {c.mime_type.split('/')[1] || 'audio'}
                        </span>
                      </div>
                    </div>
                  </td>

                  <td className="py-3.5 px-4">
                    {res ? (
                      <ThreatBadge prediction={res.prediction} size="sm" />
                    ) : (
                      <span className="font-mono text-xs text-slate-500">{c.status}</span>
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
                              ? 'text-red-600 font-semibold'
                              : res.prediction === 'replay'
                              ? 'text-amber-600 font-semibold'
                              : 'text-emerald-600 font-semibold'
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

                  <td className="py-3.5 px-4 text-slate-500 font-mono text-[11px] whitespace-nowrap">
                    {dateStr}
                  </td>

                  <td className="py-3.5 px-4 text-right">
                    <Link
                      href={`/detections/${c.id}`}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 hover:text-indigo-600 text-xs font-medium transition-colors shadow-xs"
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
