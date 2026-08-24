'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  UploadCloud,
  Mic,
  Square,
  FileAudio,
  AlertCircle,
  CheckCircle2,
  Cpu,
  ArrowRight,
  ShieldAlert,
  Loader2,
} from 'lucide-react';
import { api } from '../lib/api';
import { DetectionResult } from '../lib/types';
import { ThreatBadge } from './ThreatBadge';
import { ConfidenceGauge } from './ConfidenceGauge';

interface DetectionDropzoneProps {
  onDetectionComplete?: (result: DetectionResult) => void;
  redirectToDetail?: boolean;
}

const PIPELINE_STAGES = [
  'Ingesting & Validating Audio Stream',
  'Extracting Acoustic Formants & Phase Dynamics',
  'Neural Vocoder & Diffusion Artifact Classification',
  'Synthesizing Forensic Security Verdict',
];

export const DetectionDropzone: React.FC<DetectionDropzoneProps> = ({
  onDetectionComplete,
  redirectToDetail = false,
}) => {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [pipelineStage, setPipelineStage] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [result, setResult] = useState<DetectionResult | null>(null);

  // Live microphone recording states
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const validateAndSetFile = (file: File) => {
    setErrorMessage(null);
    setResult(null);

    const validExtensions = ['.wav', '.mp3', '.ogg', '.flac', '.m4a', '.aac', '.webm'];
    const fileExt = '.' + file.name.split('.').pop()?.toLowerCase();

    if (!validExtensions.includes(fileExt)) {
      setErrorMessage(`Invalid file type (${fileExt}). Allowed: ${validExtensions.join(', ')}`);
      return;
    }

    if (file.size > 25 * 1024 * 1024) {
      setErrorMessage('File size exceeds 25 MB limit.');
      return;
    }

    setSelectedFile(file);
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
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  // Microphone recording
  const startRecording = async () => {
    try {
      setErrorMessage(null);
      setResult(null);
      setSelectedFile(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const recordedFile = new File(
          [audioBlob],
          `mic_sample_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.webm`,
          { type: 'audio/webm' }
        );
        validateAndSetFile(recordedFile);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(200);
      setIsRecording(true);
      setRecordingSeconds(0);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      setErrorMessage('Microphone access denied or unavailable: ' + (err.message || 'Error'));
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
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

    // Simulate animated pipeline stages
    const stageInterval = setInterval(() => {
      setPipelineStage((prev) => (prev < PIPELINE_STAGES.length - 1 ? prev + 1 : prev));
    }, 400);

    try {
      const data = await api.uploadAndDetect(selectedFile);
      setResult(data);
      if (onDetectionComplete) {
        onDetectionComplete(data);
      }
      if (redirectToDetail) {
        setTimeout(() => {
          router.push(`/detections/${data.id}`);
        }, 1200);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Detection failed.');
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
        className={`relative border-2 border-dashed rounded-2xl p-8 transition-all text-center backdrop-blur-md ${
          isDragging
            ? 'border-cyan-400 bg-cyan-950/20 scale-[1.01]'
            : selectedFile
            ? 'border-slate-700 bg-slate-900/40'
            : 'border-slate-800 bg-slate-950/50 hover:border-slate-700 hover:bg-slate-900/20'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".wav,.mp3,.ogg,.flac,.m4a,.aac,.webm"
          className="hidden"
          onChange={handleFileChange}
        />

        {isRecording ? (
          <div className="py-6 flex flex-col items-center justify-center space-y-4">
            <div className="relative flex items-center justify-center w-20 h-20 rounded-full bg-red-500/10 border border-red-500/30">
              <span className="absolute w-full h-full rounded-full bg-red-500/20 animate-ping" />
              <Mic className="w-8 h-8 text-red-400" />
            </div>
            <div>
              <span className="font-mono text-2xl font-bold text-red-400">
                {formatSecs(recordingSeconds)}
              </span>
              <p className="text-xs font-mono text-slate-400 mt-1">
                Recording live audio stream from microphone...
              </p>
            </div>
            <button
              onClick={stopRecording}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-semibold uppercase tracking-wider transition-all shadow-[0_0_15px_rgba(239,68,68,0.4)]"
            >
              <Square className="w-4 h-4" /> Stop & Validate
            </button>
          </div>
        ) : selectedFile ? (
          <div className="py-4 flex flex-col items-center justify-center space-y-4">
            <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <FileAudio className="w-7 h-7" />
            </div>
            <div className="max-w-md text-center">
              <h4 className="text-sm font-semibold text-slate-100 truncate">
                {selectedFile.name}
              </h4>
              <p className="text-xs font-mono text-slate-400 mt-1">
                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • {selectedFile.type || 'audio file'}
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isAnalyzing}
                className="px-3.5 py-1.5 rounded-lg border border-slate-700 bg-slate-800/80 hover:bg-slate-700 text-xs font-medium text-slate-300 transition-colors"
              >
                Choose Different File
              </button>
              <button
                onClick={runDetection}
                disabled={isAnalyzing}
                className="flex items-center gap-2 px-5 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-700 text-slate-950 font-semibold text-xs uppercase tracking-wider transition-all shadow-[0_0_15px_rgba(6,182,212,0.3)] hover:scale-105 active:scale-95"
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Analyzing Forensic Signal...
                  </>
                ) : (
                  <>
                    <Cpu className="w-4 h-4" /> Run Voice Cloning Analysis
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="py-8 flex flex-col items-center justify-center space-y-4">
            <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 text-slate-400 group-hover:text-cyan-400 transition-colors">
              <UploadCloud className="w-8 h-8 text-cyan-400" />
            </div>

            <div className="space-y-1">
              <h3 className="text-base font-semibold text-slate-200">
                Drop suspicious audio file here, or browse
              </h3>
              <p className="text-xs text-slate-400">
                Supports <span className="font-mono text-slate-300">WAV, MP3, OGG, FLAC, M4A, AAC, WEBM</span> up to 25 MB
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="px-4 py-2 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 text-xs font-semibold uppercase tracking-wider transition-all shadow-[0_0_10px_rgba(6,182,212,0.1)]"
              >
                Browse Audio File
              </button>
              <button
                onClick={startRecording}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 text-xs font-semibold uppercase tracking-wider transition-all"
              >
                <Mic className="w-3.5 h-3.5 text-red-400" /> Record Live Microphone
              </button>
            </div>
          </div>
        )}

        {/* Pipeline progress bar */}
        {isAnalyzing && (
          <div className="mt-6 pt-6 border-t border-slate-800 space-y-3">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-cyan-400 flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                {PIPELINE_STAGES[pipelineStage]}
              </span>
              <span className="text-slate-400">
                Step {pipelineStage + 1} of {PIPELINE_STAGES.length}
              </span>
            </div>
            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-300 rounded-full"
                style={{ width: `${((pipelineStage + 1) / PIPELINE_STAGES.length) * 100}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Error display */}
      {errorMessage && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-red-950/40 border border-red-500/30 text-red-400 text-xs">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Instant Result Summary Card */}
      {result && (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-6 backdrop-blur-md shadow-xl space-y-5 animate-in fade-in slide-in-from-bottom-2 duration-300">
          <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
            <div>
              <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
                Detection Verdict
              </span>
              <div className="flex items-center gap-3 mt-1">
                <ThreatBadge prediction={result.prediction} size="lg" />
                <ThreatBadge riskLevel={result.risk_level} size="md" />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => router.push(`/detections/${result.id}`)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-xs tracking-wider uppercase transition-all shadow-[0_0_12px_rgba(6,182,212,0.3)]"
              >
                Inspect Forensic Case <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <ConfidenceGauge
              confidence={result.confidence}
              riskLevel={result.risk_level}
              prediction={result.prediction}
              size="lg"
            />

            <div className="space-y-3 font-mono text-xs text-slate-300">
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-500">Attack Classification:</span>
                <span className="font-semibold text-slate-200">{result.attack_type || 'N/A'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-500">Engine / Model Version:</span>
                <span className="text-cyan-400">
                  {result.model_version === 'baseline-v1' ? 'Baseline ML Model (baseline-v1)' : result.model_version}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-500">Inference Latency:</span>
                <span className="text-slate-200">{result.processing_time_ms} ms</span>
              </div>
            </div>
          </div>

          {result.explanation && (
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-300 leading-relaxed">
              <span className="font-mono text-slate-400 block mb-1 font-semibold uppercase text-[10px]">
                Forensic Reasoning & Anomaly Analysis:
              </span>
              {result.explanation}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
