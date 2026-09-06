'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  UploadCloud,
  Mic,
  Square,
  FileAudio,
  AlertCircle,
  Cpu,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import { api } from '../lib/api';
import { DetectionResult } from '../lib/types';
import { ThreatBadge } from './ThreatBadge';
import { ConfidenceGauge } from './ConfidenceGauge';
import { formatModelDisplayName } from '@/lib/formatters';

interface DetectionDropzoneProps {
  onDetectionComplete?: (result: DetectionResult) => void;
  redirectToDetail?: boolean;
}

const PIPELINE_STAGES = [
  'Ingesting & Validating Audio Stream',
  'Standardizing 16 kHz Mono & 3.0s Window',
  'Extracting 88-dim MFCC & Spectral Descriptors',
  'Evaluating Classification Probability',
];

export const DetectionDropzone: React.FC<DetectionDropzoneProps> = ({
  onDetectionComplete,
  redirectToDetail = false,
}) => {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [inputSource, setInputSource] = useState<'uploaded_file' | 'browser_microphone'>('uploaded_file');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [pipelineStage, setPipelineStage] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<DetectionResult | null>(null);

  // Live microphone recording states
  const [isRecording, setIsRecording] = useState(false);
  // True between .stop() call and the async onstop event resolving the blob,
  // preventing the UI from flashing back to the idle/empty dropzone state.
  const [isStoppingRecording, setIsStoppingRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const validateAndSetFile = (file: File, source: 'uploaded_file' | 'browser_microphone' = 'uploaded_file') => {
    setErrorMessage(null);
    setResult(null);

    const validExtensions = ['.wav', '.mp3', '.ogg', '.flac', '.m4a', '.aac', '.webm'];
    const fileExt = '.' + file.name.split('.').pop()?.toLowerCase();

    if (!validExtensions.includes(fileExt)) {
      setErrorMessage(`Invalid file type (${fileExt}). Allowed: ${validExtensions.join(', ')}`);
      return;
    }

    if (file.size === 0) {
      setErrorMessage('Recording is empty (0 bytes). Please record for at least 1 second before stopping.');
      return;
    }

    if (file.size > 25 * 1024 * 1024) {
      setErrorMessage('File size exceeds 25 MB limit.');
      return;
    }

    setSelectedFile(file);
    setInputSource(source);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0], 'uploaded_file');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0], 'uploaded_file');
    }
  };

  // Microphone recording
  const startRecording = async () => {
    try {
      setErrorMessage(null);
      setResult(null);
      setSelectedFile(null);
      setInputSource('browser_microphone');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];

      let selectedMimeType = '';
      let chosenExtension = '.webm';

      if (typeof MediaRecorder !== 'undefined' && typeof MediaRecorder.isTypeSupported === 'function') {
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
          selectedMimeType = 'audio/webm;codecs=opus';
          chosenExtension = '.webm';
        } else if (MediaRecorder.isTypeSupported('audio/webm')) {
          selectedMimeType = 'audio/webm';
          chosenExtension = '.webm';
        } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
          selectedMimeType = 'audio/ogg;codecs=opus';
          chosenExtension = '.ogg';
        } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
          selectedMimeType = 'audio/ogg';
          chosenExtension = '.ogg';
        } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
          selectedMimeType = 'audio/mp4';
          chosenExtension = '.m4a';
        } else if (MediaRecorder.isTypeSupported('audio/wav')) {
          selectedMimeType = 'audio/wav';
          chosenExtension = '.wav';
        }
      }

      const options = selectedMimeType ? { mimeType: selectedMimeType } : undefined;
      const mediaRecorder = options ? new MediaRecorder(stream, options) : new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        const actualMime = mediaRecorder.mimeType || selectedMimeType || 'audio/webm';
        let ext = chosenExtension;
        if (actualMime.includes('ogg')) {
          ext = '.ogg';
        } else if (actualMime.includes('webm')) {
          ext = '.webm';
        } else if (actualMime.includes('mp4') || actualMime.includes('aac')) {
          ext = '.m4a';
        } else if (actualMime.includes('wav')) {
          ext = '.wav';
        }

        const audioBlob = new Blob(audioChunksRef.current, { type: actualMime });
        const recordedFile = new File(
          [audioBlob],
          `mic_sample_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}${ext}`,
          { type: actualMime }
        );
        // Clear the stopping flag before handing off to validateAndSetFile,
        // so the UI transitions cleanly to the file-selected state.
        setIsStoppingRecording(false);
        validateAndSetFile(recordedFile, 'browser_microphone');
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(200);
      setIsRecording(true);
      setRecordingSeconds(0);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: unknown) {
      setErrorMessage('Microphone access denied or unavailable: ' + (err instanceof Error ? err.message : 'Error'));
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      // Enter the stopping state immediately so the UI stays in the recording
      // view until the onstop blob is ready, rather than flashing to idle.
      setIsStoppingRecording(true);
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  // Run detection
  const runDetection = async () => {
    if (!selectedFile) return;

    setIsAnalyzing(true);
    setPipelineStage(0);
    setErrorMessage(null);
    setResult(null);

    // Simulated step progression
    const stageInterval = setInterval(() => {
      setPipelineStage((prev) => (prev < PIPELINE_STAGES.length - 1 ? prev + 1 : prev));
    }, 400);

    try {
      const data = await api.uploadAndDetect(selectedFile, inputSource);
      setResult(data);
      if (onDetectionComplete) {
        onDetectionComplete(data);
      }
      if (redirectToDetail) {
        setTimeout(() => {
          router.push(`/detections/${data.id}`);
        }, 1000);
      }
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Detection analysis failed.');
    } finally {
      clearInterval(stageInterval);
      setIsAnalyzing(false);
    }
  };

  const formatSecs = (s: number) => {
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="w-full space-y-6">
      {/* Dropzone Container */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-2xl p-8 transition-all text-center ${
          isDragging
            ? 'border-indigo-500 bg-indigo-50/80 scale-[1.01]'
            : selectedFile
            ? 'border-indigo-200 bg-indigo-50/30'
            : 'border-slate-300 bg-slate-50/60 hover:border-slate-400 hover:bg-slate-50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".wav,.mp3,.ogg,.flac,.m4a,.aac,.webm"
          className="hidden"
          onChange={handleFileChange}
        />

        {isRecording || isStoppingRecording ? (
          <div className="py-6 flex flex-col items-center justify-center space-y-4">
            <div className="relative flex items-center justify-center w-20 h-20 rounded-full bg-red-50 border border-red-200">
              <span className="absolute w-full h-full rounded-full bg-red-100 animate-ping opacity-60" />
              <Mic className="w-8 h-8 text-red-600" />
            </div>
            <div>
              <span className="font-mono text-2xl font-bold text-red-600">
                {isStoppingRecording ? 'Processing…' : formatSecs(recordingSeconds)}
              </span>
              <p className="text-xs font-mono text-slate-500 mt-1">
                {isStoppingRecording ? 'Assembling audio blob…' : 'Recording live audio stream from microphone...'}
              </p>
            </div>
            <button
              onClick={stopRecording}
              disabled={isStoppingRecording}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold uppercase tracking-wider transition-all shadow-xs cursor-pointer"
            >
              <Square className="w-4 h-4" /> Stop Recording
            </button>
          </div>
        ) : selectedFile ? (
          <div className="py-4 flex flex-col items-center justify-center space-y-4">
            <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-50 border border-indigo-200 text-indigo-600">
              <FileAudio className="w-7 h-7" />
            </div>
            <div className="max-w-md text-center">
              <h4 className="text-sm font-semibold text-slate-900 truncate">
                {selectedFile.name}
              </h4>
              <p className="text-xs font-mono text-slate-500 mt-1">
                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • {selectedFile.type || 'audio file'}
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isAnalyzing}
                className="px-3.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-xs font-medium text-slate-700 transition-colors shadow-xs cursor-pointer"
              >
                Choose Different File
              </button>
              <button
                onClick={runDetection}
                disabled={isAnalyzing}
                className="flex items-center gap-2 px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white font-semibold text-xs uppercase tracking-wider transition-all shadow-xs hover:scale-105 active:scale-95 cursor-pointer"
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Analyzing Audio Signal...
                  </>
                ) : (
                  <>
                    <Cpu className="w-4 h-4" /> Run Authenticity Analysis
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="py-8 flex flex-col items-center justify-center space-y-4">
            <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 text-indigo-600 transition-colors">
              <UploadCloud className="w-8 h-8 text-indigo-600" />
            </div>

            <div className="space-y-1">
              <h3 className="text-base font-semibold text-slate-800">
                Drop audio recording here, or browse
              </h3>
              <p className="text-xs text-slate-500">
                Supports <span className="font-mono text-slate-700">WAV, MP3, OGG, FLAC, M4A, AAC, WEBM</span> up to 25 MB
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold uppercase tracking-wider transition-all shadow-xs cursor-pointer"
              >
                Browse Audio File
              </button>
              <button
                onClick={startRecording}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 text-xs font-semibold uppercase tracking-wider transition-all shadow-xs cursor-pointer"
              >
                <Mic className="w-3.5 h-3.5 text-red-600" /> Record Live Microphone
              </button>
            </div>
          </div>
        )}

        {/* Pipeline progress bar */}
        {isAnalyzing && (
          <div className="mt-6 pt-6 border-t border-slate-200 space-y-3">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-indigo-600 flex items-center gap-2 font-semibold">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                {PIPELINE_STAGES[pipelineStage]}
              </span>
              <span className="text-slate-500">
                Step {pipelineStage + 1} of {PIPELINE_STAGES.length}
              </span>
            </div>
            <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-600 transition-all duration-300 rounded-full"
                style={{ width: `${((pipelineStage + 1) / PIPELINE_STAGES.length) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Error display */}
      {errorMessage && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs shadow-xs">
          <AlertCircle className="w-5 h-5 shrink-0 text-red-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Instant Result Summary Card */}
      {result && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-5 animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-100">
            <div>
              <span className="text-[11px] font-mono uppercase tracking-wider text-slate-500">
                Detection Result
              </span>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                <ThreatBadge prediction={result.prediction} size="lg" />
                <ThreatBadge
                  riskLevel={
                    result.prediction === 'unknown' || result.raw_ml_action === 'NOT_EVALUATED' || result.analysis_status === 'inconclusive'
                      ? 'not_assessed'
                      : result.risk_level
                  }
                  size="md"
                />
                {result.action && <ThreatBadge action={result.action} size="md" />}
                {(result.input_source || result.decision?.input_source) && (
                  <ThreatBadge
                    inputSource={result.input_source || result.decision?.input_source || undefined}
                    captureDomainReliability={result.capture_domain_reliability || result.decision?.capture_domain_reliability || undefined}
                    size="md"
                  />
                )}
                {(result.analysis_reliability || result.decision?.analysis_reliability || result.audio_quality?.analysis_reliability) && (
                  <ThreatBadge
                    reliability={result.analysis_reliability || result.decision?.analysis_reliability || result.audio_quality?.analysis_reliability}
                    inputSource={result.input_source || result.decision?.input_source || undefined}
                    captureDomainReliability={result.capture_domain_reliability || result.decision?.capture_domain_reliability || undefined}
                    size="md"
                  />
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => router.push(`/detections/${result.id}`)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs tracking-wider uppercase transition-all shadow-xs cursor-pointer"
              >
                Inspect Case Details <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Security Decision & Prevention Directives */}
          {result.action && (
            <div
              className={`p-4 rounded-xl border ${
                result.action === 'BLOCK'
                  ? 'bg-red-50 border-red-200 text-red-900'
                  : result.action === 'VERIFY'
                  ? 'bg-amber-50 border-amber-200 text-amber-900'
                  : 'bg-emerald-50 border-emerald-200 text-emerald-900'
              } space-y-2`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] font-bold uppercase tracking-wider">
                  Security Directive: {result.action === 'BLOCK' ? 'Block Voice-Only Authorization' : result.action === 'VERIFY' ? 'Step-Up Verification Required' : 'Standard Authorization Permitted'}
                </span>
                <span className="font-mono text-[10px] opacity-70">
                  Policy {result.decision?.policy_version || 'v1.0'}
                </span>
              </div>
              <p className="text-xs leading-relaxed">
                {result.decision_message || result.decision?.decision_message}
              </p>
              {result.decision?.recommended_steps && result.decision.recommended_steps.length > 0 && (
                <ul className="list-disc list-inside text-[11px] opacity-90 space-y-0.5 pt-1">
                  {result.decision.recommended_steps.map((step, idx) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <ConfidenceGauge
              confidence={result.confidence}
              riskLevel={result.risk_level}
              prediction={result.prediction}
              size="lg"
            />

            <div className="space-y-3 font-mono text-xs text-slate-700">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Attack Classification:</span>
                <span className="font-semibold text-slate-800">{result.attack_type || 'Not classified'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Engine / Model Version:</span>
                <span className="text-indigo-600 font-semibold">
                  {formatModelDisplayName(result.model_version, result.engine_type)}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Analysis Latency:</span>
                <span className="text-slate-800 font-semibold">{result.processing_time_ms} ms</span>
              </div>
            </div>
          </div>

          {result.explanation && (
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 leading-relaxed">
              <span className="font-mono text-slate-500 block mb-1 font-semibold uppercase text-[10px]">
                Model Analysis:
              </span>
              {result.explanation}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
