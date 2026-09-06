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
  Waves,
  Mic,
  MicOff,
  UserCheck,
  Globe,
  Bot,
  Zap,
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
import {
  CallAudioStreamClient,
  LiveAcousticUpdate,
  LiveSessionSummary,
  computeLiveAcousticAssessment,
} from '@/lib/call-audio-stream';
import { LiveSTTClient } from '@/lib/live-stt';
import {
  WebRTCCallSession,
  WebRTCRole,
  WebRTCConnectionStatus,
  WebRTCMicStatus,
  WebRTCRemoteAudioStatus,
} from '@/lib/webrtc-call';

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

const baseBtn =
  'rounded-xl px-4 py-2.5 font-bold text-xs uppercase tracking-wider transition-all disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer shadow-xs';
const secondaryBtn = `${baseBtn} border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 hover:border-slate-400`;
const primaryBtn = `${baseBtn} border border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700`;
const dangerBtn = `${baseBtn} border border-red-600 bg-red-600 text-white hover:bg-red-700 flex items-center gap-2`;
const successBtn = `${baseBtn} border border-emerald-600 bg-emerald-600 text-white hover:bg-emerald-700 flex items-center gap-1.5`;
const secondaryDangerBtn = `${baseBtn} border border-red-300 bg-white text-red-700 hover:bg-red-50`;

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

  // Phase 3: Real-Time Audio Streaming State
  const [isStreamingMic, setIsStreamingMic] = useState(false);
  const [liveStreamingState, setLiveStreamingState] = useState<string>('idle');
  const [liveAcousticUpdates, setLiveAcousticUpdates] = useState<LiveAcousticUpdate[]>([]);
  const [finalSessionSummary, setFinalSessionSummary] = useState<LiveSessionSummary | null>(null);
  const [userOverrideWarning, setUserOverrideWarning] = useState(false);
  const [liveError, setLiveError] = useState<string | null>(null);

  const streamClientRef = useRef<CallAudioStreamClient | null>(null);
  const latestUpdateRef = useRef<LiveAcousticUpdate | null>(null);

  // Phase 9: Live STT State
  const [useLiveSTT, setUseLiveSTT] = useState(true);
  const [interimSTT, setInterimSTT] = useState('');
  const [sttStatus, setSTTStatus] = useState<'idle' | 'listening' | 'stopped' | 'unsupported'>('idle');
  const liveSTTRef = useRef<LiveSTTClient | null>(null);

  // Phase 10: ML Scam Intent State
  const [mlScamData, setMlScamData] = useState<{
    scam_probability: number;
    risk_level: string;
    primary_intent: string;
    detected_triggers: string[];
    is_ml_inferred: boolean;
  } | null>(null);

  // Phase 11: Speaker Verification State
  const [claimedSpeakerId, setClaimedSpeakerId] = useState<string>('none');
  const [enrolledSpeakers, setEnrolledSpeakers] = useState<
    Array<{ speaker_id: string; speaker_name: string; duration_seconds?: number }>
  >([
    { speaker_id: 'SPK_ALICE_CFO', speaker_name: 'Alice (VP of Finance)' },
    { speaker_id: 'SPK_BOB_TECH', speaker_name: 'Bob (Lead Infrastructure Engineer)' },
    { speaker_id: 'SPK_CAROL_BANK', speaker_name: 'Carol (Authorized Bank Security Officer)' },
  ]);
  const [speakerVerifyState, setSpeakerVerifyState] = useState<{
    state: string;
    similarity_score: number | null;
    explanation: string;
  } | null>(null);
  const [isVerifyingSpeaker, setIsVerifyingSpeaker] = useState(false);

  // Backend Engine Detection State
  const [backendDetectionEngine, setBackendDetectionEngine] = useState<string>('mock');
  const [backendModelVersion, setBackendModelVersion] = useState<string>('mock-v1');
  const [isBackendAasistReady, setIsBackendAasistReady] = useState<boolean>(false);
  const [backendStatusMessage, setBackendStatusMessage] = useState<string>('Querying backend engine...');

  // Phase 14: Real WebRTC Cross-Tab State
  const [rtcRole, setRtcRole] = useState<WebRTCRole>('caller');
  const [rtcRoomId, setRtcRoomId] = useState<string>('voiceguard-test');
  const [rtcConnection, setRtcConnection] = useState<WebRTCConnectionStatus>('IDLE');
  const [rtcLocalMic, setRtcLocalMic] = useState<WebRTCMicStatus>('MUTED');
  const [rtcRemoteAudio, setRtcRemoteAudio] = useState<WebRTCRemoteAudioStatus>('WAITING');
  const [rtcSTT, setRtcSTT] = useState<'ACTIVE' | 'UNAVAILABLE'>('UNAVAILABLE');
  const [rtcAudioDiagnostics, setRtcAudioDiagnostics] = useState('Audio pipeline idle');
  const [rtcSpeaker, setRtcSpeaker] = useState<Awaited<ReturnType<typeof api.verifySpeaker>> | null>(null);
  const [rtcVerifyIdentity, setRtcVerifyIdentity] = useState(false);
  const [rtcDiagnostics, setRtcDiagnostics] = useState('Waiting for peer');
  const [rtcRisk, setRtcRisk] = useState<Awaited<ReturnType<typeof api.evaluateMultimodal>> | null>(null);
  const rtcLatestAcousticRef = useRef<LiveAcousticUpdate | null>(null);
  const rtcTranscriptRef = useRef('');
  const rtcRecorderTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [rtcSTTTranscript, setRtcSTTTranscript] = useState<string>('');
  const [rtcAudioPlayError, setRtcAudioPlayError] = useState<string | null>(null);
  const [rtcAcousticUpdate, setRtcAcousticUpdate] = useState<LiveAcousticUpdate | null>(null);
  const [rtcAcousticWindows, setRtcAcousticWindows] = useState<LiveAcousticUpdate[]>([]);
  const [rtcAcousticError, setRtcAcousticError] = useState<string | null>(null);

  const realWebRtcSessionRef = useRef<WebRTCCallSession | null>(null);
  const remoteAudioElementRef = useRef<HTMLAudioElement | null>(null);
  const rtcStreamClientRef = useRef<CallAudioStreamClient | null>(null);
  const rtcMediaRecorderRef = useRef<MediaRecorder | null>(null);

  // Load backend engine status and enrolled speakers on mount
  useEffect(() => {
    api.getHealth()
      .then((health) => {
        const eng = (health.detection_engine || 'mock').toLowerCase();
        setBackendDetectionEngine(eng);
        setBackendModelVersion(health.model_version || (eng === 'mock' ? 'mock-v1' : 'aasist-v1'));
        const engineInfo = health.details?.engine_info as Record<string, unknown> | undefined;
        const isReady = Boolean(engineInfo?.model_trained || engineInfo?.status === 'ready');
        setIsBackendAasistReady(isReady);
        if (eng === 'mock') {
          setBackendStatusMessage('MOCK ENGINE active (mock-v1). Heuristic spectral scoring.');
        } else if (eng === 'aasist') {
          if (isReady) {
            setBackendStatusMessage('AASIST active (aasist-v1). Deep graph attention network.');
          } else {
            setBackendStatusMessage('AASIST checkpoint missing on disk (models/aasist/AASIST.pth). ACOUSTIC UNAVAILABLE.');
          }
        } else {
          setBackendStatusMessage(`${eng.toUpperCase()} engine configured.`);
        }
      })
      .catch(() => {
        setBackendDetectionEngine('mock');
        setBackendStatusMessage('Backend health check unreachable. Defaulting to mock safeguards.');
      });

    api.listEnrolledSpeakers()
      .then((list) => {
        if (list && list.length > 0) {
          setEnrolledSpeakers((prev) => {
            const ids = new Set(prev.map((s) => s.speaker_id));
            const merged = [...prev];
            for (const item of list) {
              if (!ids.has(item.speaker_id)) {
                merged.push(item);
                ids.add(item.speaker_id);
              }
            }
            return merged;
          });
        }
      })
      .catch(() => {});
  }, []);

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
    if (call.status !== 'active' || call.unified.verdict !== 'HIGH' || !autoEnd || userOverrideWarning) return;
    const timer = setTimeout(() => {
      handleEndCall('Automatically ended: high-risk scam & synthetic indicators');
    }, 2500);
    return () => clearTimeout(timer);
  }, [call.status, call.unified.verdict, autoEnd, userOverrideWarning]);

  // Clean up streaming on unmount
  useEffect(() => {
    return () => {
      streamClientRef.current?.disconnect();
      const session = realWebRtcSessionRef.current;
      realWebRtcSessionRef.current = null;
      session?.endCall();
      rtcStreamClientRef.current?.disconnect();
      if (rtcRecorderTimerRef.current) clearTimeout(rtcRecorderTimerRef.current);
      if (rtcMediaRecorderRef.current?.state === 'recording') rtcMediaRecorderRef.current.stop();
    };
  }, []);

  // Handle Scenario Selection: populates transcript, resets acoustic, computes semantic & unified
  function handleScenarioChange(id: string) {
    if (streamClientRef.current) {
      streamClientRef.current.disconnect();
      streamClientRef.current = null;
    }
    setIsStreamingMic(false);
    latestUpdateRef.current = null;
    setLiveAcousticUpdates([]);
    setFinalSessionSummary(null);
    setUserOverrideWarning(false);
    setLiveError(null);

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
    if (streamClientRef.current) {
      streamClientRef.current.disconnect();
      streamClientRef.current = null;
    }
    setIsStreamingMic(false);
    latestUpdateRef.current = null;
    setLiveAcousticUpdates([]);
    setFinalSessionSummary(null);
    setUserOverrideWarning(false);
    setLiveError(null);

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
    const currentAcoustic = computeAcousticAssessment(null);
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

  async function handleAnswerCall(overrideStream?: MediaStream) {
    setCall((prev) => ({ ...prev, status: 'active' }));
    setIsStreamingMic(true);
    setLiveStreamingState('connecting');
    setLiveAcousticUpdates([]);
    setLiveError(null);
    setUserOverrideWarning(false);
    latestUpdateRef.current = null;

    const client = new CallAudioStreamClient();
    streamClientRef.current = client;

    // Phase 9: Start live browser STT if enabled
    if (useLiveSTT) {
      if (!liveSTTRef.current) {
        liveSTTRef.current = new LiveSTTClient();
      }
      liveSTTRef.current.start({
        onTranscriptSegment: (segment, isFinal) => {
          if (isFinal) {
            setInterimSTT('');
            setCall((prev) => {
              const messages = [...prev.messages, segment];
              const semantic = assessScamTranscript(messages);
              const unified = computeUnifiedAssessment(prev.acoustic, semantic);
              return { ...prev, messages, semantic, unified };
            });
            client.sendContextUpdate(
              segment,
              claimedSpeakerId !== 'none' ? claimedSpeakerId : undefined
            );
            api
              .analyzeScamIntent(segment)
              .then((data) => setMlScamData(data))
              .catch(() => {});
          } else {
            setInterimSTT(segment);
          }
        },
        onStatusChange: (s) => setSTTStatus(s),
      });
    }

    try {
      await client.start(
        {
          onStatus: (statusEvent) => {
            setLiveStreamingState(statusEvent.state);
            setCall((prev) => {
              const liveAcoustic = computeLiveAcousticAssessment(
                latestUpdateRef.current,
                statusEvent.state,
                null,
                backendDetectionEngine
              );
              return {
                ...prev,
                acoustic: liveAcoustic,
                unified: computeUnifiedAssessment(liveAcoustic, prev.semantic),
              };
            });
          },
          onAcousticUpdate: (update) => {
            latestUpdateRef.current = update;
            setLiveAcousticUpdates((prev) => [...prev, update]);
            setCall((prev) => {
              const liveAcoustic = computeLiveAcousticAssessment(
                update,
                undefined,
                null,
                backendDetectionEngine
              );
              return {
                ...prev,
                acoustic: liveAcoustic,
                unified: computeUnifiedAssessment(liveAcoustic, prev.semantic),
              };
            });
          },
          onMultimodalUpdate: (mmUpdate) => {
            setCall((prev) => ({
              ...prev,
              unified: {
                verdict:
                  mmUpdate.overall_risk === 'HIGH'
                    ? 'HIGH'
                    : mmUpdate.overall_risk === 'LOW'
                    ? 'LOW'
                    : 'MEDIUM',
                headline: mmUpdate.headline,
                explanation: mmUpdate.explanation,
                acousticSummary: prev.unified.acousticSummary,
                semanticSummary: prev.unified.semanticSummary,
                recommendedAction:
                  mmUpdate.overall_risk === 'HIGH'
                    ? 'Safety warning: Potential AI impersonation detected. Disconnect immediately.'
                    : prev.unified.recommendedAction,
                disclaimer: prev.unified.disclaimer,
              },
            }));
          },
          onError: (err) => {
            setLiveError(err.message);
            setIsStreamingMic(false);
            setCall((prev) => {
              const errorAcoustic = computeLiveAcousticAssessment(
                null,
                undefined,
                err.message,
                backendDetectionEngine
              );
              return {
                ...prev,
                acoustic: errorAcoustic,
                unified: computeUnifiedAssessment(errorAcoustic, prev.semantic),
              };
            });
          },
          onSummary: (summary) => {
            setFinalSessionSummary(summary);
          },
          onClose: () => {
            setIsStreamingMic(false);
            setLiveStreamingState('closed');
          },
        },
        { engine: backendDetectionEngine }
      );

      if (overrideStream) {
        client.attachMediaStream(overrideStream);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setLiveError(message);
      setIsStreamingMic(false);
      setCall((prev) => {
        const errorAcoustic = computeLiveAcousticAssessment(null, undefined, message);
        return {
          ...prev,
          acoustic: errorAcoustic,
          unified: computeUnifiedAssessment(errorAcoustic, prev.semantic),
        };
      });
    }
  }

  // Phase 14: Real WebRTC Handlers (Tab A Caller vs Tab B Protected User)
  async function playRtcRemote(stream: MediaStream) {
    const audio = remoteAudioElementRef.current;
    if (!audio) return;
    audio.srcObject = stream;
    audio.muted = false;
    audio.volume = 1;
    try { await audio.play(); setRtcRemoteAudio('PLAYING'); }
    catch (error) {
      setRtcRemoteAudio('ERROR');
      setRtcAudioPlayError(`Playback blocked: ${String(error)}. Click Play Remote Audio.`);
    }
  }

  async function handleRtcStartCaller() {
    setRtcAudioPlayError(null);
    setRtcAcousticError(null);
    setRtcAcousticUpdate(null);
    setRtcAcousticWindows([]);
    setRtcSTTTranscript('');
    rtcTranscriptRef.current = '';
    rtcLatestAcousticRef.current = null;
    setRtcRisk(null);
    setRtcSpeaker(null);
    setRtcSTT('UNAVAILABLE');

    const session = new WebRTCCallSession();
    realWebRtcSessionRef.current = session;

    try {
      await session.startCaller(rtcRoomId, {
        onRemoteStream: playRtcRemote,
        onRemoteAudioStatusChange: setRtcRemoteAudio,
        onConnectionStatusChange: (status) => {
          setRtcConnection(status);
          if (status === 'ENDED') {
            setRtcSTT('UNAVAILABLE');
            setRtcAudioDiagnostics('Audio pipeline stopped');
            if (rtcRecorderTimerRef.current) clearTimeout(rtcRecorderTimerRef.current);
            if (rtcMediaRecorderRef.current?.state === 'recording') rtcMediaRecorderRef.current.stop();
            rtcStreamClientRef.current?.disconnect();
            if (remoteAudioElementRef.current) remoteAudioElementRef.current.srcObject = null;
          }
        },
        onDiagnostics: setRtcDiagnostics,
        onMicStatusChange: (status) => setRtcLocalMic(status),
        onError: (err) => setRtcAudioPlayError(err),
      });
    } catch (err: unknown) {
      setRtcLocalMic('ERROR');
      setRtcConnection('ENDED');
      setRtcAudioPlayError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleRtcJoinProtectedUser() {
    setRtcAudioPlayError(null);
    setRtcAcousticError(null);
    setRtcAcousticUpdate(null);
    setRtcAcousticWindows([]);
    setRtcSTTTranscript('');
    rtcTranscriptRef.current = '';
    rtcLatestAcousticRef.current = null;
    setRtcRisk(null);
    setRtcSpeaker(null);
    setRtcSTT('UNAVAILABLE');

    const session = new WebRTCCallSession();
    realWebRtcSessionRef.current = session;

    let riskSequence = 0;
    const refreshRisk = async () => {
      const sequence = ++riskSequence;
      const isCurrent = () => realWebRtcSessionRef.current === session && session.isCallActive();
      try {
        const semantic = rtcTranscriptRef.current ? await api.analyzeScamIntent(rtcTranscriptRef.current) : null;
        const acoustic = rtcLatestAcousticRef.current;
        const risk = await api.evaluateMultimodal({
          acoustic: acoustic?.engine === 'aasist' ? {
            status: acoustic.prediction === 'synthetic' ? 'synthetic_detected' : 'likely_genuine',
            synthetic_probability: acoustic.synthetic_probability,
            confidence: acoustic.confidence,
            engine: acoustic.engine,
            channel_reliability: 'UNVALIDATED_WEBRTC',
          } : undefined,
          semantic: semantic ? { risk: semantic.risk_level, scam_probability: semantic.scam_probability,
            primary_intent: semantic.primary_intent, reasons: semantic.detected_triggers } : undefined,
          context: { audio_source: 'remote_webrtc', speaker_verification: 'Unverified; MFCC prototype has no validated identity calibration' },
        });
        if (isCurrent() && sequence === riskSequence) setRtcRisk(risk);
      } catch (error) { if (isCurrent()) setRtcAudioPlayError(`Risk analysis unavailable: ${String(error)}`); }
    };
    try {
      await session.startProtectedUser(rtcRoomId, {
        onMicStatusChange: setRtcLocalMic,
        onConnectionStatusChange: (status) => {
          setRtcConnection(status);
          if (status === 'ENDED') {
            setRtcSTT('UNAVAILABLE');
            setRtcAudioDiagnostics('Audio pipeline stopped');
            if (rtcRecorderTimerRef.current) clearTimeout(rtcRecorderTimerRef.current);
            if (rtcMediaRecorderRef.current?.state === 'recording') rtcMediaRecorderRef.current.stop();
            rtcStreamClientRef.current?.disconnect();
            if (remoteAudioElementRef.current) remoteAudioElementRef.current.srcObject = null;
          }
        },
        onDiagnostics: setRtcDiagnostics,
        onRemoteAudioStatusChange: (status) => setRtcRemoteAudio(status),
        onError: (err) => setRtcAudioPlayError(err),
        onRemoteStream: async (remoteStream) => {
          void playRtcRemote(remoteStream);
          // TASK 4: Analyze remote caller stream ONLY
          const streamClient = new CallAudioStreamClient();
          rtcStreamClientRef.current = streamClient;
          try {
            await streamClient.startFromStream(
              remoteStream,
              {
                onDiagnostics: setRtcAudioDiagnostics,
                onAcousticUpdate: (update) => {
                  rtcLatestAcousticRef.current = update;
                  void refreshRisk();
                  setRtcAcousticUpdate(update);
                  setRtcAcousticWindows((prev) => [...prev.slice(-9), update]);
                },
                onError: (err) => {
                  if (err.code === 'AASIST_UNAVAILABLE') {
                    setRtcAcousticError(`AASIST unavailable: ${err.detail || err.message}`);
                  } else {
                    setRtcAcousticError(err.message);
                  }
                  rtcLatestAcousticRef.current = null;
                  void refreshRisk();
                },
              },
              { engine: 'aasist' }
            );
          } catch (err: unknown) {
            setRtcAcousticError(err instanceof Error ? err.message : String(err));
          }

          // TASK 5: Remote STT via backend
          try {
            const mimeType =
              typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
                ? 'audio/ogg;codecs=opus'
                : 'audio/webm';

            if (typeof MediaRecorder !== 'undefined') {
              const recorder = new MediaRecorder(remoteStream, { mimeType });
              rtcMediaRecorderRef.current = recorder;
              let chunks: Blob[] = [];
              let busy = false;
              const isCurrent = () => realWebRtcSessionRef.current === session && session.isCallActive();
              const startSegment = () => {
                if (!isCurrent()) return;
                chunks = [];
                recorder.start();
                rtcRecorderTimerRef.current = setTimeout(() => {
                  if (recorder.state === 'recording') recorder.stop();
                }, 4000);
              };
              recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
              recorder.onerror = () => setRtcSTT('UNAVAILABLE');
              recorder.onstop = async () => {
                const blob = new Blob(chunks, { type: mimeType });
                // Restart a complete container; later timeslices alone lack WebM headers.
                startSegment();
                if (!isCurrent() || !blob.size) return;
                if (busy) { setRtcSTT('UNAVAILABLE'); return; }
                busy = true;
                try {
                  const file = new File([blob], mimeType.includes('ogg') ? 'remote.ogg' : 'remote.webm', { type: mimeType });
                  if (rtcVerifyIdentity && claimedSpeakerId !== 'none') {
                    // Display the actual legacy comparison without treating it as calibrated identity evidence.
                    try {
                      const speaker = await api.verifySpeaker(claimedSpeakerId, file);
                      if (isCurrent()) setRtcSpeaker(speaker);
                    } catch (error) { if (isCurrent()) setRtcAudioPlayError(`Speaker comparison unavailable: ${String(error)}`); }
                  }
                  const result = await api.transcribeAudio(file);
                  if (!isCurrent()) return;
                  if (result.engine !== 'wav2vec2_asr_base_960h') throw new Error('Remote STT unavailable');
                  setRtcSTT('ACTIVE');
                  if (result.text.trim()) {
                    rtcTranscriptRef.current = `${rtcTranscriptRef.current} ${result.text}`.trim().slice(-12000);
                    setRtcSTTTranscript(rtcTranscriptRef.current);
                  }
                  await refreshRisk();
                } catch (error) {
                  if (isCurrent()) { setRtcSTT('UNAVAILABLE'); setRtcAudioPlayError(`Remote analysis: ${String(error)}`); }
                } finally { busy = false; }
              };
              startSegment();
            }
          } catch {
            setRtcSTT('UNAVAILABLE');
            setRtcSTTTranscript('REMOTE STT UNAVAILABLE');
          }
        },
      });
    } catch (err: unknown) {
      setRtcConnection('ENDED');
      setRtcAudioPlayError(err instanceof Error ? err.message : String(err));
    }
  }

  function handleRtcToggleMute() {
    if (realWebRtcSessionRef.current) {
      const next = rtcLocalMic === 'ACTIVE';
      realWebRtcSessionRef.current.muteMicrophone(next);
      setRtcLocalMic(next ? 'MUTED' : 'ACTIVE');
    }
  }

  function handleRtcEndCall() {
    const session = realWebRtcSessionRef.current;
    realWebRtcSessionRef.current = null;
    if (rtcRecorderTimerRef.current) clearTimeout(rtcRecorderTimerRef.current);
    session?.endCall();
    setRtcSTT('UNAVAILABLE');
    if (rtcMediaRecorderRef.current && rtcMediaRecorderRef.current.state !== 'inactive') {
      try {
        rtcMediaRecorderRef.current.stop();
      } catch {
        // Ignore
      }
      rtcMediaRecorderRef.current = null;
    }
    if (rtcStreamClientRef.current) {
      rtcStreamClientRef.current.stop();
      rtcStreamClientRef.current = null;
    }
    if (remoteAudioElementRef.current) {
      remoteAudioElementRef.current.srcObject = null;
    }
    setRtcConnection('ENDED');
    setRtcRemoteAudio('WAITING');
    setRtcLocalMic('MUTED');
  }

  function handleManualPlayRemoteAudio() {
    if (remoteAudioElementRef.current) {
      remoteAudioElementRef.current.play()
        .then(() => {
          setRtcRemoteAudio('PLAYING');
          setRtcAudioPlayError(null);
        })
        .catch((err: Error) => {
          setRtcAudioPlayError(`Audio playback blocked: ${err.message}`);
        });
    }
  }

  async function handleVerifySpeaker() {
    if (claimedSpeakerId === 'none') {
      setSpeakerVerifyState({
        state: 'NOT_ENROLLED',
        similarity_score: null,
        explanation: 'No claimed speaker identity selected. Select an identity profile to verify.',
      });
      return;
    }
    setIsVerifyingSpeaker(true);
    try {
      if (attachedAudioFile) {
        const res = await api.verifySpeaker(claimedSpeakerId, attachedAudioFile);
        setSpeakerVerifyState(res);
      } else {
        setSpeakerVerifyState({
          state: 'INSUFFICIENT_AUDIO',
          similarity_score: null,
          explanation: 'Attach an audio file or stream voice to execute biometric identity comparison.',
        });
      }
    } catch (err: unknown) {
      setSpeakerVerifyState({
        state: 'IDENTITY_UNCERTAIN',
        similarity_score: null,
        explanation: err instanceof Error ? err.message : 'Verification request failed',
      });
    } finally {
      setIsVerifyingSpeaker(false);
    }
  }

  async function handleEndCall(outcome: string) {
    setIsStreamingMic(false);
    if (liveSTTRef.current) {
      liveSTTRef.current.stop();
    }
    setInterimSTT('');

    if (streamClientRef.current?.isStreaming()) {
      try {
        const summary = await streamClientRef.current.stop();
        if (summary) {
          setFinalSessionSummary(summary);
        }
      } catch {
        // Ignore stop error
      }
    }
    setCall((previous) => ({
      ...previous,
      status: 'ended',
      outcome,
    }));
  }

  function resetToNewDemo() {
    if (streamClientRef.current) {
      streamClientRef.current.disconnect();
      streamClientRef.current = null;
    }
    setIsStreamingMic(false);
    latestUpdateRef.current = null;
    setLiveAcousticUpdates([]);
    setFinalSessionSummary(null);
    setUserOverrideWarning(false);
    setLiveError(null);

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
    <div className="mx-auto max-w-6xl space-y-6 text-slate-900 font-sans">
      {/* Header */}
      <div className="space-y-2 border-b border-slate-200 pb-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
            DUAL-LAYER DEFENSE DEMO
          </span>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-slate-100 text-slate-700 border border-slate-200">
            PHASE 2.5 SCENARIO AUTOMATION
          </span>
          <span
            className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-bold ${
              backendDetectionEngine === 'aasist' && isBackendAasistReady
                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                : backendDetectionEngine === 'mock'
                ? 'bg-amber-50 text-amber-800 border border-amber-200'
                : 'bg-red-50 text-red-800 border border-red-200'
            }`}
          >
            {backendDetectionEngine === 'aasist' && isBackendAasistReady
              ? `AASIST ENGINE (${backendModelVersion})`
              : backendDetectionEngine === 'mock'
              ? 'MOCK ENGINE (mock-v1)'
              : 'ACOUSTIC UNAVAILABLE'}
          </span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Scam Call & Voice Cloning Protection</h1>
        <p className="text-sm text-slate-600 max-w-3xl">
          Unified defense correlating <strong>Acoustic Analysis</strong> ({backendDetectionEngine === 'mock' ? 'Mock Detection heuristic simulator' : backendDetectionEngine === 'aasist' && isBackendAasistReady ? 'AASIST SincNet synthetic voice detection' : 'Acoustic layer unavailable'}) with{' '}
          <strong>Semantic Defense</strong> (conversational intent heuristics). Features real two-peer WebRTC calling and interactive scenario simulations without placing real carrier calls.
        </p>
        <div className="text-xs font-mono text-slate-500 flex items-center gap-2 pt-0.5">
          <span className="inline-block w-2 h-2 rounded-full bg-indigo-600"></span>
          <span>Engine Status: {backendStatusMessage}</span>
        </div>
      </div>

      {/* Presentation Demo Mode: Compact Automation Section */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 flex items-center gap-1.5">
                <Sparkles className="w-3 h-3" />
                DEMO MODE AUTOMATION
              </span>
              <span className="text-xs font-mono text-slate-500">Presentation Ready</span>
            </div>
            <h2 className="text-xl font-bold tracking-tight text-slate-900 mt-1">Presentation Scenario Runner</h2>
            <p className="text-xs text-slate-600 mt-0.5">
              Select a scenario to populate the transcript and click <strong>Run Scenario</strong> for an immediate dual-layer assessment.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleRunScenario}
              disabled={isRunningScenario}
              className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-mono font-bold text-xs uppercase tracking-wider flex items-center gap-2 shadow-xs transition-all disabled:opacity-50 cursor-pointer"
            >
              <Play className="w-4 h-4 fill-current" />
              {isRunningScenario ? 'Executing Backend Analysis…' : 'Run Scenario'}
            </button>
            <button
              type="button"
              onClick={resetToNewDemo}
              disabled={busy}
              className={`${secondaryBtn} flex items-center gap-1.5`}
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
                    ? 'border-indigo-500 bg-indigo-50/70 ring-1 ring-indigo-500/30 shadow-xs'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/70 shadow-xs'
                }`}
              >
                <div className="flex items-start justify-between gap-2 min-h-[32px]">
                  <span className={`text-xs font-mono font-bold leading-snug ${isSelected ? 'text-indigo-950' : 'text-slate-800'}`}>
                    {item.title}
                  </span>
                  {item.id === 'ordinary' ? (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 shrink-0 font-semibold">
                      BENIGN
                    </span>
                  ) : (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-red-50 text-red-800 border border-red-200 shrink-0 font-semibold">
                      SCAM
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-600 mt-1 line-clamp-2 leading-relaxed">
                  {item.impersonationContext}
                </p>
              </button>
            );
          })}
        </div>

        {/* 4-Stage Presentation Sequence Display */}
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between text-xs font-mono text-slate-600 border-b border-slate-200 pb-2">
            <span className="uppercase font-bold tracking-wider text-slate-700">
              Execution Sequence: Select Scenario → Run Scenario → Acoustic Analysis → Semantic Analysis → Unified Verdict
            </span>
            <span className="text-[11px] text-slate-500 font-medium">
              {isRunningScenario
                ? 'Status: Evaluating dual-layer telemetry…'
                : call.acoustic.status === 'not_analyzed'
                ? 'Status: Ready to Run (Click "Run Scenario")'
                : 'Status: Dual-layer assessment completed'}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs font-mono">
            {/* Step 1: Scenario Context */}
            <div className="p-3 rounded-lg bg-white border border-slate-200 space-y-1.5 shadow-xs">
              <div className="flex items-center gap-1.5 text-indigo-700">
                <span className="w-4 h-4 rounded-full bg-indigo-100 text-indigo-700 text-[10px] flex items-center justify-center font-bold">1</span>
                <span className="font-bold uppercase tracking-wider text-[11px]">Scenario Context</span>
              </div>
              <p className="text-slate-900 font-bold">{scenario.name}</p>
              <p className="text-[11px] text-slate-600">Caller: {scenario.caller}</p>
              <p className="text-[11px] text-slate-500 italic line-clamp-2">{scenario.impersonationContext}</p>
              <div className="pt-1">
                {scenario.sampleAudioPath ? (
                  <span className="inline-block text-[10px] text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-semibold">
                    Audio Fixture: {scenario.sampleAudioPath}
                  </span>
                ) : attachedAudioFile ? (
                  <span className="inline-block text-[10px] text-indigo-800 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200 truncate max-w-full font-semibold">
                    Attached Clip: {attachedAudioFile.name}
                  </span>
                ) : (
                  <span className="inline-block text-[10px] text-slate-600 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                    Audio: None (Semantic mode)
                  </span>
                )}
              </div>
            </div>

            {/* Step 2: Acoustic Defense */}
            <div className="p-3 rounded-lg bg-white border border-slate-200 space-y-1.5 shadow-xs">
              <div className="flex items-center gap-1.5 text-indigo-700">
                <span className="w-4 h-4 rounded-full bg-indigo-100 text-indigo-700 text-[10px] flex items-center justify-center font-bold">2</span>
                <span className="font-bold uppercase tracking-wider text-[11px]">Acoustic Defense</span>
              </div>
              <div>
                <span
                  className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                    call.acoustic.status === 'synthetic_detected'
                      ? 'bg-red-50 text-red-800 border border-red-200'
                      : call.acoustic.status === 'likely_genuine'
                      ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                      : isAcousticUnavailable
                      ? 'bg-amber-50 text-amber-800 border border-amber-200'
                      : 'bg-slate-100 text-slate-700 border border-slate-200'
                  }`}
                >
                  {call.acoustic.label}
                </span>
              </div>
              <div className="text-[11px] text-slate-600 space-y-0.5 pt-0.5">
                <p>Engine: <span className="text-slate-800 font-semibold">{call.acoustic.engineType || (backendDetectionEngine === 'mock' ? 'MOCK ENGINE' : backendDetectionEngine === 'aasist' && isBackendAasistReady ? 'AASIST' : 'ACOUSTIC UNAVAILABLE')}</span></p>
                <p>
                  P(synthetic):{' '}
                  <span className="text-slate-900 font-bold">
                    {call.acoustic.syntheticProbability !== null
                      ? `${(call.acoustic.syntheticProbability * 100).toFixed(1)}%`
                      : 'Not evaluated'}
                  </span>
                </p>
                {call.acoustic.confidence !== null && (
                  <p>Confidence: {(call.acoustic.confidence * 100).toFixed(1)}%</p>
                )}
                <p>Policy Action: <span className="text-slate-800 font-semibold">{call.acoustic.action || 'NOT_EVALUATED'}</span></p>
              </div>
            </div>

            {/* Step 3: Semantic Defense */}
            <div className="p-3 rounded-lg bg-white border border-slate-200 space-y-1.5 shadow-xs">
              <div className="flex items-center gap-1.5 text-amber-700">
                <span className="w-4 h-4 rounded-full bg-amber-100 text-amber-800 text-[10px] flex items-center justify-center font-bold">3</span>
                <span className="font-bold uppercase tracking-wider text-[11px]">Semantic Defense</span>
              </div>
              <div>
                <span
                  className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                    call.semantic.risk === 'high'
                      ? 'bg-red-50 text-red-800 border border-red-200'
                      : call.semantic.risk === 'warning'
                      ? 'bg-amber-50 text-amber-800 border border-amber-200'
                      : call.semantic.risk === 'no_indicators'
                      ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                      : 'bg-slate-100 text-slate-700 border border-slate-200'
                  }`}
                >
                  Risk: {call.semantic.risk.toUpperCase()}
                </span>
              </div>
              {call.semantic.reasons.length > 0 ? (
                <ul className="text-[10px] text-amber-900 space-y-0.5 list-disc pl-3 mt-1 font-medium">
                  {call.semantic.reasons.map((r, i) => (
                    <li key={i} className="line-clamp-2">{r}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-[11px] text-slate-500 italic mt-1">No scam indicators flagged</p>
              )}
            </div>

            {/* Step 4: Unified Verdict */}
            <div className="p-3 rounded-lg bg-white border border-slate-200 space-y-1.5 shadow-xs">
              <div className="flex items-center gap-1.5 text-purple-700">
                <span className="w-4 h-4 rounded-full bg-purple-100 text-purple-700 text-[10px] flex items-center justify-center font-bold">4</span>
                <span className="font-bold uppercase tracking-wider text-[11px]">Unified Verdict</span>
              </div>
              <div>
                <span
                  className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-mono font-bold ${
                    call.unified.verdict === 'HIGH'
                      ? 'bg-red-50 text-red-800 border border-red-200'
                      : call.unified.verdict === 'MEDIUM'
                      ? 'bg-amber-50 text-amber-800 border border-amber-200'
                      : call.unified.verdict === 'LOW'
                      ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                      : 'bg-slate-100 text-slate-700 border border-slate-200'
                  }`}
                >
                  {call.unified.verdict}
                </span>
              </div>
              <p className="text-[11px] text-slate-900 font-bold line-clamp-2 mt-0.5">
                {call.unified.headline}
              </p>
              <p className="text-[10px] text-slate-600 line-clamp-3 italic">
                {call.unified.explanation}
              </p>
            </div>
          </div>
        </div>

        {/* Phase 11: Speaker Impersonation Defense Panel */}
        <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3 shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
            <div className="flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-indigo-600" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-800">
                Speaker Impersonation Defense & Voice Biometrics
              </span>
            </div>
            <span className="text-[11px] font-mono text-slate-500">
              Biometric Vocal-Tract Embeddings (Addresses Human Social Engineering)
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-center text-xs font-mono">
            <div>
              <label className="text-[11px] text-slate-600 block mb-1">Claimed Caller Identity:</label>
              <select
                value={claimedSpeakerId}
                onChange={(e) => {
                  setClaimedSpeakerId(e.target.value);
                  setSpeakerVerifyState(null);
                }}
                className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-800 text-xs focus:outline-none focus:border-indigo-500 shadow-xs"
              >
                <option value="none">Unverified External Caller (No Identity Claim)</option>
                {enrolledSpeakers.map((spk) => (
                  <option key={spk.speaker_id} value={spk.speaker_id}>
                    {spk.speaker_name} ({spk.speaker_id})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-[11px] text-slate-600 block mb-1">Identity Verification:</label>
              <button
                type="button"
                onClick={handleVerifySpeaker}
                disabled={isVerifyingSpeaker || claimedSpeakerId === 'none'}
                className="w-full py-2 px-3 rounded-lg font-mono font-bold text-xs flex items-center justify-center gap-1.5 transition-all shadow-xs disabled:bg-slate-100 disabled:text-slate-400 disabled:border disabled:border-slate-200 disabled:cursor-not-allowed bg-indigo-600 hover:bg-indigo-700 text-white cursor-pointer"
              >
                <UserCheck className="w-3.5 h-3.5" />
                {isVerifyingSpeaker ? 'Comparing Biometrics…' : 'Verify Voice Biometrics'}
              </button>
            </div>

            <div>
              <label className="text-[11px] text-slate-600 block mb-1">Biometric Decision:</label>
              <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between min-h-[38px]">
                {speakerVerifyState ? (
                  <span
                    className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                      speakerVerifyState.state === 'IDENTITY_MATCH'
                        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                        : speakerVerifyState.state === 'IDENTITY_MISMATCH'
                        ? 'bg-red-50 text-red-800 border border-red-200 animate-pulse'
                        : 'bg-amber-50 text-amber-800 border border-amber-200'
                    }`}
                  >
                    {speakerVerifyState.state === 'IDENTITY_MATCH'
                      ? 'IDENTITY MATCH'
                      : speakerVerifyState.state === 'IDENTITY_MISMATCH'
                      ? 'IMPERSONATION DETECTED'
                      : speakerVerifyState.state}
                    {speakerVerifyState.similarity_score !== null
                      ? ` (r=${speakerVerifyState.similarity_score.toFixed(3)})`
                      : ''}
                  </span>
                ) : (
                  <span className="text-[11px] text-slate-500 italic">No verification performed</span>
                )}
              </div>
            </div>
          </div>

          {speakerVerifyState && (
            <p className="text-[11px] font-mono text-slate-700 bg-slate-50 p-2 rounded border border-slate-200">
              {speakerVerifyState.explanation}
            </p>
          )}
        </div>

        {/* Error or Notice Alert Banner */}
        {runError && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs font-mono text-red-900 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{runError}</span>
          </div>
        )}

        {isAcousticUnavailable && call.acoustic.errorMessage && (
          <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs font-mono text-amber-900 flex items-start gap-2">
            <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
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
        className={`rounded-2xl border p-6 space-y-3 transition-all shadow-xs ${
          call.unified.verdict === 'HIGH'
            ? 'border-red-200 bg-gradient-to-b from-red-50/90 via-red-50/40 to-white text-slate-900'
            : call.unified.verdict === 'MEDIUM'
            ? 'border-amber-200 bg-gradient-to-b from-amber-50/90 via-amber-50/40 to-white text-slate-900'
            : call.unified.verdict === 'LOW'
            ? 'border-emerald-200 bg-gradient-to-b from-emerald-50/90 via-emerald-50/40 to-white text-slate-900'
            : 'border-slate-200 bg-white text-slate-900'
        }`}
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-slate-200 pb-3">
          <div className="flex items-center gap-3">
            {call.unified.verdict === 'HIGH' && <ShieldAlert className="w-6 h-6 text-red-600 animate-pulse" />}
            {call.unified.verdict === 'MEDIUM' && <AlertTriangle className="w-6 h-6 text-amber-600" />}
            {call.unified.verdict === 'LOW' && <CheckCircle2 className="w-6 h-6 text-emerald-600" />}
            {call.unified.verdict === 'UNASSESSED' && <Info className="w-6 h-6 text-slate-500" />}
            <div>
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-slate-500">
                Unified Threat Assessment
              </span>
              <h2 className="text-xl font-bold text-slate-900">{call.unified.headline}</h2>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider ${
                call.unified.verdict === 'HIGH'
                  ? 'bg-red-50 text-red-800 border border-red-200'
                  : call.unified.verdict === 'MEDIUM'
                  ? 'bg-amber-50 text-amber-800 border border-amber-200'
                  : call.unified.verdict === 'LOW'
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                  : 'bg-slate-100 text-slate-700 border border-slate-200'
              }`}
            >
              Verdict: {call.unified.verdict}
            </span>
          </div>
        </div>

        <p className="text-sm text-slate-700 leading-relaxed">{call.unified.explanation}</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono pt-1">
          <div className="bg-slate-50 rounded-xl p-3 border border-slate-200 space-y-1">
            <span className="text-slate-500 uppercase font-semibold">Layer 1 (Acoustic Telemetry):</span>
            <p className="text-slate-800 font-medium">{call.unified.acousticSummary}</p>
          </div>
          <div className="bg-slate-50 rounded-xl p-3 border border-slate-200 space-y-1">
            <span className="text-slate-500 uppercase font-semibold">Layer 2 (Semantic Intent):</span>
            <p className="text-slate-800 font-medium">{call.unified.semanticSummary}</p>
          </div>
        </div>

        <div className="pt-2 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-t border-slate-200">
          <p className="font-semibold text-indigo-950">{call.unified.recommendedAction}</p>
          <span className="text-[11px] text-slate-500 max-w-md">{call.unified.disclaimer}</span>
        </div>

        {call.status === 'active' && call.unified.verdict === 'HIGH' && autoEnd && (
          <p className="text-xs font-bold text-red-700 animate-pulse">
            Safety protocol active: Automatically terminating simulated call in two seconds…
          </p>
        )}
      </div>

      {/* Standalone REAL WEBRTC CALL (TWO PEERS) Section */}
      <section className="rounded-2xl border-2 border-indigo-200 bg-white p-6 space-y-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-indigo-100 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-600">
              <Globe className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-slate-900 tracking-wide">
                  REAL WEBRTC CALL (TWO PEERS)
                </h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                  LIVE AUDIO TRANSMISSION
                </span>
              </div>
              <p className="text-xs font-mono text-slate-600 mt-0.5">
                Authentic cross-tab WebRTC voice call. Open two browser tabs: Tab A (Caller) streams real microphone audio to Tab B (Protected User) for live acoustic analysis and optional experimental speaker comparison.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider ${
                rtcConnection === 'CONNECTED'
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 animate-pulse'
                  : rtcConnection === 'CONNECTING'
                  ? 'bg-amber-50 text-amber-800 border border-amber-200 animate-pulse'
                  : 'bg-slate-100 text-slate-700 border border-slate-200'
              }`}
            >
              Peer Status: {rtcConnection}
            </span>
          </div>
        </div>

        {/* Hidden Audio Element for Protected User playback */}
        <audio ref={remoteAudioElementRef} autoPlay playsInline />

        {/* Controls Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Step 1: Select Role */}
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2.5 font-mono text-xs">
            <span className="text-slate-700 font-bold uppercase tracking-wider block">
              1. Choose Tab Role
            </span>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setRtcRole('caller')}
                disabled={rtcConnection === 'CONNECTING' || rtcConnection === 'CONNECTED'}
                className={`py-2 px-3 rounded-lg border font-bold text-center transition-all cursor-pointer ${
                  rtcRole === 'caller'
                    ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                    : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100 shadow-xs'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                Tab A: Caller
              </button>
              <button
                type="button"
                onClick={() => setRtcRole('protected_user')}
                disabled={rtcConnection === 'CONNECTING' || rtcConnection === 'CONNECTED'}
                className={`py-2 px-3 rounded-lg border font-bold text-center transition-all cursor-pointer ${
                  rtcRole === 'protected_user'
                    ? 'bg-emerald-600 text-white border-emerald-600 shadow-xs'
                    : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100 shadow-xs'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                Tab B: Protected User
              </button>
            </div>
            <p className="text-[11px] text-slate-600 leading-tight">
              {rtcRole === 'caller'
                ? 'Caller tab captures your microphone and transmits live audio tracks over WebRTC peer connection.'
                : 'Protected User tab receives caller audio, plays it audibly out loud, and streams it to the detection backend.'}
            </p>
          </div>

          {/* Step 2: Room ID */}
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2.5 font-mono text-xs">
            <span className="text-slate-700 font-bold uppercase tracking-wider block">
              2. Signaling Room ID
            </span>
            <input
              type="text"
              value={rtcRoomId}
              onChange={(e) => setRtcRoomId(e.target.value.trim().toLowerCase())}
              disabled={rtcConnection === 'CONNECTING' || rtcConnection === 'CONNECTED'}
              placeholder="e.g. voiceguard-test"
              className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-800 text-xs focus:outline-none focus:border-indigo-500 font-mono shadow-xs disabled:opacity-50"
            />
            <p className="text-[11px] text-slate-600 leading-tight">
              Signaling runs via WebSocket <code>/api/v1/webrtc/signal/{'{room_id}'}</code> + BroadcastChannel fallback.
            </p>
          </div>

          {/* Step 3: Action Buttons */}
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2.5 font-mono text-xs flex flex-col justify-between">
            <span className="text-slate-700 font-bold uppercase tracking-wider block">
              3. Call Session Actions
            </span>
            <div className="flex flex-wrap items-center gap-2">
              {rtcConnection === 'IDLE' || rtcConnection === 'ENDED' ? (
                rtcRole === 'caller' ? (
                  <button
                    type="button"
                    onClick={handleRtcStartCaller}
                    className="flex-1 py-2 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold flex items-center justify-center gap-1.5 transition-all shadow-xs cursor-pointer"
                  >
                    <Phone className="w-4 h-4" /> Create Room (Caller)
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleRtcJoinProtectedUser}
                    className="flex-1 py-2 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold flex items-center justify-center gap-1.5 transition-all shadow-xs cursor-pointer"
                  >
                    <Phone className="w-4 h-4" /> Join Room (Protected User)
                  </button>
                )
              ) : (
                <>
                  {rtcRole === 'caller' && (
                    <button
                      type="button"
                      onClick={handleRtcToggleMute}
                      className={`py-2 px-3 rounded-lg border font-bold flex items-center gap-1.5 cursor-pointer shadow-xs ${
                        rtcLocalMic === 'ACTIVE'
                          ? 'bg-amber-600 hover:bg-amber-700 text-white border-amber-600'
                          : 'bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-600'
                      }`}
                    >
                      {rtcLocalMic === 'ACTIVE' ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                      {rtcLocalMic === 'ACTIVE' ? 'Mute Mic' : 'Unmute Mic'}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={handleRtcEndCall}
                    className="flex-1 py-2 px-3 rounded-lg bg-red-600 hover:bg-red-700 text-white font-bold flex items-center justify-center gap-1.5 transition-all shadow-xs cursor-pointer"
                  >
                    <PhoneOff className="w-4 h-4" /> End Call
                  </button>
                </>
              )}
            </div>

            {rtcConnection === 'CONNECTING' && (
              <p className="text-[11px] text-amber-700 animate-pulse font-medium">
                Exchanging SDP offer/answer with signaling room…
              </p>
            )}
          </div>
        </div>

        {/* Autoplay blocked error banner with manual button */}
        {rtcAudioPlayError && (
          <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono">
            <div className="flex items-center gap-2 text-amber-900">
              <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600" />
              <span>{rtcAudioPlayError}</span>
            </div>
            {rtcRole === 'protected_user' && (
              <button
                type="button"
                onClick={handleManualPlayRemoteAudio}
                className="py-1.5 px-3 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-bold shrink-0 transition-all shadow-xs cursor-pointer"
              >
                Play Remote Audio
              </button>
            )}
          </div>
        )}

        {/* Telemetry Status Bar */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 font-mono text-xs">
          {/* Connection */}
          <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-xs">
            <span className="text-slate-500 uppercase block text-[10px]">WebRTC Connection</span>
            <span
              className={`font-bold mt-1 inline-block ${
                rtcConnection === 'CONNECTED'
                  ? 'text-emerald-700'
                  : rtcConnection === 'CONNECTING'
                  ? 'text-amber-700'
                  : 'text-slate-600'
              }`}
            >
              {rtcConnection}
            </span>
          </div>

          {/* Local Mic */}
          <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-xs">
            <span className="text-slate-500 uppercase block text-[10px]">Local Microphone</span>
            <span
              className={`font-bold mt-1 inline-block ${
                rtcLocalMic === 'ACTIVE'
                  ? 'text-emerald-700'
                  : rtcLocalMic === 'MUTED'
                  ? 'text-amber-700'
                  : rtcLocalMic === 'ERROR'
                  ? 'text-red-700'
                  : 'text-slate-600'
              }`}
            >
              {rtcLocalMic}
            </span>
          </div>

          {/* Remote Audio */}
          <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-xs">
            <span className="text-slate-500 uppercase block text-[10px]">Remote Audio</span>
            <span
              className={`font-bold mt-1 inline-block ${
                rtcRemoteAudio === 'PLAYING'
                  ? 'text-emerald-700'
                  : rtcRemoteAudio === 'ACTIVE'
                  ? 'text-indigo-700'
                  : rtcRemoteAudio === 'ERROR'
                  ? 'text-red-700'
                  : 'text-slate-600'
              }`}
            >
              {rtcRemoteAudio}
            </span>
          </div>

          {/* Acoustic Engine */}
          <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-xs">
            <span className="text-slate-500 uppercase block text-[10px]">Acoustic Engine</span>
            <span
              className={`font-bold mt-1 inline-block ${
                backendDetectionEngine === 'mock'
                  ? 'text-indigo-700'
                  : backendDetectionEngine === 'aasist' && isBackendAasistReady
                  ? 'text-emerald-700'
                  : 'text-amber-700'
              }`}
            >
              {rtcAcousticUpdate ? `${rtcAcousticUpdate.engine || 'UNKNOWN'} (${rtcAcousticUpdate.model_version})` : rtcAcousticError ? 'UNAVAILABLE' : 'AASIST requested — awaiting inference'}
            </span>
          </div>

          {/* STT Status */}
          <div className="bg-white p-3 rounded-xl border border-slate-200 col-span-2 md:col-span-1 shadow-xs">
            <span className="text-slate-500 uppercase block text-[10px]">Remote STT</span>
            <span
              className={`font-bold mt-1 inline-block ${
                rtcSTT === 'ACTIVE' ? 'text-emerald-700' : 'text-slate-600'
              }`}
            >
              {rtcSTT}
            </span>
          </div>
        </div>

        <p className="text-xs text-slate-500">{rtcDiagnostics}. Analysis source: received remote stream. WebRTC capture-domain performance is unvalidated. Softmax scores are uncalibrated and do not establish caller identity.</p>
        <p className="text-xs text-slate-500">{rtcAudioDiagnostics}</p>
        {rtcRole === 'protected_user' && (
          <div className="my-4 p-4 border border-indigo-200 bg-indigo-50/50 rounded-xl text-slate-800 space-y-1.5 font-mono text-xs">
            <div className="font-bold text-indigo-950">Unified threat: {rtcRisk?.overall_risk || 'UNASSESSED'}</div>
            <p>{rtcRisk?.headline}</p>
            <p className="text-slate-600">{rtcRisk?.explanation}</p>
            <p>Semantic intent: <span className="font-semibold">{String((rtcRisk?.evidence_layers.semantic as Record<string, unknown> | undefined)?.primary_intent || 'UNASSESSED')}</span></p>
            <p className="text-slate-600">Identity: UNVERIFIED — existing MFCC comparison is experimental.</p>
            <label className="flex items-center gap-2 cursor-pointer pt-1">
              <input type="checkbox" checked={rtcVerifyIdentity} disabled={rtcConnection === 'CONNECTED' || rtcConnection === 'CONNECTING'} onChange={event => setRtcVerifyIdentity(event.target.checked)} className="rounded border-slate-300 text-indigo-600" />
              <span>Compare remote audio with the enrolled identity selected above (experimental; choose before joining).</span>
            </label>
            {rtcSpeaker && <p className="text-indigo-900 font-medium pt-1">MFCC comparison: {rtcSpeaker.state}; cosine similarity: {rtcSpeaker.similarity_score ?? 'unavailable'}. {rtcSpeaker.explanation} This result is not used as calibrated identity evidence in live risk fusion.</p>}
            <p className="text-slate-500 italic pt-1">Verify the caller independently. Low risk does not guarantee safety.</p>
          </div>
        )}
        {/* Live Call Telemetry for Protected User */}
        {rtcRole === 'protected_user' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
            {/* Remote Audio Acoustic Analysis */}
            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3 shadow-xs">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <span className="text-slate-700 font-bold uppercase text-[11px] flex items-center gap-1.5">
                  <Radio className="w-3.5 h-3.5 text-indigo-600" />
                  Remote Caller Acoustic Analysis
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    rtcAcousticUpdate?.action === 'BLOCK'
                      ? 'bg-red-50 text-red-800 border border-red-200'
                      : rtcAcousticUpdate?.action === 'VERIFY'
                      ? 'bg-amber-50 text-amber-800 border border-amber-200'
                      : rtcAcousticUpdate
                      ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                      : 'bg-slate-100 text-slate-700 border border-slate-200'
                  }`}
                >
                  {rtcAcousticUpdate ? rtcAcousticUpdate.action : 'WAITING FOR REMOTE AUDIO'}
                </span>
              </div>

              {rtcAcousticError ? (
                <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 text-[11px]">
                  {rtcAcousticError}
                </div>
              ) : rtcAcousticUpdate ? (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div>
                      <span className="text-slate-500">Engine:</span>{' '}
                      <span className="text-slate-800 font-bold">
                        {rtcAcousticUpdate.engine === 'aasist'
                          ? 'AASIST (aasist-v1)'
                          : 'MOCK ENGINE (mock-v1)'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">P(synthetic):</span>{' '}
                      <span
                        className={`font-bold ${
                          rtcAcousticUpdate.synthetic_probability >= 0.7
                            ? 'text-red-700'
                            : rtcAcousticUpdate.synthetic_probability < 0.5
                            ? 'text-emerald-700'
                            : 'text-amber-700'
                        }`}
                      >
                        {(rtcAcousticUpdate.synthetic_probability * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Window Count:</span>{' '}
                      <span className="text-slate-800 font-bold">
                        {rtcAcousticUpdate.window_index}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Confidence:</span>{' '}
                      <span className="text-slate-800 font-bold">
                        {((rtcAcousticUpdate.confidence ?? rtcAcousticUpdate.synthetic_probability) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  {/* Window History Mini-Bars */}
                  {rtcAcousticWindows.length > 0 && (
                    <div className="space-y-1 pt-1">
                      <span className="text-[10px] text-slate-500 uppercase">Recent Sliding Windows:</span>
                      <div className="flex items-end gap-1 h-8 bg-slate-50 p-1 rounded border border-slate-200">
                        {rtcAcousticWindows.map((w, i) => (
                          <div
                            key={i}
                            className={`flex-1 rounded-xs transition-all ${
                              w.synthetic_probability >= 0.7
                                ? 'bg-red-500'
                                : w.synthetic_probability >= 0.5
                                ? 'bg-amber-500'
                                : 'bg-emerald-500'
                            }`}
                            style={{ height: `${Math.max(15, w.synthetic_probability * 100)}%` }}
                            title={`Window ${w.window_index}: ${(w.synthetic_probability * 100).toFixed(1)}%`}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-[11px] text-slate-500 italic">
                  {rtcConnection === 'CONNECTED'
                    ? 'Buffering remote caller audio stream (resampling to 16 kHz mono PCM for live detection WebSocket)…'
                    : 'Establish WebRTC connection from Tab A (Caller) to begin receiving remote audio.'}
                </p>
              )}

              <p className="text-[10px] text-slate-500 italic pt-1 border-t border-slate-100">
                Audio source: Caller MediaStream via <code>pc.ontrack</code>. Protected User local microphone is never analyzed.
              </p>
            </div>

            {/* Remote Caller STT & Transcript */}
            <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3 shadow-xs">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <span className="text-slate-700 font-bold uppercase text-[11px] flex items-center gap-1.5">
                  <Waves className="w-3.5 h-3.5 text-indigo-600" />
                  Remote Caller Speech-to-Text
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    rtcSTT === 'ACTIVE'
                      ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                      : 'bg-slate-100 text-slate-700 border border-slate-200'
                  }`}
                >
                  {rtcSTT}
                </span>
              </div>

              <div className="min-h-[70px] max-h-[120px] overflow-y-auto p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                {rtcSTTTranscript ? (
                  <p className="text-slate-900 leading-relaxed font-sans">{rtcSTTTranscript}</p>
                ) : (
                  <p className="text-slate-500 italic">
                    {rtcConnection === 'CONNECTED'
                      ? 'Listening for caller speech (transcribing remote chunks via backend Wav2Vec2 CTC)…'
                      : 'No caller transcript. Real WebRTC Call does not inject mock transcripts.'}
                  </p>
                )}
              </div>

              <p className="text-[10px] text-slate-500 italic pt-1 border-t border-slate-100">
                Browser Web Speech API restriction: Cannot capture remote WebRTC MediaStreams. Transcription is performed directly by the backend STT service on remote audio chunks.
              </p>
            </div>
          </div>
        )}
      </section>

      {/* Two-Column Workspace */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left Column: Call Controls & Layer 1 Acoustic Defense */}
        <section className="space-y-6">
          {/* Interactive Call Simulator Box */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4 shadow-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-800">
                Interactive Call Simulator
              </h3>
              <label className="flex items-center gap-2 text-xs font-mono text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  className="rounded border-slate-300 bg-white text-indigo-600 focus:ring-0"
                  checked={autoEnd}
                  onChange={(event) => setAutoEnd(event.target.checked)}
                />
                <span>Auto-Terminate on HIGH</span>
              </label>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center space-y-3">
              <div className="relative inline-block">
                <Phone className={`mx-auto h-10 w-10 ${busy ? 'text-indigo-600 animate-bounce' : 'text-slate-400'}`} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-900">{scenario.caller}</h2>
                <p className="text-xs font-mono uppercase tracking-wider text-slate-500 mt-0.5">
                  {call.status === 'idle'
                    ? 'Ready for incoming call simulation'
                    : call.status === 'active'
                    ? 'Connected · Monitoring Dual-Layer Telemetry'
                    : call.status === 'ringing'
                    ? 'Incoming simulated call ringing…'
                    : 'Call session ended'}
                </p>

                {call.status === 'active' && (
                  <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
                    {isStreamingMic ? (
                      <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-mono animate-pulse font-medium">
                        <Waves className="w-3.5 h-3.5 text-indigo-600" />
                        Live Microphone Stream Active (16 kHz PCM)
                      </span>
                    ) : liveError ? (
                      <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 text-amber-800 border border-amber-200 text-xs font-mono font-medium">
                        <MicOff className="w-3.5 h-3.5 text-amber-600" />
                        Microphone Offline — Semantic Monitoring Active
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200 text-xs font-mono font-medium">
                        <Mic className="w-3.5 h-3.5" />
                        Dual-Layer Monitoring Active
                      </span>
                    )}

                    <button
                      type="button"
                      onClick={() => setUseLiveSTT((prev) => !prev)}
                      className={`flex items-center gap-1 px-2.5 py-0.5 rounded-full border text-[11px] font-mono transition-all cursor-pointer font-medium ${
                        useLiveSTT
                          ? 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100'
                          : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'
                      }`}
                      title="Click to toggle continuous Speech-to-Text transcription"
                    >
                      <Bot className="w-3 h-3" />
                      {useLiveSTT ? (sttStatus === 'listening' ? 'STT Transcribing Live…' : 'STT Active') : 'STT Paused'}
                    </button>

                    {mlScamData && (
                      <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-purple-50 text-purple-800 border border-purple-200 text-[11px] font-mono font-medium">
                        <Zap className="w-3 h-3 text-purple-600" />
                        ML Intent: {mlScamData.primary_intent} ({(mlScamData.scam_probability * 100).toFixed(0)}%)
                      </span>
                    )}
                  </div>
                )}

                {interimSTT && (
                  <p className="text-xs font-mono text-indigo-700 italic text-center pt-1 animate-pulse">
                    Transcribing: &ldquo;{interimSTT}&hellip;&rdquo;
                  </p>
                )}
              </div>

              {/* In-Call High Threat Warning Banner with Continue / End Call Options */}
              {call.status === 'active' && call.unified.verdict === 'HIGH' && !userOverrideWarning && (
                <div
                  role="alert"
                  className="p-3.5 rounded-xl bg-red-50 border border-red-200 space-y-2 text-left my-2 shadow-xs"
                >
                  <div className="flex items-center gap-2 text-red-800 font-bold text-xs font-mono">
                    <ShieldAlert className="w-4 h-4 text-red-600 animate-pulse shrink-0" />
                    <span>HIGH THREAT DETECTED IN ACTIVE CALL</span>
                  </div>
                  <p className="text-[11px] text-red-900 font-mono leading-relaxed">
                    Acoustic telemetry flagged synthetic voice characteristics and conversational analysis detected overt scam demands.
                  </p>
                  <div className="flex flex-wrap gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => handleEndCall('Terminated immediately by user upon high threat alert')}
                      className="px-3.5 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-mono font-bold text-xs flex items-center gap-1.5 shadow-xs cursor-pointer transition-all"
                    >
                      <PhoneOff className="w-3.5 h-3.5" /> End Call Immediately
                    </button>
                    <button
                      type="button"
                      onClick={() => setUserOverrideWarning(true)}
                      className="px-3 py-1.5 rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 font-mono text-xs cursor-pointer transition-all shadow-xs"
                    >
                      Continue Call (Acknowledge Risk)
                    </button>
                  </div>
                </div>
              )}

              <div className="flex flex-wrap justify-center gap-3 pt-2">
                {call.status === 'idle' && (
                  <button
                    className={primaryBtn}
                    onClick={startCall}
                  >
                    Simulate Incoming Call
                  </button>
                )}
                {call.status === 'ringing' && (
                  <>
                    <button
                      className={successBtn}
                      onClick={() => handleAnswerCall()}
                    >
                      <Mic className="w-3.5 h-3.5" /> Answer & Stream Audio
                    </button>
                    <button
                      className={secondaryDangerBtn}
                      onClick={() => handleEndCall('Declined before answering')}
                    >
                      Decline
                    </button>
                  </>
                )}
                {call.status === 'active' && (
                  <button
                    className={dangerBtn}
                    onClick={() => handleEndCall('Ended by user')}
                  >
                    <PhoneOff className="h-4 w-4" /> End Call
                  </button>
                )}
                {call.status === 'ended' && (
                  <button
                    className={secondaryBtn}
                    onClick={resetToNewDemo}
                  >
                    Reset Call Simulator
                  </button>
                )}
              </div>

              {/* Call Outcome & Final Security Explanation Card */}
              {call.status === 'ended' && (
                <div className="space-y-3 pt-2">
                  <p role="status" className="rounded-lg bg-slate-100 border border-slate-200 p-2.5 text-xs font-mono text-slate-600 text-center">
                    {call.outcome || 'Call session completed'}. No real telephone carrier calls or hardware lines affected.
                  </p>

                  <div className="rounded-xl border border-slate-200 bg-white p-4 text-left space-y-2.5 font-mono text-xs shadow-xs">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                      <span className="text-slate-700 uppercase font-bold text-[11px] flex items-center gap-1.5">
                        <Info className="w-3.5 h-3.5 text-indigo-600" />
                        Final Security Explanation
                      </span>
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                          call.unified.verdict === 'HIGH'
                            ? 'bg-red-50 text-red-800 border border-red-200'
                            : call.unified.verdict === 'MEDIUM'
                            ? 'bg-amber-50 text-amber-800 border border-amber-200'
                            : call.unified.verdict === 'LOW'
                            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                            : 'bg-slate-100 text-slate-700 border border-slate-200'
                        }`}
                      >
                        {call.unified.verdict} THREAT
                      </span>
                    </div>

                    <p className="text-slate-800 text-xs leading-relaxed">{call.unified.explanation}</p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] pt-1">
                      <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 space-y-0.5">
                        <span className="text-slate-500 uppercase font-bold text-[10px] block">Acoustic Telemetry Summary</span>
                        <span className="text-slate-800">
                          {finalSessionSummary
                            ? `${finalSessionSummary.windows_analyzed} sliding windows (${finalSessionSummary.total_duration_seconds}s), Peak P(synth)=${
                                finalSessionSummary.peak_synthetic_probability !== null
                                   ? (finalSessionSummary.peak_synthetic_probability * 100).toFixed(1) + '%'
                                  : 'None'
                              }`
                            : liveAcousticUpdates.length > 0
                            ? `${liveAcousticUpdates.length} sliding windows analyzed`
                            : call.acoustic.syntheticProbability !== null
                            ? `P_synth=${(call.acoustic.syntheticProbability * 100).toFixed(1)}%`
                            : isAcousticUnavailable
                            ? 'Acoustic analysis unavailable — semantic monitoring only'
                            : 'Acoustic not evaluated'}
                        </span>
                      </div>

                      <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 space-y-0.5">
                        <span className="text-slate-500 uppercase font-bold text-[10px] block">Semantic Intent Summary</span>
                        <span className="text-slate-800">
                          {call.semantic.reasons.length > 0
                            ? `${call.semantic.reasons.length} scam indicator${call.semantic.reasons.length === 1 ? '' : 's'} flagged`
                            : 'No suspicious scam patterns detected'}
                        </span>
                      </div>
                    </div>

                    <div className="pt-1 text-[11px] text-indigo-950 font-semibold border-t border-slate-100">
                      Recommendation: {call.unified.recommendedAction}
                    </div>
                    <p className="text-slate-500 text-[10px] italic">
                      {call.unified.disclaimer}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Layer 1: Acoustic Defense Panel */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4 shadow-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-indigo-600" />
                <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-800">
                  Layer 1: Acoustic Defense ({call.acoustic.engineType || (backendDetectionEngine === 'mock' ? 'MOCK ENGINE' : backendDetectionEngine === 'aasist' && isBackendAasistReady ? 'AASIST' : 'ACOUSTIC UNAVAILABLE')})
                </h3>
              </div>
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold ${
                  call.acoustic.status === 'synthetic_detected'
                    ? 'bg-red-50 text-red-800 border border-red-200'
                    : call.acoustic.status === 'likely_genuine'
                    ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                    : isAcousticUnavailable
                    ? 'bg-amber-50 text-amber-800 border border-amber-200'
                    : 'bg-slate-100 text-slate-700 border border-slate-200'
                }`}
              >
                {call.acoustic.label}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                <span className="text-slate-500 uppercase">Detection Engine</span>
                <p className="text-slate-800 font-bold mt-0.5">
                  {call.acoustic.engineType || (backendDetectionEngine === 'mock' ? 'MOCK ENGINE' : backendDetectionEngine === 'aasist' && isBackendAasistReady ? 'AASIST' : 'ACOUSTIC UNAVAILABLE')}
                </p>
              </div>
              <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                <span className="text-slate-500 uppercase">Model Version</span>
                <p className="text-slate-800 font-bold mt-0.5">
                  {call.acoustic.modelVersion || (backendDetectionEngine === 'mock' ? 'mock-v1' : backendDetectionEngine === 'aasist' && isBackendAasistReady ? 'aasist-v1' : 'unavailable')}
                </p>
              </div>
              <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                <span className="text-slate-500 uppercase">Synthetic Probability</span>
                <p
                  className={`font-bold mt-0.5 ${
                    call.acoustic.syntheticProbability !== null && call.acoustic.syntheticProbability >= 0.70
                      ? 'text-red-700'
                      : call.acoustic.syntheticProbability !== null && call.acoustic.syntheticProbability < 0.50
                      ? 'text-emerald-700'
                      : 'text-slate-700'
                  }`}
                >
                  {call.acoustic.syntheticProbability !== null
                    ? `${(call.acoustic.syntheticProbability * 100).toFixed(1)}%`
                    : 'Not evaluated'}
                </p>
              </div>
              <div className="bg-slate-50 p-3 rounded-xl border border-slate-200">
                <span className="text-slate-500 uppercase">Raw Policy Action</span>
                <p className="text-slate-800 font-bold mt-0.5">{call.acoustic.action || 'NOT_EVALUATED'}</p>
              </div>
            </div>

            {/* Real-Time Sliding-Window Acoustic Telemetry Feed */}
            {isStreamingMic && (
              <div className="p-3.5 rounded-xl bg-slate-50 border border-indigo-200 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-indigo-950 font-bold flex items-center gap-1.5">
                    <Waves className="w-3.5 h-3.5 animate-pulse text-indigo-600" />
                    Sliding-Window Monitoring (64,600 samples / window)
                  </span>
                  <span className="text-xs text-slate-500">
                    {liveStreamingState === 'buffering'
                      ? 'Buffering Audio…'
                      : `${liveAcousticUpdates.length} window${liveAcousticUpdates.length === 1 ? '' : 's'} analyzed`}
                  </span>
                </div>

                {liveAcousticUpdates.length > 0 ? (
                  <div className="space-y-1.5 pt-1">
                    <span className="text-[10px] text-slate-500 uppercase font-bold block">
                      Live Window Feed (75% overlap / 16,150-sample hop):
                    </span>
                    <div className="max-h-28 overflow-y-auto space-y-1 text-[11px] font-mono pr-1">
                      {liveAcousticUpdates.slice(-4).reverse().map((w, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between p-1.5 rounded bg-white border border-slate-200 shadow-xs"
                        >
                          <span className="text-slate-700 font-medium">
                            Window #{w.window_index} ({w.start_seconds.toFixed(1)}s - {w.end_seconds.toFixed(1)}s)
                          </span>
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              w.risk_level === 'high'
                                ? 'bg-red-50 text-red-800 border border-red-200'
                                : w.risk_level === 'medium'
                                ? 'bg-amber-50 text-amber-800 border border-amber-200'
                                : 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                            }`}
                          >
                            P={(w.synthetic_probability * 100).toFixed(1)}% &bull; {w.risk_level.toUpperCase()}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-500 font-mono italic">
                    Buffering incoming microphone samples to fulfill initial 64,600-sample window (~4.0s @ 16 kHz)…
                  </p>
                )}
              </div>
            )}

            {/* Offline or Error Telemetry Fallback Alert */}
            {liveError && (
              <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs font-mono text-amber-900 space-y-1">
                <div className="flex items-center gap-1.5 font-bold">
                  <MicOff className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                  <span>Acoustic Monitoring Status</span>
                </div>
                <p className="text-[11px] text-amber-800 leading-relaxed">
                  {liveError}
                </p>
              </div>
            )}

            {/* Audio Clip Attachment */}
            <div className="space-y-2 pt-1 border-t border-slate-100">
              <div className="flex items-center justify-between">
                <label className="text-xs font-mono text-slate-600 flex items-center gap-1.5">
                  <FileAudio className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Attach Audio Clip to Evaluate Acoustic Layer:</span>
                </label>
                {audioFileName && (
                  <span className="text-xs font-mono text-indigo-700 truncate max-w-[180px] font-semibold">
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
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-white border border-slate-300 hover:bg-slate-50 text-xs font-mono text-slate-700 transition-all disabled:opacity-50 cursor-pointer shadow-xs font-medium"
                >
                  <UploadCloud className="w-3.5 h-3.5 text-indigo-600" />
                  {isAnalyzingAudio ? 'Running Acoustic Inference…' : 'Select Audio File to Run Acoustic Check'}
                </button>
              </div>

              <p className="text-[11px] font-mono text-slate-500 leading-tight">
                Backend integration: Calls existing <code>POST /api/v1/detections</code> with 16 kHz multi-window inference. No demo audio files are committed in git; attach any audio file to run live acoustic verification.
              </p>
            </div>
          </div>
        </section>

        {/* Right Column: Layer 2 Semantic Defense & Live Transcript */}
        <section className="space-y-6">
          {/* Layer 2: Semantic Defense Panel */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4 shadow-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-amber-600" />
                <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-800">
                  Layer 2: Semantic Intent Defense
                </h3>
              </div>
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold ${
                  call.semantic.risk === 'high'
                    ? 'bg-red-50 text-red-800 border border-red-200'
                    : call.semantic.risk === 'warning'
                    ? 'bg-amber-50 text-amber-800 border border-amber-200'
                    : call.semantic.risk === 'no_indicators'
                    ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                    : 'bg-slate-100 text-slate-700 border border-slate-200'
                }`}
              >
                Semantic: {call.semantic.risk.toUpperCase()}
              </span>
            </div>

            <div className="text-xs font-mono space-y-2">
              <div className="flex items-center justify-between text-slate-500">
                <span>Expected Pattern:</span>
                <span className="text-slate-800 font-medium text-right">{scenario.expectedPattern}</span>
              </div>
              {call.semantic.reasons.length > 0 ? (
                <div className="space-y-2 pt-1">
                  <span className="text-amber-900 font-bold uppercase text-[11px] flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600" /> Matched Scam Indicators:
                  </span>
                  <ul className="space-y-1.5 bg-amber-50/90 p-3.5 rounded-xl border border-amber-300 text-slate-800 text-xs font-medium">
                    {call.semantic.reasons.map((r, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-600 mt-1.5 shrink-0" />
                        <span className="text-slate-900 font-medium">{r}</span>
                      </li>
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
          <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4 shadow-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-800">
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
                  <div key={index} className="rounded-xl bg-slate-50 border border-slate-200 p-3 space-y-1 shadow-xs">
                    <span className="text-[10px] text-slate-500 uppercase tracking-widest block">
                      Message #{index + 1}
                    </span>
                    <p className="text-slate-800 leading-relaxed break-words">{message}</p>
                  </div>
                ))
              ) : (
                <div className="h-36 flex items-center justify-center text-slate-400 text-xs italic">
                  No conversation messages received yet. Click &ldquo;Simulate Incoming Call&rdquo; to start.
                </div>
              )}
            </div>

            <form
              className="space-y-3 pt-2 border-t border-slate-100"
              onSubmit={(event) => {
                event.preventDefault();
                addMessage(draft);
                setDraft('');
              }}
            >
              <label htmlFor="caller-message" className="block text-xs font-mono text-slate-600">
                Inject Custom Caller Phrase:
              </label>
              <textarea
                id="caller-message"
                className="w-full rounded-xl border border-slate-300 bg-white p-3 text-xs font-mono text-slate-900 focus:outline-none focus:border-indigo-500 shadow-xs"
                maxLength={500}
                rows={2}
                value={draft}
                disabled={call.status !== 'active' || call.messages.length >= 50}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Type a custom phrase, e.g.: 'Send me your verification code immediately.'"
              />
              <button
                type="submit"
                className="w-full rounded-xl px-4 py-2.5 font-bold text-xs uppercase tracking-wider transition-all bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs disabled:bg-slate-100 disabled:text-slate-400 disabled:border disabled:border-slate-200 disabled:cursor-not-allowed cursor-pointer"
                disabled={call.status !== 'active' || !draft.trim() || call.messages.length >= 50}
              >
                Inject Caller Message
              </button>
            </form>
          </div>
        </section>
      </div>

      {/* Session History */}
      <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <h3 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-800">
          Demo Session History
        </h3>
        <p className="text-xs font-mono text-slate-500">
          Last ten simulated calls and scenario automation runs in this session. Maintained in page memory; independent of backend audit records.
        </p>

        {history.length === 0 ? (
          <p className="text-xs font-mono text-slate-500 italic py-2">
            Finish a simulated call session or click &ldquo;Run Scenario&rdquo; to record its dual-layer evaluation here.
          </p>
        ) : (
          <div className="divide-y divide-slate-100 text-xs font-mono">
            {history.map((entry, index) => (
              <div key={index} className="py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <span className="font-bold text-slate-900">{entry.caller}</span>
                  <span className="text-slate-400 mx-2">&bull;</span>
                  <span className="text-slate-600">{entry.outcome}</span>
                  <p className="text-slate-500 text-[11px] mt-0.5">
                    {entry.reasons.join('; ') || 'No semantic flags'} &bull; Acoustic: {entry.acousticLabel}
                  </p>
                </div>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold self-start sm:self-auto ${
                    entry.verdict === 'HIGH'
                      ? 'bg-red-50 text-red-800 border border-red-200'
                      : entry.verdict === 'MEDIUM'
                      ? 'bg-amber-50 text-amber-800 border border-amber-200'
                      : entry.verdict === 'LOW'
                      ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                      : 'bg-slate-100 text-slate-700 border border-slate-200'
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
