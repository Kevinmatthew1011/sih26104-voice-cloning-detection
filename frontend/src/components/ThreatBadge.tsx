import React from 'react';
import { PredictionType, RiskLevelType, ActionType, ReliabilityType, CaptureDomainReliabilityType, InputSourceType } from '../lib/types';
import { ShieldCheck, ShieldAlert, AlertTriangle, HelpCircle, Lock, CheckCircle2, Sliders, AlertOctagon, Mic, FileAudio } from 'lucide-react';

interface ThreatBadgeProps {
  prediction?: PredictionType;
  riskLevel?: RiskLevelType;
  action?: ActionType;
  reliability?: ReliabilityType;
  captureDomainReliability?: CaptureDomainReliabilityType;
  inputSource?: InputSourceType;
  showIcon?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const ThreatBadge: React.FC<ThreatBadgeProps> = ({
  prediction,
  riskLevel,
  action,
  reliability,
  captureDomainReliability,
  inputSource,
  showIcon = true,
  size = 'md',
  className = '',
}) => {
  // If capture domain reliability or input source is provided
  if (captureDomainReliability || inputSource) {
    if (captureDomainReliability === 'unvalidated' || inputSource === 'browser_microphone') {
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded-md uppercase tracking-wider border ${
            size === 'sm' ? 'px-2 py-0.5 text-[10px]' : size === 'lg' ? 'px-3 py-1.5 text-xs' : 'px-2.5 py-1 text-xs'
          } bg-amber-950/40 text-amber-300 border-amber-500/30 shadow-[0_0_12px_rgba(245,158,11,0.15)] ${className}`}
        >
          {showIcon && <Mic className={size === 'lg' ? 'w-3.5 h-3.5' : 'w-3 h-3 text-amber-400'} />}
          Mic Domain: Unvalidated
        </span>
      );
    } else if (captureDomainReliability === 'validated' || inputSource === 'uploaded_file') {
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded-md uppercase tracking-wider border ${
            size === 'sm' ? 'px-2 py-0.5 text-[10px]' : size === 'lg' ? 'px-3 py-1.5 text-xs' : 'px-2.5 py-1 text-xs'
          } bg-blue-950/40 text-blue-300 border-blue-500/30 ${className}`}
        >
          {showIcon && <FileAudio className={size === 'lg' ? 'w-3.5 h-3.5' : 'w-3 h-3 text-blue-400'} />}
          Standard File Domain
        </span>
      );
    }
  }

  // If reliability rating is provided
  if (reliability) {
    switch (reliability) {
      case 'reliable':
        const reliableLabel =
          inputSource === 'browser_microphone' || captureDomainReliability === 'unvalidated'
            ? 'Signal Quality: Good'
            : 'Reliable Input';
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-[10px]' : size === 'lg' ? 'px-3 py-1.5 text-xs' : 'px-2.5 py-1 text-xs'
            } bg-emerald-950/40 text-emerald-300 border-emerald-500/30 ${className}`}
          >
            {showIcon && <CheckCircle2 className={size === 'lg' ? 'w-3.5 h-3.5' : 'w-3 h-3 text-emerald-400'} />}
            {reliableLabel}
          </span>
        );
      case 'degraded':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-[10px]' : size === 'lg' ? 'px-3 py-1.5 text-xs' : 'px-2.5 py-1 text-xs'
            } bg-amber-950/60 text-amber-300 border-amber-500/50 shadow-[0_0_12px_rgba(245,158,11,0.15)] ${className}`}
          >
            {showIcon && <Sliders className={size === 'lg' ? 'w-3.5 h-3.5' : 'w-3 h-3 text-amber-400'} />}
            Degraded Channel
          </span>
        );
      case 'insufficient_speech':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-[10px]' : size === 'lg' ? 'px-3 py-1.5 text-xs' : 'px-2.5 py-1 text-xs'
            } bg-rose-950/60 text-rose-300 border-rose-500/50 shadow-[0_0_12px_rgba(244,63,94,0.15)] ${className}`}
          >
            {showIcon && <AlertOctagon className={size === 'lg' ? 'w-3.5 h-3.5' : 'w-3 h-3 text-rose-400'} />}
            Insufficient Speech
          </span>
        );
    }
  }

  // If security action is provided
  if (action) {
    switch (action) {
      case 'BLOCK':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-bold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-red-950/60 text-red-400 border-red-500/40 shadow-[0_0_15px_rgba(239,68,68,0.2)] ${className}`}
          >
            {showIcon && <Lock className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />}
            BLOCK
          </span>
        );
      case 'VERIFY':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-bold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-amber-950/60 text-amber-400 border-amber-500/40 shadow-[0_0_15px_rgba(245,158,11,0.2)] ${className}`}
          >
            {showIcon && <AlertTriangle className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />}
            VERIFY (MFA)
          </span>
        );
      case 'ALLOW':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-bold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-emerald-950/60 text-emerald-400 border-emerald-500/40 shadow-[0_0_15px_rgba(16,185,129,0.2)] ${className}`}
          >
            {showIcon && <CheckCircle2 className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />}
            ALLOW
          </span>
        );
      case 'NOT_EVALUATED':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-medium rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-slate-900 text-slate-400 border-slate-700 ${className}`}
          >
            {showIcon && <HelpCircle className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />}
            Not Evaluated
          </span>
        );
    }
  }
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
            Synthetic
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
            Real Speech
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
            Replay (Planned)
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
      case 'not_assessed':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded uppercase tracking-wider ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2.5 py-0.5 text-xs'
            } bg-slate-900 text-slate-400 border border-slate-700 ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
            Risk Not Assessed
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
