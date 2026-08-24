import React from 'react';
import { PredictionType, RiskLevelType } from '../lib/types';

interface ConfidenceGaugeProps {
  confidence: number; // 0.0 to 1.0 (uncalibrated probability estimate)
  riskLevel: RiskLevelType;
  prediction: PredictionType;
  size?: 'sm' | 'md' | 'lg';
}

export const ConfidenceGauge: React.FC<ConfidenceGaugeProps> = ({
  confidence,
  riskLevel,
  prediction,
  size = 'md',
}) => {
  const percentage = Math.round(confidence * 100);

  const getColorClass = () => {
    if (prediction === 'synthetic' || riskLevel === 'high') {
      return {
        text: 'text-red-400',
        stroke: 'stroke-red-500',
        bg: 'bg-red-500/10',
        border: 'border-red-500/20',
        glow: 'drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]',
      };
    }
    if (prediction === 'replay' || riskLevel === 'medium') {
      return {
        text: 'text-amber-400',
        stroke: 'stroke-amber-500',
        bg: 'bg-amber-500/10',
        border: 'border-amber-500/20',
        glow: 'drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]',
      };
    }
    if (prediction === 'real' || riskLevel === 'low') {
      return {
        text: 'text-emerald-400',
        stroke: 'stroke-emerald-500',
        bg: 'bg-emerald-500/10',
        border: 'border-emerald-500/20',
        glow: 'drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]',
      };
    }
    return {
      text: 'text-cyan-400',
      stroke: 'stroke-cyan-500',
      bg: 'bg-cyan-500/10',
      border: 'border-cyan-500/20',
      glow: 'drop-shadow-[0_0_8px_rgba(6,182,212,0.5)]',
    };
  };

  const colors = getColorClass();

  // Circle dimensions
  const radius = size === 'lg' ? 44 : size === 'sm' ? 24 : 34;
  const strokeWidth = size === 'lg' ? 7 : size === 'sm' ? 4 : 5;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;
  const svgSize = (radius + strokeWidth) * 2;

  const probabilityLabel =
    prediction === 'synthetic'
      ? 'Synthetic Probability'
      : prediction === 'real'
      ? 'Real Speech Probability'
      : 'Probability Estimate';

  return (
    <div className="flex items-center gap-4">
      <div className="relative inline-flex items-center justify-center">
        <svg
          width={svgSize}
          height={svgSize}
          className="transform -rotate-90"
        >
          {/* Background circle */}
          <circle
            cx={svgSize / 2}
            cy={svgSize / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            fill="transparent"
            className="text-slate-800"
          />
          {/* Progress circle */}
          <circle
            cx={svgSize / 2}
            cy={svgSize / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="transparent"
            className={`${colors.stroke} ${colors.glow} transition-all duration-1000 ease-out`}
          />
        </svg>
        <div className="absolute flex flex-col items-center justify-center">
          <span
            className={`font-mono font-bold tracking-tighter ${
              size === 'lg' ? 'text-2xl' : size === 'sm' ? 'text-xs' : 'text-base'
            } ${colors.text}`}
          >
            {percentage}%
          </span>
        </div>
      </div>
      <div className="flex flex-col">
        <span className="text-xs uppercase tracking-wider text-slate-400 font-mono">
          {probabilityLabel}
        </span>
        <span className="text-sm font-semibold text-slate-200 font-mono">
          {(confidence * 100).toFixed(1)}%
        </span>
        <span className="text-[10px] text-slate-500 font-mono">
          Uncalibrated model estimate
        </span>
      </div>
    </div>
  );
};
