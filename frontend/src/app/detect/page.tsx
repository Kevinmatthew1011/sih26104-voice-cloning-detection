'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ShieldAlert, Cpu, Sparkles, CheckCircle2 } from 'lucide-react';
import { DetectionDropzone } from '../../components/DetectionDropzone';

import { api } from '../../lib/api';

export default function DetectPage() {
  const router = useRouter();
  const [isSynthesizingSample, setIsSynthesizingSample] = useState(false);
  const [sampleError, setSampleError] = useState<string | null>(null);

  // Helper to generate minimal test audio waveform for quick test bench
  const createTestAudioBlob = (sampleType: string): File => {
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

    // Fill data samples with synthetic test tones
    const freq = sampleType === 'synthetic' ? 880 : 440;
    for (let i = 0; i < numSamples; i++) {
      const t = i / sampleRate;
      const sample = Math.sin(2 * Math.PI * freq * t) * 0.5;
      const intSample = Math.max(-32768, Math.min(32767, Math.floor(sample * 32767)));
      view.setInt16(44 + i * 2, intSample, true);
    }

    const blob = new Blob([buffer], { type: 'audio/wav' });
    const filename =
      sampleType === 'synthetic'
        ? 'synthetic_speech_test.wav'
        : 'real_speech_test.wav';

    return new File([blob], filename, { type: 'audio/wav' });
  };

  const testQuickSample = async (sampleType: string) => {
    setIsSynthesizingSample(true);
    setSampleError(null);
    try {
      const file = createTestAudioBlob(sampleType);
      const res = await api.uploadAndDetect(file);
      router.push(`/detections/${res.id}`);
    } catch (err: unknown) {
      setSampleError(err instanceof Error ? err.message : 'Sample test failed');
    } finally {
      setIsSynthesizingSample(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-indigo-200 bg-indigo-50 text-indigo-700 font-mono text-xs uppercase tracking-wider font-semibold">
          <Cpu className="w-3.5 h-3.5 text-indigo-600" />
          VOICE CLONING DETECTION SCANNER
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
          Analyze Audio for Synthetic Speech
        </h1>
        <p className="text-sm text-slate-600 max-w-xl mx-auto">
          Upload an audio file or capture microphone input to analyze it for potential synthetic-speech indicators.
        </p>
      </div>

      {/* Main Dropzone & Upload Studio */}
      <div className="rounded-3xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
        <DetectionDropzone redirectToDetail={true} />

        {/* Quick Test Demo Samples */}
        <div className="pt-6 border-t border-slate-100">
          <div className="flex items-center justify-between mb-3">
            <span className="font-mono text-xs uppercase tracking-wider text-slate-600 flex items-center gap-1.5 font-semibold">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" /> Development Test Inputs:
            </span>
            <span className="text-[11px] text-slate-400 font-mono">
              DEVELOPMENT TEST INPUTS
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              onClick={() => testQuickSample('synthetic')}
              disabled={isSynthesizingSample}
              className="flex items-center justify-between p-3.5 rounded-xl border border-red-200 bg-red-50/60 hover:bg-red-50 text-red-900 text-xs font-mono transition-all text-left shadow-xs cursor-pointer disabled:opacity-50"
            >
              <div>
                <span className="font-bold block text-red-900">1. SYNTHETIC SPEECH</span>
                <span className="text-[10px] text-red-700/80">Baseline synthetic-speech test</span>
              </div>
              <ShieldAlert className="w-4 h-4 text-red-600 shrink-0" />
            </button>

            <button
              onClick={() => testQuickSample('real')}
              disabled={isSynthesizingSample}
              className="flex items-center justify-between p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/60 hover:bg-emerald-50 text-emerald-900 text-xs font-mono transition-all text-left shadow-xs cursor-pointer disabled:opacity-50"
            >
              <div>
                <span className="font-bold block text-emerald-900">2. REAL SPEECH</span>
                <span className="text-[10px] text-emerald-700/80">Baseline real-speech test</span>
              </div>
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            </button>
          </div>

          {sampleError && (
            <p className="mt-3 text-xs font-mono text-red-600">{sampleError}</p>
          )}
        </div>
      </div>

      {/* Security Guidance Note */}
      <div className="rounded-2xl border border-slate-200 bg-slate-100/70 p-5 text-xs text-slate-600 space-y-1 font-mono">
        <span className="text-slate-900 font-semibold uppercase block">Security Notice:</span>
        <p>
          Audio files are securely processed and stored with unique case identifiers. Audio data is
          analyzed locally within the configured pipeline and is never shared with third-party public AI APIs.
        </p>
      </div>
    </div>
  );
}
