'use client';

import React, { useState, useRef } from 'react';
import { Play, Pause, Volume2, VolumeX, RotateCcw, Activity } from 'lucide-react';

interface AudioWaveformVisualizerProps {
  audioUrl: string;
  filename?: string;
  durationSeconds?: number | null;
  prediction?: string;
}

export const AudioWaveformVisualizer: React.FC<AudioWaveformVisualizerProps> = ({
  audioUrl,
  filename,
  durationSeconds,
  prediction,
}) => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(durationSeconds || 0);
  const [isMuted, setIsMuted] = useState(false);
  const [audioError, setAudioError] = useState<string | null>(null);

  // Frequency spectrum visualization envelope
  const [bars] = useState(() =>
    Array.from({ length: 48 }, (_, i) => {
      const x = i / 48;
      const formant1 = Math.exp(-Math.pow((x - 0.2) / 0.1, 2));
      const formant2 = Math.exp(-Math.pow((x - 0.5) / 0.15, 2));
      const formant3 = Math.exp(-Math.pow((x - 0.8) / 0.1, 2));
      const base = 0.15 + (formant1 * 0.7 + formant2 * 0.5 + formant3 * 0.3) * 0.8;
      return Math.min(1.0, Math.max(0.08, base));
    })
  );

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch(() => {
          setAudioError('Playback failed. Please interact with page first.');
        });
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current && (!durationSeconds || durationSeconds === 0)) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    setCurrentTime(time);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
    setCurrentTime(0);
  };

  const toggleMute = () => {
    if (audioRef.current) {
      audioRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remainingSecs = Math.floor(secs % 60);
    return `${mins}:${remainingSecs.toString().padStart(2, '0')}`;
  };

  const activeProgress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
      <audio
        ref={audioRef}
        src={audioUrl}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
        onError={() => setAudioError('Audio stream could not be loaded.')}
        preload="metadata"
      />

      <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-indigo-600" />
          <span className="font-mono text-xs uppercase tracking-wider text-slate-700 font-semibold">
            Audio Signal & Playback
          </span>
        </div>
        {filename && (
          <span className="font-mono text-xs text-slate-500 truncate max-w-[200px]">
            {filename}
          </span>
        )}
      </div>

      {/* Simulated Waveform Visualizer */}
      <div className="relative h-20 w-full flex items-end justify-between gap-[2px] px-2 py-3 bg-slate-50 rounded-xl border border-slate-200 overflow-hidden mb-4">
        {/* Playback progress overlay */}
        <div
          className="absolute inset-0 bg-indigo-500/10 pointer-events-none transition-all duration-100"
          style={{ width: `${activeProgress}%` }}
        />
        <div
          className="absolute top-0 bottom-0 w-[2px] bg-indigo-600 pointer-events-none shadow-xs"
          style={{ left: `${activeProgress}%` }}
        />

        {bars.map((bar, idx) => {
          const isPassed = (idx / bars.length) * 100 <= activeProgress;
          const dynamicHeight = isPlaying
            ? Math.min(100, Math.max(15, bar * 100 + (Math.sin(idx * 0.4 + currentTime * 8) * 20)))
            : bar * 100;

          const barColor =
            prediction === 'synthetic'
              ? isPassed
                ? 'bg-red-500'
                : 'bg-red-200'
              : prediction === 'replay'
              ? isPassed
                ? 'bg-amber-500'
                : 'bg-amber-200'
              : isPassed
              ? 'bg-indigo-600'
              : 'bg-slate-200';

          return (
            <div
              key={idx}
              className={`w-full rounded-t-xs transition-all duration-75 ${barColor}`}
              style={{ height: `${dynamicHeight}%` }}
            />
          );
        })}
      </div>

      {/* Scrubber & Time */}
      <div className="space-y-1 mb-4">
        <input
          type="range"
          min="0"
          max={duration || 100}
          step="0.01"
          value={currentTime}
          onChange={handleSeek}
          className="w-full h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600 focus:outline-none"
        />
        <div className="flex justify-between text-xs font-mono text-slate-500">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>

      {/* Controls Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold transition-all shadow-xs hover:scale-105 active:scale-95"
            title={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
          </button>
          <button
            onClick={() => {
              if (audioRef.current) audioRef.current.currentTime = 0;
              setCurrentTime(0);
            }}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
            title="Restart"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={toggleMute}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
          >
            {isMuted ? <VolumeX className="w-4 h-4 text-red-500" /> : <Volume2 className="w-4 h-4 text-slate-600" />}
          </button>
        </div>
      </div>

      {audioError && (
        <p className="mt-3 text-xs text-red-600 font-mono">{audioError}</p>
      )}
    </div>
  );
};
