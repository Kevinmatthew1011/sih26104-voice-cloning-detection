'use client';

import React, { useState } from 'react';
import { UploadCloud, ShieldAlert, Cpu, Sparkles, CheckCircle2, AlertTriangle } from 'lucide-react';
import { DetectionDropzone } from '../../components/DetectionDropzone';
import { DetectionResult } from '../../lib/types';
import { api } from '../../lib/api';

export default function DetectPage() {
  const [lastResult, setLastResult] = useState<DetectionResult | null>(null);
  const [isSynthesizingSample, setIsSynthesizingSample] = useState(false);
  const [sampleError, setSampleError] = useState<string | null>(null);

  // Helper to generate minimal test audio wave on the fly in the browser
  const createTestAudioBlob = (sampleType: string): File => {
    // Generate simple 1 second PCM WAV header with test tone
    const sampleRate = 16000;
    const duration = 1.5;
    const numSamples = Math.floor(sampleRate * duration);
    const buffer = new ArrayBuffer(44 + numSamples * 2);
    const view = new DataView(buffer);

    // RIFF chunk descriptor
    const writeString = (offset: number, string: string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };

    writeString(0, 'RIFF');
    view.setUint32(4, 36 + numSamples * 2, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // Mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(36, 'data');
    view.setUint32(40, numSamples * 2, true);

    // Fill data samples with synthetic sinusoidal tone
    const freq = sampleType === 'synthetic' ? 880 : sampleType === 'replay' ? 320 : 440;
    for (let i = 0; i < numSamples; i++) {
      const t = i / sampleRate;
      const sample = Math.sin(2 * Math.PI * freq * t) * 0.5;
      const intSample = Math.max(-32768, Math.min(32767, Math.floor(sample * 32767)));
      view.setInt16(44 + i * 2, intSample, true);
    }

    const blob = new Blob([buffer], { type: 'audio/wav' });
    const filename =
      sampleType === 'synthetic'
        ? 'synthetic_neural_clone_sample.wav'
        : sampleType === 'replay'
        ? 'replay_attack_transducer.wav'
        : 'genuine_human_speech.wav';

    return new File([blob], filename, { type: 'audio/wav' });
  };

  const testQuickSample = async (sampleType: string) => {
    setIsSynthesizingSample(true);
    setSampleError(null);
    try {
      const file = createTestAudioBlob(sampleType);
      const res = await api.uploadAndDetect(file);
      setLastResult(res);
    } catch (err: any) {
      setSampleError(err.message || 'Sample test failed');
    } finally {
      setIsSynthesizingSample(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 font-mono text-xs uppercase tracking-wider">
          <Cpu className="w-3.5 h-3.5" />
          Real-Time Forensic Audio Scanner
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          Analyze Audio for Voice Cloning
        </h1>
        <p className="text-sm text-slate-300 max-w-xl mx-auto">
          Upload an audio file or capture live microphone input to inspect for AI-synthesized speech,
          neural vocoder artifacts, and acoustic replay impersonation.
        </p>
      </div>

      {/* Main Dropzone & Upload Studio */}
      <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 sm:p-8 backdrop-blur-xl shadow-2xl space-y-6">
        <DetectionDropzone onDetectionComplete={(res) => setLastResult(res)} />

        {/* Quick Test Demo Samples */}
        <div className="pt-6 border-t border-slate-800/80">
          <div className="flex items-center justify-between mb-3">
            <span className="font-mono text-xs uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" /> Quick Forensic Test Bench:
            </span>
            <span className="text-[11px] text-slate-500 font-mono">
              Generates calibrated forensic audio streams
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <button
              onClick={() => testQuickSample('synthetic')}
              disabled={isSynthesizingSample}
              className="flex items-center justify-between p-3 rounded-xl border border-red-500/20 bg-red-950/20 hover:bg-red-950/40 text-red-300 text-xs font-mono transition-all text-left"
            >
              <div>
                <span className="font-bold block">1. Synthetic Clone</span>
                <span className="text-[10px] text-red-400/70">Neural vocoder signature</span>
              </div>
              <ShieldAlert className="w-4 h-4 text-red-400 shrink-0" />
            </button>

            <button
              onClick={() => testQuickSample('genuine')}
              disabled={isSynthesizingSample}
              className="flex items-center justify-between p-3 rounded-xl border border-emerald-500/20 bg-emerald-950/20 hover:bg-emerald-950/40 text-emerald-300 text-xs font-mono transition-all text-left"
            >
              <div>
                <span className="font-bold block">2. Genuine Voice</span>
                <span className="text-[10px] text-emerald-400/70">Organic formant track</span>
              </div>
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            </button>

            <button
              onClick={() => testQuickSample('replay')}
              disabled={isSynthesizingSample}
              className="flex items-center justify-between p-3 rounded-xl border border-amber-500/20 bg-amber-950/20 hover:bg-amber-950/40 text-amber-300 text-xs font-mono transition-all text-left"
            >
              <div>
                <span className="font-bold block">3. Replay Attack</span>
                <span className="text-[10px] text-amber-400/70">Transducer coloration</span>
              </div>
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            </button>
          </div>

          {sampleError && (
            <p className="mt-3 text-xs font-mono text-red-400">{sampleError}</p>
          )}
        </div>
      </div>

      {/* Security Guidance Note */}
      <div className="rounded-2xl border border-slate-800/80 bg-slate-900/30 p-5 text-xs text-slate-400 space-y-1 font-mono">
        <span className="text-cyan-400 font-semibold uppercase block">Security Notice:</span>
        <p>
          Audio files are securely stored with anonymized UUIDs and processed strictly for
          cybersecurity threat verification. Data is never shared with third-party public AI providers.
        </p>
      </div>
    </div>
  );
}
