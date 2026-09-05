'use client';

import React, { useEffect, useState, useRef } from 'react';
import {
  Play,
  Phone,
  PhoneOff,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Info,
  Activity,
  UploadCloud,
  FileAudio,
  Radio,
  RotateCcw,
  Sparkles,
} from 'lucide-react';
import { api } from '@/lib/api';
import {
  assessScamTranscript,
  demoScenarios,
  getDemoScenario,
  computeAcousticAssessment,
  computeUnifiedAssessment,
  runScenario,
  AcousticAssessment,
  ScamAssessment,
  UnifiedAssessment,
} from '@/lib/scam-demo';

type Status = 'idle' | 'ringing' | 'active' | 'ended';

interface CallState {
  status: Status;
  messages: string[];
  semantic: ScamAssessment;
  acoustic: AcousticAssessment;
  unified: UnifiedAssessment;
  outcome: string;
}

interface HistoryEntry {
  caller: string;
  outcome: string;
  verdict: string;
  reasons: string[];
  acousticLabel: string;
}

const defaultScenario = demoScenarios[0];
const initialSemantic = assessScamTranscript(defaultScenario.messages);
const initialAcoustic = computeAcousticAssessment(null);
const initialUnified = computeUnifiedAssessment(initialAcoustic, initialSemantic);

const initialCall: CallState = {
  status: 'idle',
  messages: [...defaultScenario.messages],
  semantic: initialSemantic,
  acoustic: initialAcoustic,
  unified: initialUnified,
  outcome: '',
};

const buttonStyle =
  'rounded-xl border border-slate-700 px-4 py-2.5 font-medium text-xs uppercase tracking-wider hover:bg-slate-800 transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer';

