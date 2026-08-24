import React from 'react';
import { PredictionType, RiskLevelType } from '../lib/types';
import { ShieldCheck, ShieldAlert, AlertTriangle, HelpCircle } from 'lucide-react';

interface ThreatBadgeProps {
  prediction?: PredictionType;
  riskLevel?: RiskLevelType;
  showIcon?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const ThreatBadge: React.FC<ThreatBadgeProps> = ({
  prediction,
  riskLevel,
  showIcon = true,
  size = 'md',
  className = '',
}) => {
  // If prediction is provided
  if (prediction) {
    switch (prediction) {
      case 'synthetic':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-medium rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-red-950/40 text-red-400 border-red-500/30 shadow-[0_0_12px_rgba(239,68,68,0.15)] ${className}`}
          >
            {showIcon && <ShieldAlert className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />}
            Synthetic / Cloned
          </span>
        );
      case 'real':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-medium rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-emerald-950/40 text-emerald-400 border-emerald-500/30 shadow-[0_0_12px_rgba(16,185,129,0.15)] ${className}`}
          >
            {showIcon && <ShieldCheck className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />}
            Organic / Genuine
          </span>
        );
      case 'replay':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-medium rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-amber-950/40 text-amber-400 border-amber-500/30 shadow-[0_0_12px_rgba(245,158,11,0.15)] ${className}`}
          >
            {showIcon && <AlertTriangle className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />}
            Acoustic Replay
          </span>
        );
      case 'unknown':
      default:
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-medium rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-slate-900 text-slate-300 border-slate-700 ${className}`}
          >
            {showIcon && <HelpCircle className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />}
            Inconclusive
          </span>
        );
    }
  }

  // If risk level is provided separately
  if (riskLevel) {
    switch (riskLevel) {
      case 'high':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded uppercase tracking-wider ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2.5 py-0.5 text-xs'
            } bg-red-500/10 text-red-400 border border-red-500/20 ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            High Risk
          </span>
        );
      case 'medium':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded uppercase tracking-wider ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2.5 py-0.5 text-xs'
            } bg-amber-500/10 text-amber-400 border border-amber-500/20 ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            Medium Risk
          </span>
        );
      case 'low':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded uppercase tracking-wider ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2.5 py-0.5 text-xs'
            } bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Low Risk
          </span>
        );
    }
  }

  return null;
};
