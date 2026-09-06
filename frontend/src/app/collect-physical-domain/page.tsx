'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
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
  ChevronRight,
  ChevronLeft,
  Info,
  RotateCcw,
  UploadCloud,
  Download,
  Target,
  Users,
  HardDrive,
  Cpu,
} from 'lucide-react';
import { api } from '@/lib/api';
import {
  PromptItem,
  BalanceDashboardResponse,
  IngestionResponse,
  ExportSplitsResponse,
} from '@/lib/types';

type DeviceCategory = 'laptop' | 'mobile' | 'external_microphone' | 'other';
type DistanceCategory = 'close_10cm' | 'medium_30cm' | 'far_1m';
type PlaybackDeviceCategory =
  | 'smartphone_loudspeaker'
  | 'laptop_speakers'
  | 'bluetooth_speaker'
  | 'desktop_monitors'
  | 'other_transducer';

export default function PhysicalDomainCollectionPage() {
  const [activeTab, setActiveTab] = useState<'genuine_capture' | 'synthetic_recapture' | 'balance_dashboard'>('genuine_capture');

  // Metadata Form State
  const [speakerId, setSpeakerId] = useState('HUMAN_SPK_01');
  const [deviceCategory, setDeviceCategory] = useState<DeviceCategory>('laptop');
  const [deviceName, setDeviceName] = useState('');
  const [distanceCategory, setDistanceCategory] = useState<DistanceCategory>('medium_30cm');
  const [roomEnv, setRoomEnv] = useState('quiet_office');
  const [sessionId, setSessionId] = useState(() => {
    const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    const rand = Math.floor(100 + Math.random() * 900);
    return `SESS_${dateStr}_${rand}`;
  });

  // Synthetic Recapture Specifics
  const [generatorName, setGeneratorName] = useState('ElevenLabs');
  const [generatorVersion, setGeneratorVersion] = useState('v2');
  const [attackId, setAttackId] = useState('zero_shot_clone');
  const [parentSourceId, setParentSourceId] = useState('');
  const [playbackDevice, setPlaybackDevice] = useState('Pixel 8 Smartphone Loudspeaker');
  const [playbackDeviceCategory, setPlaybackDeviceCategory] = useState<PlaybackDeviceCategory>('smartphone_loudspeaker');

  // Prompts State
  const [prompts, setPrompts] = useState<PromptItem[]>([]);
  const [currentPromptIdx, setCurrentPromptIdx] = useState(0);

  // Recording & Preview State
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [audioConstraints, setAudioConstraints] = useState<MediaTrackConstraints>({});
  const [appliedSettings, setAppliedSettings] = useState<MediaTrackSettings>({});
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewMime, setPreviewMime] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Status & Telemetry
  const [lastUploadedSample, setLastUploadedSample] = useState<IngestionResponse | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);

  // Dashboard & Export State
  const [dashboard, setDashboard] = useState<BalanceDashboardResponse | null>(null);
  const [isLoadingDashboard, setIsLoadingDashboard] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportResult, setExportResult] = useState<ExportSplitsResponse | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const fetchDashboard = useCallback(async () => {
    setIsLoadingDashboard(true);
    try {
      const data = await api.getCollectionBalanceDashboard();
      setDashboard(data);
    } catch (err: unknown) {
      console.error('Failed to load dashboard:', err);
    } finally {
      setIsLoadingDashboard(false);
    }
  }, []);

  useEffect(() => {
    let isCancelled = false;

    // Fetch standardized prompt set
    api.getCollectionPrompts()
      .then((data) => {
        if (!isCancelled && data && data.prompts) {
          setPrompts(data.prompts);
        }
      })
      .catch((err: unknown) => {
        console.error('Failed to load prompts:', err);
      });

    // Fetch initial balance dashboard
    api.getCollectionBalanceDashboard()
      .then((data) => {
        if (!isCancelled) {
          setDashboard(data);
        }
      })
      .catch((err: unknown) => {
        console.error('Failed to load dashboard:', err);
      });

    return () => {
      isCancelled = true;
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleRetake = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewBlob(null);
    setPreviewUrl(null);
    setPreviewMime('');
    setStatusMessage(null);
  };

  const startRecording = async () => {
    handleRetake();
    setAudioConstraints({});
    setAppliedSettings({});
    audioChunksRef.current = [];

    const audioConstraintsConfig: MediaTrackConstraints = {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      sampleRate: 48000,
      channelCount: 1,
    };

    setAudioConstraints(audioConstraintsConfig);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraintsConfig });
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

      const recorder = selectedMime ? new MediaRecorder(stream, { mimeType: selectedMime }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        const actualMime = recorder.mimeType || selectedMime || 'audio/webm';
        const blob = new Blob(audioChunksRef.current, { type: actualMime });
        stream.getTracks().forEach((track) => track.stop());

        if (blob.size < 100) {
          setStatusMessage({ type: 'error', text: 'Recording too short or empty. Please re-record.' });
          return;
        }

        const url = URL.createObjectURL(blob);
        setPreviewBlob(blob);
        setPreviewUrl(url);
        setPreviewMime(actualMime);
        setStatusMessage({
          type: 'info',
          text: 'Utterance captured. Listen to verify audio quality before submitting or retaking.',
        });
      };

      recorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setStatusMessage({ type: 'error', text: `Microphone access failed: ${message}` });
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const handleSubmitRecording = async () => {
    if (!previewBlob) return;

    const isSynthetic = activeTab === 'synthetic_recapture';
    const groundTruth = isSynthetic ? 'synthetic' : 'real';

    if (!isSynthetic && !speakerId.trim()) {
      setStatusMessage({ type: 'error', text: 'Human Speaker ID is mandatory for genuine microphone speech.' });
      return;
    }

    if (isSynthetic) {
      if (!playbackDevice.trim()) {
        setStatusMessage({ type: 'error', text: 'Playback device is required for physical replay recordings.' });
        return;
      }
      if (!generatorName.trim()) {
        setStatusMessage({ type: 'error', text: 'Generator model name is required for physical replay recordings.' });
        return;
      }
    }

    const ext = previewMime.includes('ogg') ? '.ogg' : previewMime.includes('mp4') ? '.m4a' : '.webm';
    const filename = `${speakerId || 'UNKNOWN'}_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}${ext}`;

    const formData = new FormData();
    formData.append('file', previewBlob, filename);
    formData.append('ground_truth', groundTruth);
    formData.append('human_identity', isSynthetic ? '' : speakerId.trim());
    formData.append('source_speaker_identity', isSynthetic ? speakerId.trim() : '');
    formData.append('source_id', filename);
    formData.append('capture_type', isSynthetic ? 'physical_recapture' : 'physical_browser_microphone');
    formData.append('capture_device_category', deviceCategory);
    formData.append('capture_device_name', deviceName || 'Standard Microphone Array');
    formData.append('distance_category', distanceCategory);
    formData.append('browser', navigator.userAgent.includes('Chrome') ? 'Google Chrome' : navigator.userAgent.includes('Firefox') ? 'Mozilla Firefox' : 'Other Browser');
    formData.append('browser_version', navigator.userAgent);
    formData.append('os_name', navigator.platform || 'Linux');
    formData.append('requested_constraints_json', JSON.stringify(audioConstraints));
    formData.append('applied_settings_json', JSON.stringify(appliedSettings));
    formData.append('media_recorder_mime_type', previewMime);
    formData.append('room_environment', roomEnv);
    formData.append('capture_session_id', sessionId);
    formData.append('prompt_id', prompts[currentPromptIdx]?.prompt_id || 'FREEFORM');

    if (isSynthetic) {
      formData.append('generator_name', generatorName.trim());
      formData.append('generator_version', generatorVersion.trim());
      formData.append('attack_id', attackId.trim());
      formData.append('playback_device', playbackDevice.trim());
      formData.append('playback_device_category', playbackDeviceCategory);
      formData.append('parent_source_id', parentSourceId.trim() || 'SYNTH_PARENT_MANUAL');
    }

    setIsSubmitting(true);
    try {
      setStatusMessage({ type: 'info', text: 'Analyzing audio quality & staging into pool...' });
      const data = await api.ingestPhysicalRecording(formData);
      setLastUploadedSample(data);
      setStatusMessage({
        type: 'success',
        text: `Sample ${data.sample_id} successfully staged (${data.duration_seconds}s). Advance to next prompt.`,
      });

      // Advance prompt automatically
      if (prompts.length > 0) {
        setCurrentPromptIdx((prev) => (prev + 1) % prompts.length);
      }

      // Clear preview
      handleRetake();
      fetchDashboard();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setStatusMessage({ type: 'error', text: `Upload rejected: ${message}` });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleExportSplits = async () => {
    setIsExporting(true);
    setExportResult(null);
    try {
      const result = await api.exportCollectionSplits();
      setExportResult(result);
      setStatusMessage({
        type: 'success',
        text: `Exported ${result.total_exported} samples to ${result.export_directory} with strict speaker disjointness.`,
      });
      fetchDashboard();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setStatusMessage({ type: 'error', text: `Split export failed: ${message}` });
    } finally {
      setIsExporting(false);
    }
  };

  const formatSecs = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 py-10 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                DEVELOPMENT TOOL
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
                PHASE 5 DATASET READINESS
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 flex items-center gap-3">
              <Radio className="w-8 h-8 text-emerald-600 animate-pulse" />
              Physical-Domain Acoustic Data Collection
            </h1>
            <p className="text-sm text-slate-600 mt-1 max-w-2xl font-mono">
              Target: N=300 balanced acoustic samples (150 Genuine + 150 Physical Replay across &ge;15 speakers) with strict provenance and speaker disjointness.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchDashboard}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-xs font-mono text-slate-700 shadow-xs transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingDashboard ? 'animate-spin' : ''}`} /> Refresh Stats
            </button>
          </div>
        </div>

        {/* Target Progress Bar Cards */}
        {dashboard && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white border border-slate-200 rounded-2xl p-4 space-y-2 shadow-xs">
              <div className="flex justify-between items-center text-xs font-mono text-slate-600">
                <span className="flex items-center gap-1.5"><Target className="w-3.5 h-3.5 text-emerald-600" /> Total Samples</span>
                <span className="text-slate-900 font-bold">{dashboard.total_samples} / {dashboard.target_total || 300}</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
                <div
                  className="bg-emerald-600 h-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.round((dashboard.total_samples / (dashboard.target_total || 300)) * 100))}%` }}
                />
              </div>
              <p className="text-[11px] font-mono text-slate-500">{Math.round((dashboard.total_samples / (dashboard.target_total || 300)) * 100)}% of collection target</p>
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl p-4 space-y-2 shadow-xs">
              <div className="flex justify-between items-center text-xs font-mono text-slate-600">
                <span className="flex items-center gap-1.5"><Mic className="w-3.5 h-3.5 text-emerald-600" /> Genuine Mic</span>
                <span className="text-emerald-700 font-bold">{dashboard.real_sample_count} / {dashboard.target_genuine || 150}</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
                <div
                  className="bg-emerald-600 h-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.round((dashboard.real_sample_count / (dashboard.target_genuine || 150)) * 100))}%` }}
                />
              </div>
              <p className="text-[11px] font-mono text-slate-500">{Math.round((dashboard.real_sample_count / (dashboard.target_genuine || 150)) * 100)}% of genuine target</p>
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl p-4 space-y-2 shadow-xs">
              <div className="flex justify-between items-center text-xs font-mono text-slate-600">
                <span className="flex items-center gap-1.5"><Volume2 className="w-3.5 h-3.5 text-indigo-600" /> Physical Replay</span>
                <span className="text-indigo-700 font-bold">{dashboard.physical_replay_count || 0} / {dashboard.target_replay || 150}</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
                <div
                  className="bg-indigo-600 h-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.round(((dashboard.physical_replay_count || 0) / (dashboard.target_replay || 150)) * 100))}%` }}
                />
              </div>
              <p className="text-[11px] font-mono text-slate-500">{Math.round(((dashboard.physical_replay_count || 0) / (dashboard.target_replay || 150)) * 100)}% of replay target</p>
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl p-4 space-y-2 shadow-xs">
              <div className="flex justify-between items-center text-xs font-mono text-slate-600">
                <span className="flex items-center gap-1.5"><Users className="w-3.5 h-3.5 text-amber-600" /> Human Speakers</span>
                <span className="text-amber-700 font-bold">{dashboard.human_speaker_count} / {dashboard.target_speakers || 15}</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200">
                <div
                  className="bg-amber-500 h-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.round((dashboard.human_speaker_count / (dashboard.target_speakers || 15)) * 100))}%` }}
                />
              </div>
              <p className="text-[11px] font-mono text-slate-500">{Math.round((dashboard.human_speaker_count / (dashboard.target_speakers || 15)) * 100)}% of speaker quota</p>
            </div>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex gap-2 border-b border-slate-200">
          <button
            onClick={() => {
              setActiveTab('genuine_capture');
              handleRetake();
            }}
            className={`px-4 py-2.5 text-xs font-mono font-semibold rounded-t-xl transition-all flex items-center gap-2 border-t border-x ${
              activeTab === 'genuine_capture'
                ? 'bg-white border-slate-200 text-emerald-700 border-b-2 border-b-emerald-600 shadow-xs'
                : 'bg-transparent border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Mic className="w-4 h-4" /> Mode A: Genuine Microphone Speech
          </button>
          <button
            onClick={() => {
              setActiveTab('synthetic_recapture');
              handleRetake();
            }}
            className={`px-4 py-2.5 text-xs font-mono font-semibold rounded-t-xl transition-all flex items-center gap-2 border-t border-x ${
              activeTab === 'synthetic_recapture'
                ? 'bg-white border-slate-200 text-indigo-700 border-b-2 border-b-indigo-600 shadow-xs'
                : 'bg-transparent border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Volume2 className="w-4 h-4" /> Mode B: Synthetic Acoustic Replay
          </button>
          <button
            onClick={() => {
              setActiveTab('balance_dashboard');
              handleRetake();
            }}
            className={`px-4 py-2.5 text-xs font-mono font-semibold rounded-t-xl transition-all flex items-center gap-2 border-t border-x ${
              activeTab === 'balance_dashboard'
                ? 'bg-white border-slate-200 text-amber-700 border-b-2 border-b-amber-600 shadow-xs'
                : 'bg-transparent border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Layers className="w-4 h-4" /> Balance Dashboard & Export Splits
          </button>
        </div>

        {/* Status Message */}
        {statusMessage && (
          <div
            className={`p-4 rounded-xl border flex items-center gap-3 text-xs font-mono ${
              statusMessage.type === 'success'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : statusMessage.type === 'error'
                ? 'bg-rose-50 border-rose-200 text-rose-800'
                : 'bg-indigo-50 border-indigo-200 text-indigo-800'
            }`}
          >
            {statusMessage.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : statusMessage.type === 'error' ? (
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            ) : (
              <Info className="w-4 h-4 text-indigo-600 shrink-0" />
            )}
            <span>{statusMessage.text}</span>
          </div>
        )}

        {/* Mode A (Genuine) & Mode B (Synthetic Replay) Ingestion View */}
        {activeTab !== 'balance_dashboard' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column: Metadata Controls */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4 shadow-xs">
              <h2 className="text-xs font-mono font-bold text-slate-800 uppercase tracking-wider flex items-center gap-2">
                <Sliders className="w-4 h-4 text-emerald-600" /> Acoustic Provenance
              </h2>

              <div className="space-y-3 text-xs">
                {activeTab === 'genuine_capture' ? (
                  <div>
                    <label className="block text-slate-700 font-mono mb-1">
                      Human Speaker ID <span className="text-emerald-600">*</span>
                    </label>
                    <input
                      type="text"
                      value={speakerId}
                      onChange={(e) => setSpeakerId(e.target.value)}
                      placeholder="e.g. HUMAN_SPK_01"
                      className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-emerald-600 focus:bg-white"
                    />
                    <p className="text-[10px] font-mono text-slate-500 mt-1">Pseudonymous identifier (&ge;15 unique speakers required).</p>
                  </div>
                ) : (
                  <div>
                    <label className="block text-slate-700 font-mono mb-1">Source Cloned Speaker / Voice</label>
                    <input
                      type="text"
                      value={speakerId}
                      onChange={(e) => setSpeakerId(e.target.value)}
                      placeholder="e.g. CLONED_TARGET_01"
                      className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-indigo-600 focus:bg-white"
                    />
                  </div>
                )}

                <div>
                  <label className="block text-slate-700 font-mono mb-1">Microphone Device Category</label>
                  <select
                    value={deviceCategory}
                    onChange={(e) => setDeviceCategory(e.target.value as DeviceCategory)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-emerald-600 focus:bg-white"
                  >
                    <option value="laptop">Laptop Integrated Array</option>
                    <option value="mobile">Smartphone Primary MEMS</option>
                    <option value="external_microphone">External USB / Condenser</option>
                    <option value="other">Other Microphone</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-700 font-mono mb-1">Microphone Hardware Name</label>
                  <input
                    type="text"
                    value={deviceName}
                    onChange={(e) => setDeviceName(e.target.value)}
                    placeholder="Auto-detected from browser"
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono text-[11px] focus:outline-none focus:border-emerald-600 focus:bg-white"
                  />
                </div>

                <div>
                  <label className="block text-slate-700 font-mono mb-1">Recording Distance</label>
                  <select
                    value={distanceCategory}
                    onChange={(e) => setDistanceCategory(e.target.value as DistanceCategory)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-emerald-600 focus:bg-white"
                  >
                    <option value="close_10cm">Close (~10 cm, mouth proximity)</option>
                    <option value="medium_30cm">Medium (~30 cm, desk / handheld)</option>
                    <option value="far_1m">Far-field (~1 meter)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-700 font-mono mb-1">Room Environment</label>
                  <select
                    value={roomEnv}
                    onChange={(e) => setRoomEnv(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-emerald-600 focus:bg-white"
                  >
                    <option value="quiet_office">Quiet Office (Low Noise)</option>
                    <option value="living_room">Living Room (Moderate Reverberation)</option>
                    <option value="meeting_room">Conference Room (Echoey / Hard Surfaces)</option>
                    <option value="ambient_cafe">Noisy Room (HVAC / Ambient Chatter)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-700 font-mono mb-1">Capture Session ID</label>
                  <input
                    type="text"
                    value={sessionId}
                    onChange={(e) => setSessionId(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-emerald-600 focus:bg-white"
                  />
                </div>

                {/* Synthetic Replay Controls (Mode B) */}
                {activeTab === 'synthetic_recapture' && (
                  <div className="pt-3 border-t border-slate-200 space-y-3">
                    <h3 className="text-xs font-mono font-bold text-indigo-700 uppercase flex items-center gap-1.5">
                      <Volume2 className="w-3.5 h-3.5" /> Replay Transducer & Generator
                    </h3>

                    <div>
                      <label className="block text-slate-700 font-mono mb-1">
                        Playback Loudspeaker <span className="text-indigo-600">*</span>
                      </label>
                      <input
                        type="text"
                        value={playbackDevice}
                        onChange={(e) => setPlaybackDevice(e.target.value)}
                        placeholder="e.g. Pixel 8 Phone Speaker, JBL Flip"
                        className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-indigo-600 focus:bg-white"
                      />
                      <p className="text-[10px] font-mono text-slate-500 mt-1">Loudspeaker transducer that physically emits the synthetic audio.</p>
                    </div>

                    <div>
                      <label className="block text-slate-700 font-mono mb-1">Playback Transducer Category</label>
                      <select
                        value={playbackDeviceCategory}
                        onChange={(e) => setPlaybackDeviceCategory(e.target.value as PlaybackDeviceCategory)}
                        className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-indigo-600 focus:bg-white"
                      >
                        <option value="smartphone_loudspeaker">Smartphone Loudspeaker (MEMS / Micro-driver)</option>
                        <option value="laptop_speakers">Laptop Internal Speakers</option>
                        <option value="bluetooth_speaker">Portable Bluetooth Speaker</option>
                        <option value="desktop_monitors">Desktop Studio Monitors / PC Speakers</option>
                        <option value="other_transducer">Other Transducer</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-slate-700 font-mono mb-1">
                        Generator Model <span className="text-indigo-600">*</span>
                      </label>
                      <input
                        type="text"
                        value={generatorName}
                        onChange={(e) => setGeneratorName(e.target.value)}
                        placeholder="e.g. ElevenLabs, Tacotron, Bark"
                        className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-indigo-600 focus:bg-white"
                      />
                    </div>

                    <div>
                      <label className="block text-slate-700 font-mono mb-1">Generator Version</label>
                      <input
                        type="text"
                        value={generatorVersion}
                        onChange={(e) => setGeneratorVersion(e.target.value)}
                        placeholder="e.g. v2, turbo"
                        className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-indigo-600 focus:bg-white"
                      />
                    </div>

                    <div>
                      <label className="block text-slate-700 font-mono mb-1">Attack Algorithm ID</label>
                      <input
                        type="text"
                        value={attackId}
                        onChange={(e) => setAttackId(e.target.value)}
                        placeholder="e.g. zero_shot_clone, vc_sv"
                        className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-indigo-600 focus:bg-white"
                      />
                    </div>

                    <div>
                      <label className="block text-slate-700 font-mono mb-1">Parent Source Utterance ID</label>
                      <input
                        type="text"
                        value={parentSourceId}
                        onChange={(e) => setParentSourceId(e.target.value)}
                        placeholder="e.g. LA_E_1234567 or synth_clip_01"
                        className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-slate-900 font-mono focus:outline-none focus:border-indigo-600 focus:bg-white"
                      />
                      <p className="text-[10px] font-mono text-slate-500 mt-1">Used to guarantee parent source disjointness across splits.</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Middle & Right Columns: Prompt Display & Recorder */}
            <div className="lg:col-span-2 space-y-6">
              {/* Prompt Carousel */}
              {prompts.length > 0 && (
                <div className="bg-white border border-slate-200 rounded-2xl p-6 relative overflow-hidden shadow-xs">
                  <div className="flex items-center justify-between border-b border-slate-200 pb-3 mb-4">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-amber-50 text-amber-700 border border-amber-200">
                        {prompts[currentPromptIdx].prompt_id}
                      </span>
                      <span className="text-xs font-mono text-slate-500">
                        ({currentPromptIdx + 1} of {prompts.length}) &bull; {prompts[currentPromptIdx].category}
                      </span>
                    </div>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setCurrentPromptIdx((prev) => (prev > 0 ? prev - 1 : prompts.length - 1))}
                        className="p-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition-all"
                        title="Previous prompt"
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setCurrentPromptIdx((prev) => (prev < prompts.length - 1 ? prev + 1 : 0))}
                        className="p-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition-all"
                        title="Next prompt"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <div className="py-2">
                    <p className="text-lg font-medium text-slate-900 leading-relaxed font-mono">
                      &ldquo;{prompts[currentPromptIdx].text}&rdquo;
                    </p>
                    <p className="text-xs font-mono text-slate-500 mt-2">
                      Target duration: {prompts[currentPromptIdx].target_duration_range[0]}s &ndash; {prompts[currentPromptIdx].target_duration_range[1]}s &bull; Focus: {prompts[currentPromptIdx].phonetic_focus}
                    </p>
                  </div>
                </div>
              )}

              {/* Live Recorder Box */}
              <div className="bg-white border border-slate-200 rounded-2xl p-6 flex flex-col items-center justify-center text-center space-y-6 shadow-xs">
                <div className="relative flex items-center justify-center">
                  <div
                    className={`w-24 h-24 rounded-full flex items-center justify-center border transition-all ${
                      isRecording
                        ? 'bg-rose-50 border-rose-300 shadow-[0_0_25px_rgba(244,63,94,0.2)] animate-pulse'
                        : previewBlob
                        ? 'bg-emerald-50 border-emerald-300'
                        : 'bg-slate-100 border-slate-200'
                    }`}
                  >
                    {isRecording ? (
                      <Mic className="w-10 h-10 text-rose-600" />
                    ) : previewBlob ? (
                      <CheckCircle2 className="w-10 h-10 text-emerald-600" />
                    ) : (
                      <Mic className="w-10 h-10 text-slate-400" />
                    )}
                  </div>
                  {isRecording && (
                    <span className="absolute -top-1 -right-1 flex h-4 w-4">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-4 w-4 bg-rose-600"></span>
                    </span>
                  )}
                </div>

                <div>
                  <span className="font-mono text-3xl font-bold text-slate-900">
                    {isRecording ? formatSecs(recordingSeconds) : previewBlob ? 'Captured' : '00:00'}
                  </span>
                  <p className="text-xs font-mono text-slate-600 mt-1">
                    {isRecording
                      ? 'Recording acoustic stream & hardware telemetry...'
                      : previewBlob
                      ? 'Utterance captured. Review playback before submitting.'
                      : activeTab === 'genuine_capture'
                      ? 'Speak the prompt text into your physical microphone'
                      : 'Play synthetic audio through loudspeaker toward microphone'}
                  </p>
                </div>

                {/* Preview Audio Controls (when captured) */}
                {previewUrl && (
                  <div className="w-full max-w-md bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
                    <span className="text-xs font-mono text-slate-600 uppercase tracking-wider block text-left font-medium">
                      Playback Preview:
                    </span>
                    <audio controls src={previewUrl} className="w-full rounded-lg" />
                  </div>
                )}

                {/* Primary Action Buttons */}
                <div className="flex flex-wrap gap-4 justify-center">
                  {!isRecording && !previewBlob && (
                    <button
                      onClick={startRecording}
                      className="flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-mono text-xs font-semibold uppercase tracking-wider transition-all shadow-xs"
                    >
                      <Mic className="w-4 h-4" /> Start Recording
                    </button>
                  )}

                  {isRecording && (
                    <button
                      onClick={stopRecording}
                      className="flex items-center gap-2 px-6 py-3 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-mono text-xs font-semibold uppercase tracking-wider transition-all shadow-xs"
                    >
                      <Square className="w-4 h-4" /> Stop Recording
                    </button>
                  )}

                  {previewBlob && (
                    <>
                      <button
                        onClick={handleRetake}
                        disabled={isSubmitting}
                        className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-300 text-slate-700 font-mono text-xs font-semibold uppercase tracking-wider transition-all shadow-xs"
                      >
                        <RotateCcw className="w-4 h-4" /> Retake
                      </button>
                      <button
                        onClick={handleSubmitRecording}
                        disabled={isSubmitting}
                        className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-mono text-xs font-semibold uppercase tracking-wider transition-all shadow-xs"
                      >
                        <UploadCloud className={`w-4 h-4 ${isSubmitting ? 'animate-bounce' : ''}`} />
                        {isSubmitting ? 'Submitting...' : 'Submit Recording'}
                      </button>
                    </>
                  )}
                </div>

                {/* Telemetry Chips */}
                {appliedSettings.sampleRate && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 w-full pt-4 border-t border-slate-200 text-[11px] font-mono text-slate-600">
                    <div className="bg-slate-50 p-2 rounded-lg border border-slate-200">
                      Rate: <span className="text-emerald-700 font-semibold">{appliedSettings.sampleRate} Hz</span>
                    </div>
                    <div className="bg-slate-50 p-2 rounded-lg border border-slate-200">
                      Distance: <span className="text-emerald-700 font-semibold">{distanceCategory.replace('_', ' ')}</span>
                    </div>
                    <div className="bg-slate-50 p-2 rounded-lg border border-slate-200">
                      EchoCancel: <span className="text-emerald-700 font-semibold">{String(appliedSettings.echoCancellation ?? 'true')}</span>
                    </div>
                    <div className="bg-slate-50 p-2 rounded-lg border border-slate-200">
                      NoiseSupp: <span className="text-emerald-700 font-semibold">{String(appliedSettings.noiseSuppression ?? 'true')}</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Last Sample Ingested Card */}
              {lastUploadedSample && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4 flex items-center justify-between text-xs font-mono shadow-xs">
                  <div className="space-y-1">
                    <span className="text-emerald-800 font-bold">LATEST INGESTED SAMPLE: {lastUploadedSample.sample_id}</span>
                    <p className="text-slate-600">
                      Duration: {lastUploadedSample.duration_seconds}s &bull; Clipping: {lastUploadedSample.quality_telemetry.clipping_percentage}% &bull; SNR: {lastUploadedSample.quality_telemetry.estimated_snr_db} dB &bull; Silence: {lastUploadedSample.quality_telemetry.silence_percentage}%
                    </p>
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-xs font-mono font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
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
              <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-1 shadow-xs">
                <span className="text-xs font-mono text-slate-500 uppercase flex items-center gap-1.5">
                  <HardDrive className="w-3.5 h-3.5 text-indigo-600" /> Staged Total
                </span>
                <p className="text-3xl font-bold font-mono text-slate-900">{dashboard.total_samples} / {dashboard.target_total || 300}</p>
                <span className="text-xs font-mono text-emerald-700 font-medium">{dashboard.real_sample_count} Real &bull; {dashboard.synthetic_sample_count} Synth</span>
              </div>

              <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-1 shadow-xs">
                <span className="text-xs font-mono text-slate-500 uppercase flex items-center gap-1.5">
                  <Users className="w-3.5 h-3.5 text-amber-600" /> Human Speakers
                </span>
                <p className={`text-3xl font-bold font-mono ${dashboard.human_speaker_count >= (dashboard.target_speakers || 15) ? 'text-emerald-700' : 'text-amber-700'}`}>
                  {dashboard.human_speaker_count} / {dashboard.target_speakers || 15}
                </p>
                <span className="text-xs font-mono text-slate-500">
                  {dashboard.human_speaker_count >= (dashboard.target_speakers || 15) ? 'Target Met' : 'Need more speakers'}
                </span>
              </div>

              <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-1 shadow-xs">
                <span className="text-xs font-mono text-slate-500 uppercase flex items-center gap-1.5">
                  <Volume2 className="w-3.5 h-3.5 text-indigo-600" /> Physical Replay
                </span>
                <p className={`text-3xl font-bold font-mono ${(dashboard.physical_replay_count || 0) >= (dashboard.target_replay || 150) ? 'text-emerald-700' : 'text-indigo-700'}`}>
                  {dashboard.physical_replay_count || 0} / {dashboard.target_replay || 150}
                </p>
                <span className="text-xs font-mono text-slate-500">Transducer verified</span>
              </div>

              <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-1 shadow-xs">
                <span className="text-xs font-mono text-slate-500 uppercase flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-emerald-600" /> Readiness Gate
                </span>
                <p className={`text-base font-bold font-mono mt-1 ${dashboard.ready_for_stage_2_evaluation ? 'text-emerald-700' : 'text-amber-700'}`}>
                  {dashboard.ready_for_stage_2_evaluation ? 'READY FOR EVAL' : 'COLLECTION ACTIVE'}
                </p>
                <span className="text-xs font-mono text-slate-500">
                  {dashboard.ready_for_stage_2_evaluation ? 'Target quotas met' : 'Quotas in progress'}
                </span>
              </div>
            </div>

            {/* Statistical Sufficiency Note Banner */}
            {dashboard.statistical_sufficiency_note && (
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 text-xs font-mono text-amber-900 leading-relaxed flex items-start gap-3 shadow-xs">
                <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-bold text-amber-800 uppercase mb-1">Collection Scope & Statistical Sufficiency Note</h4>
                  <p>{dashboard.statistical_sufficiency_note}</p>
                </div>
              </div>
            )}

            {/* Confound & Imbalance Flags */}
            {(dashboard.imbalance_flags.length > 0 || dashboard.confound_flags.length > 0 || dashboard.leakage_flags.length > 0) && (
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 space-y-3 text-xs font-mono shadow-xs">
                <h3 className="font-bold text-amber-800 flex items-center gap-2 uppercase tracking-wider">
                  <AlertTriangle className="w-4 h-4 text-amber-600" /> Imbalance & Acoustic Confound Flags
                </h3>
                <ul className="space-y-1.5 list-disc list-inside text-amber-900">
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

            {/* Split Export Section */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-4 shadow-xs">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h3 className="text-xs font-mono font-bold text-slate-900 uppercase flex items-center gap-2">
                    <Download className="w-4 h-4 text-emerald-600" /> Export Partitioned Dataset Splits
                  </h3>
                  <p className="text-xs font-mono text-slate-600 mt-1">
                    Generates train, validation, and test partitions with strict human speaker disjointness into <code>ml_data/physical_domain</code>.
                  </p>
                </div>
                <button
                  onClick={handleExportSplits}
                  disabled={isExporting || dashboard.total_samples === 0}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-mono text-xs font-semibold uppercase tracking-wider transition-all shrink-0 shadow-xs"
                >
                  <Download className={`w-4 h-4 ${isExporting ? 'animate-bounce' : ''}`} />
                  {isExporting ? 'Exporting...' : 'Export Partitioned Splits'}
                </button>
              </div>

              {exportResult && (
                <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl space-y-2 text-xs font-mono">
                  <div className="flex items-center gap-2 text-emerald-800 font-bold">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Splits Successfully Exported ({exportResult.total_exported} total samples)</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1 text-slate-700">
                    <div className="bg-white p-2.5 rounded-lg border border-emerald-200">
                      Train: <span className="text-emerald-700 font-bold">{exportResult.train_count}</span> samples
                    </div>
                    <div className="bg-white p-2.5 rounded-lg border border-emerald-200">
                      Validation: <span className="text-indigo-700 font-bold">{exportResult.validation_count}</span> samples
                    </div>
                    <div className="bg-white p-2.5 rounded-lg border border-emerald-200">
                      Test: <span className="text-amber-700 font-bold">{exportResult.test_count}</span> samples
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-600 pt-1">
                    Speaker Disjointness: <span className="text-emerald-700 font-bold">{exportResult.human_speakers_disjoint ? 'VERIFIED (0% overlap)' : 'FAILED'}</span> &bull; Directory: <code>{exportResult.export_directory}</code>
                  </p>
                </div>
              )}
            </div>

            {/* Detailed Speaker & Device Breakdown Tables */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Speakers Table */}
              <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-3 shadow-xs">
                <h3 className="text-xs font-mono font-bold text-slate-900 uppercase">Human Speaker Distribution</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs font-mono text-left">
                    <thead>
                      <tr className="text-slate-500 border-b border-slate-200 pb-2">
                        <th className="pb-2">Speaker ID</th>
                        <th className="pb-2">Samples</th>
                        <th className="pb-2">% of Real</th>
                        <th className="pb-2">Devices</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {Object.entries(dashboard.per_human_speaker).map(([spk, data]) => (
                        <tr key={spk} className="hover:bg-slate-50">
                          <td className="py-2.5 font-bold text-slate-900">{spk}</td>
                          <td className="py-2.5 text-emerald-700 font-semibold">{data.genuine_sample_count}</td>
                          <td className="py-2.5 text-slate-600">{data.percentage_of_real_class}%</td>
                          <td className="py-2.5 text-slate-600">{data.device_categories.join(', ')}</td>
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
              <div className="bg-white border border-slate-200 rounded-2xl p-5 space-y-3 shadow-xs">
                <h3 className="text-xs font-mono font-bold text-slate-900 uppercase">Device Category Balance</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs font-mono text-left">
                    <thead>
                      <tr className="text-slate-500 border-b border-slate-200 pb-2">
                        <th className="pb-2">Category</th>
                        <th className="pb-2">Real</th>
                        <th className="pb-2">Synthetic</th>
                        <th className="pb-2">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {Object.entries(dashboard.per_device_category).map(([dev, counts]) => (
                        <tr key={dev} className="hover:bg-slate-50">
                          <td className="py-2.5 font-bold text-slate-900 capitalize">{dev}</td>
                          <td className="py-2.5 text-emerald-700 font-semibold">{counts.real_count}</td>
                          <td className="py-2.5 text-indigo-700 font-semibold">{counts.synthetic_count}</td>
                          <td className="py-2.5 font-bold text-slate-900">{counts.total}</td>
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