export default function CallDemoPage() {
  const [scenarioId, setScenarioId] = useState('otp');
  const [call, setCall] = useState<CallState>(initialCall);
  const [autoEnd, setAutoEnd] = useState(true);
  const [draft, setDraft] = useState('');
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [audioFileName, setAudioFileName] = useState<string | null>(null);
  const [attachedAudioFile, setAttachedAudioFile] = useState<File | null>(null);
  const [isAnalyzingAudio, setIsAnalyzingAudio] = useState(false);
  const [isRunningScenario, setIsRunningScenario] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const audioInputRef = useRef<HTMLInputElement | null>(null);

  const scenario = getDemoScenario(scenarioId);
  const busy = call.status === 'ringing' || call.status === 'active';

  function addMessage(message: string) {
    setCall((previous) => {
      if (previous.status !== 'active' || previous.messages.length >= 50 || !message.trim()) {
        return previous;
      }
      const messages = [...previous.messages, message.trim().slice(0, 500)];
      const semantic = assessScamTranscript(messages);
      const unified = computeUnifiedAssessment(previous.acoustic, semantic);
      return { ...previous, messages, semantic, unified };
    });
  }

  // Turn-by-turn messages timer during active interactive call simulation
  useEffect(() => {
    if (call.status !== 'active' || call.unified.verdict === 'HIGH') return;
    const next = scenario.messages[call.messages.length];
    if (!next) return;
    const timer = setTimeout(() => addMessage(next), 2500);
    return () => clearTimeout(timer);
  }, [call.status, call.messages.length, call.unified.verdict, scenario]);

  // Automated call ending upon HIGH unified threat
  useEffect(() => {
    if (call.status !== 'active' || call.unified.verdict !== 'HIGH' || !autoEnd) return;
    const timer = setTimeout(() => {
      setCall((previous) =>
        previous.status === 'active'
          ? {
              ...previous,
              status: 'ended',
              outcome: 'Automatically ended: high-risk scam & synthetic indicators',
            }
          : previous
      );
    }, 2000);
    return () => clearTimeout(timer);
  }, [call.status, call.unified.verdict, autoEnd]);

  // Handle Scenario Selection: populates transcript, resets acoustic, computes semantic & unified
  function handleScenarioChange(id: string) {
    setScenarioId(id);
    const nextScenario = getDemoScenario(id);
    setAudioFileName(null);
    setAttachedAudioFile(null);
    setRunError(null);

    const resetAcoustic = computeAcousticAssessment(null);
    const semantic = assessScamTranscript(nextScenario.messages);
    const unified = computeUnifiedAssessment(resetAcoustic, semantic);

    setCall({
      status: 'idle',
      messages: [...nextScenario.messages],
      semantic,
      acoustic: resetAcoustic,
      unified,
      outcome: '',
    });
  }

  // One-click Presentation Scenario Automation
  async function handleRunScenario() {
    setIsRunningScenario(true);
    setRunError(null);

    try {
      const result = await runScenario({
        scenario,
        attachedFile: attachedAudioFile,
        uploadAndDetectFn: (file: File) => api.uploadAndDetect(file, 'uploaded_file'),
      });

      setCall((previous) => ({
        ...previous,
        status: 'ended',
        messages: result.transcript,
        semantic: result.semantic,
        acoustic: result.acoustic,
        unified: result.unified,
        outcome:
          result.acoustic.status === 'synthetic_detected'
            ? 'Scenario executed: Synthetic voice flagged with high fraud indicators'
            : result.acoustic.status === 'likely_genuine'
            ? 'Scenario executed: Acoustic verified genuine human speech'
            : result.acoustic.status === 'error' || result.acoustic.status === 'audio_unavailable'
            ? 'Scenario executed: Acoustic analysis unavailable — semantic risk only'
            : 'Scenario executed: Dual-layer threat evaluation complete',
      }));

      setHistory((previous) => [
        {
          caller: scenario.caller,
          outcome: `Run Scenario (${result.unified.verdict})`,
          verdict: result.unified.verdict,
          reasons: result.semantic.reasons,
          acousticLabel: result.acoustic.label,
        },
        ...previous,
      ].slice(0, 10));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setRunError(message);
    } finally {
      setIsRunningScenario(false);
    }
  }

  // Handle manual audio attachment / upload for live AASIST testing
  async function handleAudioUpload(file: File) {
    setIsAnalyzingAudio(true);
    setAudioFileName(file.name);
    setAttachedAudioFile(file);
    setRunError(null);
    try {
      const result = await api.uploadAndDetect(file, 'uploaded_file');
      const acoustic = computeAcousticAssessment(result);
      setCall((previous) => ({
        ...previous,
        acoustic,
        unified: computeUnifiedAssessment(acoustic, previous.semantic),
      }));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      const acoustic = computeAcousticAssessment(null, message);
      setCall((previous) => ({
        ...previous,
        acoustic,
        unified: computeUnifiedAssessment(acoustic, previous.semantic),
      }));
    } finally {
      setIsAnalyzingAudio(false);
    }
  }

  function startCall() {
    if (call.status === 'ended' && call.messages.length > 0) {
      setHistory((previous) => [
        {
          caller: scenario.caller,
          outcome: call.outcome || 'Call session completed',
          verdict: call.unified.verdict,
          reasons: call.semantic.reasons,
          acousticLabel: call.acoustic.label,
        },
        ...previous,
      ].slice(0, 10));
    }
    const currentAcoustic = call.acoustic;
    const semantic = assessScamTranscript([]);
    const unified = computeUnifiedAssessment(currentAcoustic, semantic);
    setCall({
      status: 'ringing',
      messages: [],
      semantic,
      acoustic: currentAcoustic,
      unified,
      outcome: '',
    });
    setDraft('');
  }

  function endCall(outcome: string) {
    setCall((previous) => ({ ...previous, status: 'ended', outcome }));
  }

  function resetToNewDemo() {
    if (call.messages.length > 0) {
      setHistory((previous) => [
        {
          caller: scenario.caller,
          outcome: call.outcome || 'Completed session',
          verdict: call.unified.verdict,
          reasons: call.semantic.reasons,
          acousticLabel: call.acoustic.label,
        },
        ...previous,
      ].slice(0, 10));
    }
    const semantic = assessScamTranscript(scenario.messages);
    const resetAcoustic = computeAcousticAssessment(null);
    setCall({
      status: 'idle',
      messages: [...scenario.messages],
      semantic,
      acoustic: resetAcoustic,
      unified: computeUnifiedAssessment(resetAcoustic, semantic),
      outcome: '',
    });
    setDraft('');
    setAudioFileName(null);
    setAttachedAudioFile(null);
    setRunError(null);
  }

  const isAcousticUnavailable =
    call.acoustic.status === 'error' || call.acoustic.status === 'audio_unavailable';

  return (
    <div className="mx-auto max-w-6xl space-y-6 text-slate-100 font-sans">
      {/* Header */}
      <div className="space-y-2 border-b border-slate-800 pb-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            DUAL-LAYER DEFENSE DEMO
          </span>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-slate-800 text-slate-400 border border-slate-700">
            PHASE 2.5 SCENARIO AUTOMATION
          </span>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            LIVE AASIST INTEGRATION
          </span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight">Scam Call & Voice Cloning Protection</h1>
        <p className="text-sm text-slate-400 max-w-3xl">
          Unified defense correlating <strong>Acoustic Analysis</strong> (AASIST SincNet synthetic voice detection) with{' '}
          <strong>Semantic Defense</strong> (conversational intent heuristics). Features 1-click presentation automation and interactive simulated interventions without placing real telephone carrier calls.
        </p>
      </div>

      {/* Presentation Demo Mode: Compact Automation Section */}
      <section className="rounded-2xl border border-cyan-500/30 bg-gradient-to-b from-slate-900 via-slate-900/90 to-slate-950 p-6 shadow-xl space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 flex items-center gap-1.5">
                <Sparkles className="w-3 h-3" />
                DEMO MODE AUTOMATION
              </span>
              <span className="text-xs font-mono text-slate-400">Presentation Ready</span>
            </div>
            <h2 className="text-xl font-bold tracking-tight text-white mt-1">Presentation Scenario Runner</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Select a scenario to populate the transcript and click <strong>Run Scenario</strong> for an immediate dual-layer assessment.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleRunScenario}
              disabled={isRunningScenario}
              className="px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-xs uppercase tracking-wider flex items-center gap-2 shadow-[0_0_20px_rgba(6,182,212,0.3)] transition-all disabled:opacity-50 cursor-pointer"
            >
              <Play className="w-4 h-4 fill-current" />
              {isRunningScenario ? 'Executing Backend Analysis…' : 'Run Scenario'}
            </button>
            <button
              type="button"
              onClick={resetToNewDemo}
              disabled={busy}
              className={`${buttonStyle} flex items-center gap-1.5 text-slate-400 hover:text-slate-200`}
              title="Reset current scenario and acoustic state"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset
            </button>
          </div>
        </div>

        {/* Scenario Selector Tabs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {demoScenarios.map((item) => {
            const isSelected = item.id === scenarioId;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleScenarioChange(item.id)}
                className={`text-left p-3.5 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? 'border-cyan-500 bg-cyan-950/30 ring-1 ring-cyan-500/50 shadow-md'
                    : 'border-slate-800 bg-slate-950/60 hover:border-slate-700 hover:bg-slate-900/60'
                }`}
              >
                <div className="flex items-center justify-between gap-1">
                  <span className={`text-xs font-mono font-bold truncate ${isSelected ? 'text-cyan-300' : 'text-slate-300'}`}>
                    {item.title}
                  </span>
                  {item.id === 'ordinary' ? (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
                      BENIGN
                    </span>
                  ) : (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20 shrink-0">
                      SCAM
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                  {item.impersonationContext}
                </p>
              </button>
            );
          })}
        </div>

        {/* 4-Stage Presentation Sequence Display */}
        <div className="rounded-xl border border-slate-800 bg-slate-950/90 p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between text-xs font-mono text-slate-400 border-b border-slate-800 pb-2">
            <span className="uppercase font-bold tracking-wider text-slate-300">
              Execution Sequence: Select Scenario → Run Scenario → Acoustic Analysis → Semantic Analysis → Unified Verdict
            </span>
            <span className="text-[11px]">
              {isRunningScenario
                ? 'Status: Evaluating dual-layer telemetry…'
                : call.acoustic.status === 'not_analyzed'
                ? 'Status: Ready to Run (Click "Run Scenario")'
                : 'Status: Dual-layer assessment completed'}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs font-mono">
            {/* Step 1: Scenario Context */}
            <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1.5">
              <div className="flex items-center gap-1.5 text-cyan-400">
                <span className="w-4 h-4 rounded-full bg-cyan-500/20 text-[10px] flex items-center justify-center font-bold">1</span>
                <span className="font-bold uppercase tracking-wider text-[11px]">Scenario Context</span>
              </div>
              <p className="text-slate-200 font-bold">{scenario.name}</p>
              <p className="text-[11px] text-slate-400">Caller: {scenario.caller}</p>
              <p className="text-[11px] text-slate-500 italic line-clamp-2">{scenario.impersonationContext}</p>
              <div className="pt-1">
                {scenario.sampleAudioPath ? (
                  <span className="inline-block text-[10px] text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-500/30">
                    Audio Fixture: {scenario.sampleAudioPath}
                  </span>
                ) : attachedAudioFile ? (
                  <span className="inline-block text-[10px] text-cyan-300 bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-500/30 truncate max-w-full">
                    Attached Clip: {attachedAudioFile.name}
                  </span>
                ) : (
                  <span className="inline-block text-[10px] text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                    Audio: None (Semantic mode)
                  </span>
                )}
              </div>
            </div>

            {/* Step 2: Acoustic Defense */}
            <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1.5">
              <div className="flex items-center gap-1.5 text-cyan-400">
                <span className="w-4 h-4 rounded-full bg-cyan-500/20 text-[10px] flex items-center justify-center font-bold">2</span>
                <span className="font-bold uppercase tracking-wider text-[11px]">Acoustic Defense</span>
              </div>
              <div>
                <span
                  className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                    call.acoustic.status === 'synthetic_detected'
                      ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                      : call.acoustic.status === 'likely_genuine'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : isAcousticUnavailable
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      : 'bg-slate-800 text-slate-400 border border-slate-700'
                  }`}
                >
                  {call.acoustic.label}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 space-y-0.5 pt-0.5">
                <p>Engine: <span className="text-slate-200">{call.acoustic.engineType || 'AASIST'}</span></p>
                <p>
                  P(synthetic):{' '}
                  <span className="text-slate-200 font-bold">
                    {call.acoustic.syntheticProbability !== null
                      ? `${(call.acoustic.syntheticProbability * 100).toFixed(1)}%`
                      : 'Not evaluated'}
                  </span>
                </p>
                {call.acoustic.confidence !== null && (
                  <p>Confidence: {(call.acoustic.confidence * 100).toFixed(1)}%</p>
                )}
                <p>Policy Action: <span className="text-slate-200">{call.acoustic.action || 'NOT_EVALUATED'}</span></p>
              </div>
            </div>

            {/* Step 3: Semantic Defense */}
            <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1.5">
              <div className="flex items-center gap-1.5 text-amber-400">
                <span className="w-4 h-4 rounded-full bg-amber-500/20 text-[10px] flex items-center justify-center font-bold">3</span>
                <span className="font-bold uppercase tracking-wider text-[11px]">Semantic Defense</span>
              </div>
              <div>
                <span
                  className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                    call.semantic.risk === 'high'
                      ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                      : call.semantic.risk === 'warning'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      : call.semantic.risk === 'no_indicators'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : 'bg-slate-800 text-slate-400 border border-slate-700'
                  }`}
                >
                  Risk: {call.semantic.risk.toUpperCase()}
                </span>
              </div>
              {call.semantic.reasons.length > 0 ? (
                <ul className="text-[10px] text-amber-200 space-y-0.5 list-disc pl-3 mt-1">
                  {call.semantic.reasons.map((r, i) => (
                    <li key={i} className="line-clamp-2">{r}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-[11px] text-slate-500 italic mt-1">No scam indicators flagged</p>
              )}
            </div>

            {/* Step 4: Unified Verdict */}
            <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1.5">
              <div className="flex items-center gap-1.5 text-purple-400">
                <span className="w-4 h-4 rounded-full bg-purple-500/20 text-[10px] flex items-center justify-center font-bold">4</span>
                <span className="font-bold uppercase tracking-wider text-[11px]">Unified Verdict</span>
              </div>
              <div>
                <span
                  className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-mono font-bold ${
                    call.unified.verdict === 'HIGH'
                      ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                      : call.unified.verdict === 'MEDIUM'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      : call.unified.verdict === 'LOW'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : 'bg-slate-800 text-slate-400 border border-slate-700'
                  }`}
                >
                  {call.unified.verdict}
                </span>
              </div>
              <p className="text-[11px] text-slate-200 font-bold line-clamp-2 mt-0.5">
                {call.unified.headline}
              </p>
              <p className="text-[10px] text-slate-400 line-clamp-3 italic">
                {call.unified.explanation}
              </p>
            </div>
          </div>
        </div>

        {/* Error or Notice Alert Banner */}
        {runError && (
          <div className="p-3 rounded-xl bg-red-950/40 border border-red-500/40 text-xs font-mono text-red-300 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{runError}</span>
          </div>
        )}

        {isAcousticUnavailable && call.acoustic.errorMessage && (
          <div className="p-3 rounded-xl bg-amber-950/30 border border-amber-500/30 text-xs font-mono text-amber-300 flex items-start gap-2">
            <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Acoustic Telemetry Notice:</span>{' '}
              <span>{call.acoustic.errorMessage}. Semantic analysis preserved without acoustic evaluation.</span>
            </div>
          </div>
        )}
      </section>

      {/* Main Unified Threat Banner */}
      <div
        role="alert"
        aria-live="polite"
        className={`rounded-2xl border p-6 space-y-3 transition-all ${
          call.unified.verdict === 'HIGH'
            ? 'border-red-500/50 bg-red-950/30 text-red-100 shadow-[0_0_30px_rgba(239,68,68,0.2)]'
            : call.unified.verdict === 'MEDIUM'
            ? 'border-amber-500/50 bg-amber-950/30 text-amber-100'
            : call.unified.verdict === 'LOW'
            ? 'border-emerald-500/50 bg-emerald-950/30 text-emerald-100'
            : 'border-slate-800 bg-slate-900/60 text-slate-300'
        }`}
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-white/10 pb-3">
          <div className="flex items-center gap-3">
            {call.unified.verdict === 'HIGH' && <ShieldAlert className="w-6 h-6 text-red-400 animate-pulse" />}
            {call.unified.verdict === 'MEDIUM' && <AlertTriangle className="w-6 h-6 text-amber-400" />}
            {call.unified.verdict === 'LOW' && <CheckCircle2 className="w-6 h-6 text-emerald-400" />}
            {call.unified.verdict === 'UNASSESSED' && <Info className="w-6 h-6 text-slate-400" />}
            <div>
              <span className="text-xs font-mono font-bold uppercase tracking-wider opacity-75">
                Unified Threat Assessment
              </span>
              <h2 className="text-xl font-bold">{call.unified.headline}</h2>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider ${
                call.unified.verdict === 'HIGH'
                  ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                  : call.unified.verdict === 'MEDIUM'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                  : call.unified.verdict === 'LOW'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'bg-slate-800 text-slate-400 border border-slate-700'
              }`}
            >
              Verdict: {call.unified.verdict}
            </span>
          </div>
        </div>

        <p className="text-sm leading-relaxed">{call.unified.explanation}</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono pt-1">
          <div className="bg-black/20 rounded-xl p-3 border border-white/5 space-y-1">
            <span className="text-slate-400 uppercase font-semibold">Layer 1 (Acoustic Telemetry):</span>
            <p className="text-slate-200">{call.unified.acousticSummary}</p>
          </div>
          <div className="bg-black/20 rounded-xl p-3 border border-white/5 space-y-1">
            <span className="text-slate-400 uppercase font-semibold">Layer 2 (Semantic Intent):</span>
            <p className="text-slate-200">{call.unified.semanticSummary}</p>
          </div>
        </div>

        <div className="pt-2 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-t border-white/10">
          <p className="font-semibold text-cyan-300">{call.unified.recommendedAction}</p>
          <span className="text-[11px] opacity-60 max-w-md">{call.unified.disclaimer}</span>
        </div>

        {call.status === 'active' && call.unified.verdict === 'HIGH' && autoEnd && (
          <p className="text-xs font-bold text-red-400 animate-pulse">
            Safety protocol active: Automatically terminating simulated call in two seconds…
          </p>
        )}
      </div>

      {/* Two-Column Workspace */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left Column: Call Controls & Layer 1 Acoustic Defense */}
        <section className="space-y-6">
          {/* Interactive Call Simulator Box */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-200">
                Interactive Call Simulator
              </h3>
              <label className="flex items-center gap-2 text-xs font-mono text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  className="rounded border-slate-700 bg-slate-950 text-cyan-500 focus:ring-0"
                  checked={autoEnd}
                  onChange={(event) => setAutoEnd(event.target.checked)}
                />
                <span>Auto-Terminate on HIGH</span>
              </label>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 text-center space-y-3">
              <div className="relative inline-block">
                <Phone className={`mx-auto h-10 w-10 ${busy ? 'text-cyan-400 animate-bounce' : 'text-slate-500'}`} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-100">{scenario.caller}</h2>
                <p className="text-xs font-mono uppercase tracking-wider text-slate-400 mt-0.5">
                  {call.status === 'idle'
                    ? 'Ready for incoming call simulation'
                    : call.status === 'active'
                    ? 'Connected · Monitoring Dual-Layer Telemetry'
                    : call.status === 'ringing'
                    ? 'Incoming simulated call ringing…'
                    : call.status}
                </p>
              </div>

              <div className="flex flex-wrap justify-center gap-3 pt-2">
                {call.status === 'idle' && (
                  <button className={`${buttonStyle} bg-cyan-500 text-slate-950 font-bold border-cyan-400 hover:bg-cyan-400`} onClick={startCall}>
                    Simulate Incoming Call
                  </button>
                )}
                {call.status === 'ringing' && (
                  <>
                    <button className={`${buttonStyle} bg-emerald-600 text-white border-emerald-500 hover:bg-emerald-500`} onClick={() => setCall((prev) => ({ ...prev, status: 'active' }))}>
                      Answer
                    </button>
                    <button className={`${buttonStyle} text-red-400 border-red-500/40 hover:bg-red-950/40`} onClick={() => endCall('Declined before answering')}>
                      Decline
                    </button>
                  </>
                )}
                {call.status === 'active' && (
                  <button className={`${buttonStyle} bg-red-600/80 text-white border-red-500 hover:bg-red-600 flex items-center gap-2`} onClick={() => endCall('Ended by user')}>
                    <PhoneOff className="h-4 w-4" /> End Simulated Call
                  </button>
                )}
                {call.status === 'ended' && (
                  <button className={`${buttonStyle} bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-700`} onClick={resetToNewDemo}>
                    Reset Call Simulator
                  </button>
                )}
              </div>

              {call.status === 'ended' && (
                <p role="status" className="rounded-lg bg-slate-900 border border-slate-800 p-2.5 text-xs font-mono text-slate-400 mt-2">
                  {call.outcome || 'Call session completed'}. No real telephone carrier calls or hardware lines affected.
                </p>
              )}
            </div>
          </div>

          {/* Layer 1: Acoustic Defense Panel */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-200">
                  Layer 1: Acoustic Defense (AASIST)
                </h3>
              </div>
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold ${
                  call.acoustic.status === 'synthetic_detected'
                    ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                    : call.acoustic.status === 'likely_genuine'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : isAcousticUnavailable
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                    : 'bg-slate-800 text-slate-400 border border-slate-700'
                }`}
              >
                {call.acoustic.label}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-500 uppercase">Detection Engine</span>
                <p className="text-slate-200 font-bold mt-0.5">{call.acoustic.engineType || 'AASIST'}</p>
              </div>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-500 uppercase">Model Version</span>
                <p className="text-slate-200 font-bold mt-0.5">{call.acoustic.modelVersion || 'v1.0'}</p>
              </div>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-500 uppercase">Synthetic Probability</span>
                <p
                  className={`font-bold mt-0.5 ${
                    call.acoustic.syntheticProbability !== null && call.acoustic.syntheticProbability >= 0.70
                      ? 'text-red-400'
                      : call.acoustic.syntheticProbability !== null && call.acoustic.syntheticProbability < 0.50
                      ? 'text-emerald-400'
                      : 'text-slate-400'
                  }`}
                >
                  {call.acoustic.syntheticProbability !== null
                    ? `${(call.acoustic.syntheticProbability * 100).toFixed(1)}%`
                    : 'Not evaluated'}
                </p>
              </div>
              <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                <span className="text-slate-500 uppercase">Raw Policy Action</span>
                <p className="text-slate-200 font-bold mt-0.5">{call.acoustic.action || 'NOT_EVALUATED'}</p>
              </div>
            </div>

            {/* Audio Clip Attachment */}
            <div className="space-y-2 pt-1 border-t border-slate-800/80">
              <div className="flex items-center justify-between">
                <label className="text-xs font-mono text-slate-400 flex items-center gap-1.5">
                  <FileAudio className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Attach Audio Clip to Evaluate AASIST:</span>
                </label>
                {audioFileName && (
                  <span className="text-xs font-mono text-cyan-300 truncate max-w-[180px]">
                    {audioFileName}
                  </span>
                )}
              </div>

              <div className="flex gap-2">
                <input
                  type="file"
                  ref={audioInputRef}
                  accept=".wav,.flac,.mp3,.ogg,.webm,.m4a"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleAudioUpload(file);
                  }}
                />
                <button
                  type="button"
                  onClick={() => audioInputRef.current?.click()}
                  disabled={isAnalyzingAudio || isRunningScenario}
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 hover:bg-slate-800 text-xs font-mono text-slate-300 transition-all disabled:opacity-50 cursor-pointer"
                >
                  <UploadCloud className="w-3.5 h-3.5 text-cyan-400" />
                  {isAnalyzingAudio ? 'Running AASIST Inference…' : 'Select Audio File to Run AASIST'}
                </button>
              </div>

              <p className="text-[11px] font-mono text-slate-500 leading-tight">
                Backend integration: Calls existing <code>POST /api/v1/detections</code> with 16 kHz multi-window AASIST inference. No demo audio files are committed in git; attach any audio file to run live acoustic verification.
              </p>
            </div>
          </div>
        </section>

        {/* Right Column: Layer 2 Semantic Defense & Live Transcript */}
        <section className="space-y-6">
          {/* Layer 2: Semantic Defense Panel */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-200">
                  Layer 2: Semantic Intent Defense
                </h3>
              </div>
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold ${
                  call.semantic.risk === 'high'
                    ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                    : call.semantic.risk === 'warning'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                    : call.semantic.risk === 'no_indicators'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-slate-800 text-slate-400 border border-slate-700'
                }`}
              >
                Semantic: {call.semantic.risk.toUpperCase()}
              </span>
            </div>

            <div className="text-xs font-mono space-y-2">
              <div className="flex items-center justify-between text-slate-400">
                <span>Expected Pattern:</span>
                <span className="text-slate-300 text-right">{scenario.expectedPattern}</span>
              </div>
              {call.semantic.reasons.length > 0 ? (
                <div className="space-y-1.5 pt-1">
                  <span className="text-amber-400 font-semibold uppercase text-[11px]">Matched Scam Indicators:</span>
                  <ul className="list-disc pl-4 space-y-1 text-amber-200">
                    {call.semantic.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-slate-500 italic">
                  {call.messages.length
                    ? 'No recognized credential theft, remote access, or coercive payment patterns matched.'
                    : 'Awaiting caller conversation messages…'}
                </p>
              )}
            </div>
          </div>

          {/* Caller Transcript Log & Custom Message Box */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-200">
                Caller Transcript Stream
              </h3>
              <span className="text-xs font-mono text-slate-500">
                {call.messages.length} / 50 messages
              </span>
            </div>

            <div
              role="log"
              aria-label="Simulated caller transcript"
              className="max-h-64 min-h-36 space-y-2.5 overflow-y-auto font-mono text-xs pr-1"
            >
              {call.messages.length ? (
                call.messages.map((message, index) => (
                  <div key={index} className="rounded-xl bg-slate-950 border border-slate-800 p-3 space-y-1">
                    <span className="text-[10px] text-slate-500 uppercase tracking-widest block">
                      Message #{index + 1}
                    </span>
                    <p className="text-slate-200 leading-relaxed break-words">{message}</p>
                  </div>
                ))
              ) : (
                <div className="h-36 flex items-center justify-center text-slate-600 text-xs italic">
                  No conversation messages received yet. Click &ldquo;Simulate Incoming Call&rdquo; to start.
                </div>
              )}
            </div>

            <form
              className="space-y-3 pt-2 border-t border-slate-800"
              onSubmit={(event) => {
                event.preventDefault();
                addMessage(draft);
                setDraft('');
              }}
            >
              <label htmlFor="caller-message" className="block text-xs font-mono text-slate-400">
                Inject Custom Caller Phrase:
              </label>
              <textarea
                id="caller-message"
                className="w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                maxLength={500}
                rows={2}
                value={draft}
                disabled={call.status !== 'active' || call.messages.length >= 50}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Type a custom phrase, e.g.: 'Send me your verification code immediately.'"
              />
              <button
                type="submit"
                className={`${buttonStyle} bg-slate-800 hover:bg-slate-700 text-slate-200`}
                disabled={call.status !== 'active' || !draft.trim() || call.messages.length >= 50}
              >
                Inject Caller Message
              </button>
            </form>
          </div>
        </section>
      </div>

      {/* Session History */}
      <section className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
        <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-300">
          Demo Session History
        </h3>
        <p className="text-xs font-mono text-slate-500">
          Last ten simulated calls and scenario automation runs in this session. Maintained in page memory; independent of backend audit records.
        </p>

        {history.length === 0 ? (
          <p className="text-xs font-mono text-slate-600 italic py-2">
            Finish a simulated call session or click &ldquo;Run Scenario&rdquo; to record its dual-layer evaluation here.
          </p>
        ) : (
          <div className="divide-y divide-slate-800 text-xs font-mono">
            {history.map((entry, index) => (
              <div key={index} className="py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <span className="font-bold text-slate-200">{entry.caller}</span>
                  <span className="text-slate-500 mx-2">&bull;</span>
                  <span className="text-slate-400">{entry.outcome}</span>
                  <p className="text-slate-500 text-[11px] mt-0.5">
                    {entry.reasons.join('; ') || 'No semantic flags'} &bull; Acoustic: {entry.acousticLabel}
                  </p>
                </div>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold self-start sm:self-auto ${
                    entry.verdict === 'HIGH'
                      ? 'bg-red-500/20 text-red-300'
                      : entry.verdict === 'MEDIUM'
                      ? 'bg-amber-500/20 text-amber-300'
                      : entry.verdict === 'LOW'
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {entry.verdict}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
