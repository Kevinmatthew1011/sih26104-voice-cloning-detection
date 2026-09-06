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
            } bg-emerald-50 text-emerald-800 border-emerald-200 shadow-xs ${className}`}
          >
            {showIcon && <CheckCircle2 className={size === 'lg' ? 'w-3.5 h-3.5' : 'w-3 h-3 text-emerald-600'} />}
            {reliableLabel}
          </span>
        );
      case 'degraded':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-[10px]' : size === 'lg' ? 'px-3 py-1.5 text-xs' : 'px-2.5 py-1 text-xs'
            } bg-amber-50 text-amber-900 border-amber-300 shadow-xs ${className}`}
          >
            {showIcon && <Sliders className={size === 'lg' ? 'w-3.5 h-3.5' : 'w-3 h-3 text-amber-600'} />}
            Degraded Channel
          </span>
        );
      case 'insufficient_speech':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-[10px]' : size === 'lg' ? 'px-3 py-1.5 text-xs' : 'px-2.5 py-1 text-xs'
            } bg-rose-50 text-rose-800 border-rose-200 shadow-xs ${className}`}
          >
            {showIcon && <AlertOctagon className={size === 'lg' ? 'w-3.5 h-3.5' : 'w-3 h-3 text-rose-600'} />}
            Insufficient Speech
          </span>
        );
    }
  }

  // If capture domain reliability or input source is provided (when reliability is not provided)
  if (captureDomainReliability || inputSource) {
    if (captureDomainReliability === 'unvalidated' || inputSource === 'browser_microphone') {
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded-md uppercase tracking-wider border ${
            size === 'sm' ? 'px-2 py-0.5 text-[10px]' : size === 'lg' ? 'px-3 py-1.5 text-xs' : 'px-2.5 py-1 text-xs'
          } bg-amber-50 text-amber-900 border-amber-200 shadow-xs ${className}`}
        >
          {showIcon && <Mic className={size === 'lg' ? 'w-3.5 h-3.5' : 'w-3 h-3 text-amber-600'} />}
          Mic Domain: Unvalidated
        </span>
      );
    } else if (captureDomainReliability === 'validated' || inputSource === 'uploaded_file') {
      return (
        <span
          className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded-md uppercase tracking-wider border ${
            size === 'sm' ? 'px-2 py-0.5 text-[10px]' : size === 'lg' ? 'px-3 py-1.5 text-xs' : 'px-2.5 py-1 text-xs'
          } bg-blue-50 text-blue-800 border-blue-200 shadow-xs ${className}`}
        >
          {showIcon && <FileAudio className={size === 'lg' ? 'w-3.5 h-3.5' : 'w-3 h-3 text-blue-600'} />}
          Standard File Domain
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
            } bg-red-50 text-red-700 border-red-300 shadow-xs ${className}`}
          >
            {showIcon && <Lock className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5 text-red-600'} />}
            BLOCK
          </span>
        );
      case 'VERIFY':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-bold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-amber-50 text-amber-800 border-amber-300 shadow-xs ${className}`}
          >
            {showIcon && <AlertTriangle className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5 text-amber-600'} />}
            VERIFY (MFA)
          </span>
        );
      case 'ALLOW':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-bold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-emerald-50 text-emerald-800 border-emerald-300 shadow-xs ${className}`}
          >
            {showIcon && <CheckCircle2 className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5 text-emerald-600'} />}
            ALLOW
          </span>
        );
      case 'NOT_EVALUATED':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-medium rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-slate-100 text-slate-700 border-slate-200 ${className}`}
          >
            {showIcon && <HelpCircle className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5 text-slate-500'} />}
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
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-red-50 text-red-700 border-red-200 shadow-xs ${className}`}
          >
            {showIcon && <ShieldAlert className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5 text-red-600'} />}
            Synthetic
          </span>
        );
      case 'real':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-emerald-50 text-emerald-800 border-emerald-200 shadow-xs ${className}`}
          >
            {showIcon && <ShieldCheck className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5 text-emerald-600'} />}
            Real Speech
          </span>
        );
      case 'replay':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-amber-50 text-amber-800 border-amber-200 shadow-xs ${className}`}
          >
            {showIcon && <AlertTriangle className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5 text-amber-600'} />}
            Replay (Planned)
          </span>
        );
      case 'unknown':
      default:
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-medium rounded-md uppercase tracking-wider border ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3.5 py-1.5 text-sm' : 'px-2.5 py-1 text-xs'
            } bg-slate-100 text-slate-700 border-slate-200 ${className}`}
          >
            {showIcon && <HelpCircle className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5 text-slate-500'} />}
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
            } bg-red-50 text-red-700 border border-red-200 shadow-xs ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-red-600" />
            High Risk
          </span>
        );
      case 'medium':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded uppercase tracking-wider ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2.5 py-0.5 text-xs'
            } bg-amber-50 text-amber-800 border border-amber-200 shadow-xs ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
            Medium Risk
          </span>
        );
      case 'not_assessed':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded uppercase tracking-wider ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2.5 py-0.5 text-xs'
            } bg-slate-100 text-slate-600 border border-slate-200 ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
            Risk Not Assessed
          </span>
        );
      case 'low':
        return (
          <span
            className={`inline-flex items-center gap-1.5 font-mono font-semibold rounded uppercase tracking-wider ${
              size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2.5 py-0.5 text-xs'
            } bg-emerald-50 text-emerald-800 border border-emerald-200 shadow-xs ${className}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
            Low Risk
          </span>
        );
    }
  }

  return null;
};
