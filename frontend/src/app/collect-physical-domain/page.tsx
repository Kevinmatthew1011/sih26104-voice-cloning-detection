'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  Square,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Radio,
  Layers,
  Volume2,
  Sliders,
  Sparkles,
  ChevronRight,
  ChevronLeft,
  Info,
  ShieldCheck,
} from 'lucide-react';
import { api } from '@/lib/api';
import { PromptItem, BalanceDashboardResponse, IngestionResponse, SplitProposalResponse } from '@/lib/types';

export default function PhysicalDomainCollectionPage() {
  const [activeTab, setActiveTab] = useState<'genuine_capture' | 'synthetic_recapture' | 'balance_dashboard'>('genuine_capture');

  // Metadata Form State
  const [speakerId, setSpeakerId] = useState('HUMAN_SPK_05');
  const [deviceCategory, setDeviceCategory] = useState<'laptop' | 'mobile' | 'external_microphone' | 'other'>('laptop');
  const [deviceName, setDeviceName] = useState('');
  const [roomEnv, setRoomEnv] = useState('quiet_office');
  const [sessionId, setSessionId] = useState('');

  // Synthetic Recapture Specifics
  const [generatorName, setGeneratorName] = useState('ElevenLabs');
  const [generatorVersion, setGeneratorVersion] = useState('v2');
  const [attackId, setAttackId] = useState('zero_shot_clone');
  const [parentSourceId, setParentSourceId] = useState('');
  const [playbackDevice, setPlaybackDevice] = useState('Pixel 8 Smartphone Loudspeaker');

  // Prompts State
  const [prompts, setPrompts] = useState<PromptItem[]>([]);
  const [currentPromptIdx, setCurrentPromptIdx] = useState(0);

  // Recording State
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [audioConstraints, setAudioConstraints] = useState<Record<string, any>>({});
  const [appliedSettings, setAppliedSettings] = useState<Record<string, any>>({});
  const [mimeType, setMimeType] = useState<string>('');
  const [lastUploadedSample, setLastUploadedSample] = useState<IngestionResponse | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);

  // Dashboard State
  const [dashboard, setDashboard] = useState<BalanceDashboardResponse | null>(null);
  const [isLoadingDashboard, setIsLoadingDashboard] = useState(false);
  const [splitProposal, setSplitProposal] = useState<SplitProposalResponse | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Generate default session ID
    setSessionId(`SESS_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}_${Math.floor(100 + Math.random() * 900)}`);

    // Fetch standardized prompt set via API client
    api.getCollectionPrompts()
      .then((data) => {
        if (data && data.prompts) {
          setPrompts(data.prompts);
        }
      })
      .catch((err) => {
        console.error('Failed to load prompts:', err);
      });

    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    setIsLoadingDashboard(true);
    try {
      const data = await api.getCollectionBalanceDashboard();
      setDashboard(data);
    } catch (err: any) {
      console.error('Failed to load dashboard:', err);
    } finally {
      setIsLoadingDashboard(false);
    }
  };

  const handleProposeSplit = async () => {
    try {
      const prop = await api.proposeCollectionSplit();
      setSplitProposal(prop);
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: `Split proposal error: ${err.message}` });
    }
  };

  const startRecording = async () => {
    setStatusMessage(null);
    setAudioConstraints({});
    setAppliedSettings({});
    setMimeType('');
    audioChunksRef.current = [];

    const constraints: MediaStreamConstraints = {
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: 48000,
        channelCount: 1,
      },
    };

    setAudioConstraints(constraints.audio as Record<string, any>);

    try {
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      const audioTrack = stream.getAudioTracks()[0];
      if (audioTrack) {
        const settings = audioTrack.getSettings ? audioTrack.getSettings() : {};
        setAppliedSettings(settings);
        if (audioTrack.label && !deviceName) {
          setDeviceName(audioTrack.label);
        }
      }

      const preferredMimes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/ogg',
        'audio/mp4',
      ];
      let selectedMime = '';
      for (const m of preferredMimes) {
        if (MediaRecorder.isTypeSupported(m)) {
          selectedMime = m;
          break;
        }
      }
      setMimeType(selectedMime);

      const recorder = selectedMime ? new MediaRecorder(stream, { mimeType: selectedMime }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = async () => {
        const actualMime = recorder.mimeType || selectedMime || 'audio/webm';
        const blob = new Blob(audioChunksRef.current, { type: actualMime });
        stream.getTracks().forEach((track) => track.stop());

        if (blob.size < 100) {
          setStatusMessage({ type: 'error', text: 'Recording too short or empty.' });
          return;
        }

        await uploadRecording(blob, actualMime);
      };

      recorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: `Microphone access failed: ${err.message}` });
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const uploadRecording = async (blob: Blob, actualMime: string) => {
    const isSynthetic = activeTab === 'synthetic_recapture';
    const groundTruth = isSynthetic ? 'synthetic' : 'real';
    const ext = actualMime.includes('ogg') ? '.ogg' : actualMime.includes('mp4') ? '.m4a' : '.webm';
    const filename = `${speakerId}_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}${ext}`;

    const formData = new FormData();
    formData.append('file', blob, filename);
    formData.append('ground_truth', groundTruth);
    formData.append('human_identity', isSynthetic ? '' : speakerId);
    formData.append('source_speaker_identity', isSynthetic ? speakerId : '');
    formData.append('source_id', filename);
    formData.append('capture_type', isSynthetic ? 'physical_recapture' : 'physical_browser_microphone');
    formData.append('capture_device_category', deviceCategory);
    formData.append('capture_device_name', deviceName || 'Generic Audio Device');
    formData.append('browser', navigator.userAgent.includes('Chrome') ? 'Google Chrome' : navigator.userAgent.includes('Firefox') ? 'Mozilla Firefox' : 'Other Browser');
    formData.append('browser_version', navigator.userAgent);
    formData.append('os_name', navigator.platform || 'Unknown OS');
    formData.append('requested_constraints_json', JSON.stringify(audioConstraints));
    formData.append('applied_settings_json', JSON.stringify(appliedSettings));
    formData.append('media_recorder_mime_type', actualMime);
    formData.append('room_environment', roomEnv);
    formData.append('capture_session_id', sessionId);
    formData.append('prompt_id', prompts[currentPromptIdx]?.prompt_id || 'FREEFORM');

    if (isSynthetic) {
      formData.append('generator_name', generatorName);
      formData.append('generator_version', generatorVersion);
      formData.append('attack_id', attackId);
      formData.append('playback_device', playbackDevice);
      formData.append('parent_source_id', parentSourceId || 'SYNTH_SOURCE_UNKNOWN');
    }

    try {
      setStatusMessage({ type: 'info', text: 'Uploading and analyzing acoustic audio quality...' });
      const data = await api.ingestPhysicalRecording(formData);
      setLastUploadedSample(data);
      setStatusMessage({ type: 'success', text: `Sample ${data.sample_id} ingested successfully (${data.duration_seconds}s). Quality check passed.` });
      fetchDashboard();
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: `Upload failed: ${err.message}` });
    }
  };

  const formatSecs = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 py-10 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                DEVELOPMENT TOOL
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
                STAGE-2 DATA COLLECTION
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              <Radio className="w-8 h-8 text-emerald-400 animate-pulse" />
              Physical-Domain Acoustic Data Collection
            </h1>
            <p className="text-sm text-slate-400 mt-1 max-w-2xl font-mono">
              Standardized ingestion workflow for genuine microphone speech & channel-matched physical recaptures with complete acoustic provenance.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchDashboard}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs font-mono text-slate-300 transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingDashboard ? 'animate-spin' : ''}`} /> Refresh Stats
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-2 border-b border-slate-800">
          <button
            onClick={() => setActiveTab('genuine_capture')}
            className={`px-4 py-2.5 text-xs font-mono font-semibold rounded-t-xl transition-all flex items-center gap-2 border-t border-x ${
              activeTab === 'genuine_capture'
                ? 'bg-slate-900 border-slate-700 text-emerald-400 border-b-2 border-b-emerald-500'
                : 'bg-transparent border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Mic className="w-4 h-4" /> Genuine Microphone Speech
          </button>
          <button
            onClick={() => setActiveTab('synthetic_recapture')}
            className={`px-4 py-2.5 text-xs font-mono font-semibold rounded-t-xl transition-all flex items-center gap-2 border-t border-x ${
              activeTab === 'synthetic_recapture'
                ? 'bg-slate-900 border-slate-700 text-indigo-400 border-b-2 border-b-indigo-500'
                : 'bg-transparent border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Volume2 className="w-4 h-4" /> Synthetic Acoustic Recapture
          </button>
          <button
            onClick={() => setActiveTab('balance_dashboard')}
            className={`px-4 py-2.5 text-xs font-mono font-semibold rounded-t-xl transition-all flex items-center gap-2 border-t border-x ${
              activeTab === 'balance_dashboard'
                ? 'bg-slate-900 border-slate-700 text-amber-400 border-b-2 border-b-amber-500'
                : 'bg-transparent border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-4 h-4" /> Balance Dashboard & Confound Flags
          </button>
        </div>

        {/* Status Message */}
        {statusMessage && (
          <div
            className={`p-4 rounded-xl border flex items-center gap-3 text-xs font-mono ${
              statusMessage.type === 'success'
                ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
                : statusMessage.type === 'error'
                ? 'bg-red-950/40 border-red-500/30 text-red-300'
                : 'bg-blue-950/40 border-blue-500/30 text-blue-300'
            }`}
          >
            {statusMessage.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : statusMessage.type === 'error' ? (
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            ) : (
              <Info className="w-4 h-4 text-blue-400 shrink-0" />
            )}
            <span>{statusMessage.text}</span>
          </div>
        )}

        {/* Tab 1: Genuine Capture & Tab 2: Synthetic Recapture */}
        {activeTab !== 'balance_dashboard' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column: Metadata Controls */}
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4">
              <h2 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Sliders className="w-4 h-4 text-emerald-400" /> Provenance & Session Metadata
              </h2>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="block text-slate-400 font-mono mb-1">
                    {activeTab === 'genuine_capture' ? 'Human Speaker ID (Pseudonymous)' : 'Source Speaker / Identity'}
                  </label>
                  <input
                    type="text"
                    value={speakerId}
                    onChange={(e) => setSpeakerId(e.target.value)}
                    placeholder="e.g. HUMAN_SPK_05"
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 font-mono focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 font-mono mb-1">Capture Device Category</label>
                  <select
                    value={deviceCategory}
                    onChange={(e) => setDeviceCategory(e.target.value as any)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 font-mono focus:outline-none focus:border-emerald-500"
                  >
                    <option value="laptop">Laptop (Integrated Array)</option>
                    <option value="mobile">Mobile Smartphone (Primary MEMS)</option>
                    <option value="external_microphone">External Condenser / USB Mic</option>
                    <option value="other">Other Audio Transducer</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 font-mono mb-1">Room / Acoustic Environment</label>
                  <select
                    value={roomEnv}
                    onChange={(e) => setRoomEnv(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 font-mono focus:outline-none focus:border-emerald-500"
                  >
                    <option value="quiet_office">Quiet Office (Low Noise)</option>
                    <option value="living_room">Living Room (Moderate Reverberation)</option>
                    <option value="meeting_room">Conference Room (Echoey / Hard Walls)</option>
                    <option value="ambient_cafe">Noisy Room (Background Chatter/HVAC)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 font-mono mb-1">Capture Session ID</label>
                  <input
                    type="text"
                    value={sessionId}
                    onChange={(e) => setSessionId(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 font-mono focus:outline-none focus:border-emerald-500"
                  />
                </div>

                {activeTab === 'synthetic_recapture' && (
                  <div className="pt-3 border-t border-slate-800 space-y-3">
                    <h3 className="text-xs font-mono font-bold text-indigo-400 uppercase">Recapture Playback Settings</h3>
                    <div>
                      <label className="block text-slate-400 font-mono mb-1">Generator Model</label>
                      <input
                        type="text"
                        value={generatorName}
                        onChange={(e) => setGeneratorName(e.target.value)}
                        placeholder="e.g. ElevenLabs, Tacotron"
                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 font-mono mb-1">Playback Loudspeaker Device</label>
                      <input
                        type="text"
                        value={playbackDevice}
                        onChange={(e) => setPlaybackDevice(e.target.value)}
                        placeholder="e.g. Pixel 8 Phone Speaker"
                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 font-mono mb-1">Parent Source Utterance ID</label>
                      <input
                        type="text"
                        value={parentSourceId}
                        onChange={(e) => setParentSourceId(e.target.value)}
                        placeholder="e.g. LA_E_1234567 or synth_clip_01"
                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 font-mono"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Middle & Right Columns: Prompt Display & Recorder */}
            <div className="lg:col-span-2 space-y-6">
              {/* Prompt Carousel */}
              {prompts.length > 0 && (
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 relative overflow-hidden">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        {prompts[currentPromptIdx].prompt_id}
                      </span>
                      <span className="text-xs font-mono text-slate-400">
                        ({currentPromptIdx + 1} of {prompts.length}) &bull; {prompts[currentPromptIdx].category}
                      </span>
                    </div>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setCurrentPromptIdx((prev) => (prev > 0 ? prev - 1 : prompts.length - 1))}
                        className="p-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all"
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setCurrentPromptIdx((prev) => (prev < prompts.length - 1 ? prev + 1 : 0))}
                        className="p-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <div className="py-2">
                    <p className="text-lg font-medium text-slate-100 leading-relaxed font-mono">
                      &ldquo;{prompts[currentPromptIdx].text}&rdquo;
                    </p>
                    <p className="text-xs font-mono text-slate-500 mt-2">
                      Target duration: {prompts[currentPromptIdx].target_duration_range[0]}s &ndash; {prompts[currentPromptIdx].target_duration_range[1]}s &bull; Focus: {prompts[currentPromptIdx].phonetic_focus}
                    </p>
                  </div>
                </div>
              )}

              {/* Live Recorder Box */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 flex flex-col items-center justify-center text-center space-y-6">
                <div className="relative flex items-center justify-center">
                  <div
                    className={`w-24 h-24 rounded-full flex items-center justify-center border transition-all ${
                      isRecording
                        ? 'bg-red-500/20 border-red-500/50 shadow-[0_0_30px_rgba(239,68,68,0.3)] animate-pulse'
                        : 'bg-slate-950 border-slate-700'
                    }`}
                  >
                    <Mic className={`w-10 h-10 ${isRecording ? 'text-red-400' : 'text-slate-400'}`} />
                  </div>
                  {isRecording && (
                    <span className="absolute -top-1 -right-1 flex h-4 w-4">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-4 w-4 bg-red-500"></span>
                    </span>
                  )}
                </div>

                <div>
                  <span className="font-mono text-3xl font-bold text-slate-100">
                    {isRecording ? formatSecs(recordingSeconds) : '00:00'}
                  </span>
                  <p className="text-xs font-mono text-slate-400 mt-1">
                    {isRecording ? 'Recording acoustic stream & hardware telemetry...' : 'Ready to record utterance'}
                  </p>
                </div>

                <div className="flex gap-4">
                  {!isRecording ? (
                    <button
                      onClick={startRecording}
                      className="flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs font-semibold uppercase tracking-wider transition-all shadow-[0_0_20px_rgba(16,185,129,0.3)]"
                    >
                      <Mic className="w-4 h-4" /> Start Recording
                    </button>
                  ) : (
                    <button
                      onClick={stopRecording}
                      className="flex items-center gap-2 px-6 py-3 rounded-xl bg-red-600 hover:bg-red-500 text-white font-mono text-xs font-semibold uppercase tracking-wider transition-all shadow-[0_0_20px_rgba(239,68,68,0.4)]"
                    >
                      <Square className="w-4 h-4" /> Stop & Ingest
                    </button>
                  )}
                </div>

                {/* Telemetry Chips */}
                {appliedSettings.sampleRate && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 w-full pt-4 border-t border-slate-800 text-[11px] font-mono text-slate-400">
                    <div className="bg-slate-950 p-2 rounded-lg border border-slate-800">
                      Rate: <span className="text-emerald-400">{appliedSettings.sampleRate} Hz</span>
                    </div>
                    <div className="bg-slate-950 p-2 rounded-lg border border-slate-800">
                      Codec: <span className="text-emerald-400">{mimeType.split(';')[0] || 'webm'}</span>
                    </div>
                    <div className="bg-slate-950 p-2 rounded-lg border border-slate-800">
                      EchoCancel: <span className="text-emerald-400">{String(appliedSettings.echoCancellation ?? 'true')}</span>
                    </div>
                    <div className="bg-slate-950 p-2 rounded-lg border border-slate-800">
                      NoiseSupp: <span className="text-emerald-400">{String(appliedSettings.noiseSuppression ?? 'true')}</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Last Sample Ingested Card */}
              {lastUploadedSample && (
                <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-2xl p-4 flex items-center justify-between text-xs font-mono">
                  <div className="space-y-1">
                    <span className="text-emerald-400 font-bold">LATEST INGESTED SAMPLE: {lastUploadedSample.sample_id}</span>
                    <p className="text-slate-400">
                      Duration: {lastUploadedSample.duration_seconds}s &bull; Clipping: {lastUploadedSample.quality_telemetry.clipping_percentage}% &bull; SNR: {lastUploadedSample.quality_telemetry.estimated_snr_db} dB
                    </p>
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    POOL STAGED
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 3: Balance Dashboard & Confound Flags */}
        {activeTab === 'balance_dashboard' && dashboard && (
          <div className="space-y-6">
            {/* Top Metrics Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
                <span className="text-xs font-mono text-slate-400 uppercase">Total Pool Samples</span>
                <p className="text-3xl font-bold font-mono text-white mt-1">{dashboard.total_samples}</p>
                <span className="text-xs font-mono text-emerald-400">{dashboard.real_sample_count} Real &bull; {dashboard.synthetic_sample_count} Synth</span>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
                <span className="text-xs font-mono text-slate-400 uppercase">Human Speakers</span>
                <p className={`text-3xl font-bold font-mono mt-1 ${dashboard.human_speaker_count >= 8 ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {dashboard.human_speaker_count} / 8+
                </p>
                <span className="text-xs font-mono text-slate-500">{dashboard.human_speaker_count >= 8 ? 'Target Met' : 'Need more speakers'}</span>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
                <span className="text-xs font-mono text-slate-400 uppercase">Device Categories</span>
                <p className="text-3xl font-bold font-mono text-indigo-400 mt-1">{Object.keys(dashboard.per_device_category).length}</p>
                <span className="text-xs font-mono text-slate-500">Laptops & Mobile</span>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
                <span className="text-xs font-mono text-slate-400 uppercase">Stage-2 Gate Status</span>
                <p className={`text-lg font-bold font-mono mt-2 ${dashboard.ready_for_stage_2_evaluation ? 'text-emerald-400' : 'text-red-400'}`}>
                  {dashboard.ready_for_stage_2_evaluation ? 'READY FOR EVAL' : 'COLLECTION IN PROGRESS'}
                </p>
              </div>
            </div>

            {/* Warning Flags */}
            {(dashboard.imbalance_flags.length > 0 || dashboard.confound_flags.length > 0 || dashboard.leakage_flags.length > 0) && (
              <div className="bg-amber-950/30 border border-amber-500/40 rounded-2xl p-5 space-y-3 text-xs font-mono">
                <h3 className="font-bold text-amber-400 flex items-center gap-2 uppercase tracking-wider">
                  <AlertTriangle className="w-4 h-4 text-amber-400" /> Active Imbalance & Confound Flags
                </h3>
                <ul className="space-y-1.5 list-disc list-inside text-amber-200">
                  {dashboard.imbalance_flags.map((flag, i) => (
                    <li key={`imb_${i}`}>{flag}</li>
                  ))}
                  {dashboard.confound_flags.map((flag, i) => (
                    <li key={`cnf_${i}`}>{flag}</li>
                  ))}
                  {dashboard.leakage_flags.map((flag, i) => (
                    <li key={`lea_${i}`}>{flag}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Detailed Speaker & Device Breakdown Tables */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Speakers Table */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
                <h3 className="text-xs font-mono font-bold text-slate-300 uppercase">Human Speaker Breakdown</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs font-mono text-left">
                    <thead>
                      <tr className="text-slate-500 border-b border-slate-800 pb-2">
                        <th className="pb-2">Speaker ID</th>
                        <th className="pb-2">Samples</th>
                        <th className="pb-2">% of Real</th>
                        <th className="pb-2">Devices</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {Object.entries(dashboard.per_human_speaker).map(([spk, data]: [string, any]) => (
                        <tr key={spk} className="hover:bg-slate-800/30">
                          <td className="py-2.5 font-bold text-slate-200">{spk}</td>
                          <td className="py-2.5 text-emerald-400">{data.genuine_sample_count}</td>
                          <td className="py-2.5 text-slate-400">{data.percentage_of_real_class}%</td>
                          <td className="py-2.5 text-slate-400">{data.device_categories.join(', ')}</td>
                        </tr>
                      ))}
                      {Object.keys(dashboard.per_human_speaker).length === 0 && (
                        <tr>
                          <td colSpan={4} className="py-4 text-center text-slate-500">No human speakers registered yet.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Device Categories Table */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
                <h3 className="text-xs font-mono font-bold text-slate-300 uppercase">Device Category Balance</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs font-mono text-left">
                    <thead>
                      <tr className="text-slate-500 border-b border-slate-800 pb-2">
                        <th className="pb-2">Category</th>
                        <th className="pb-2">Real Count</th>
                        <th className="pb-2">Synthetic Count</th>
                        <th className="pb-2">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {Object.entries(dashboard.per_device_category).map(([dev, counts]: [string, any]) => (
                        <tr key={dev} className="hover:bg-slate-800/30">
                          <td className="py-2.5 font-bold text-slate-200 capitalize">{dev}</td>
                          <td className="py-2.5 text-emerald-400">{counts.real_count}</td>
                          <td className="py-2.5 text-indigo-400">{counts.synthetic_count}</td>
                          <td className="py-2.5 font-bold text-slate-200">{counts.total}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
