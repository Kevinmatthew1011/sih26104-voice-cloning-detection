import type { AcousticAssessment } from './scam-demo';

export interface LiveAcousticUpdate {
  type: 'acoustic_update';
  window_index: number;
  start_seconds: number;
  end_seconds: number;
  synthetic_probability: number;
  prediction: 'real' | 'synthetic';
  risk_level: 'low' | 'medium' | 'high';
  action: string;
  model_version: string;
  confidence?: number;
  cm_score?: number | null;
  cumulative_windows: number;
}

export interface LiveStatusEvent {
  type: 'status';
  state: 'connected' | 'buffering' | string;
  buffered_seconds?: number;
  required_seconds?: number;
  samples_buffered?: number;
  samples_required?: number;
  windows_analyzed?: number;
  engine?: string;
  sample_rate?: number;
}

export interface LiveSessionSummary {
  type: 'session_summary';
  total_duration_seconds: number;
  windows_analyzed: number;
  peak_synthetic_probability: number | null;
  final_prediction: string;
  final_risk_level: string;
  final_action: string;
  model_version: string;
}

export interface LiveErrorEvent {
  type: 'error';
  code: string;
  message: string;
  detail?: string;
}

export type LiveStreamEvent =
  | LiveStatusEvent
  | LiveAcousticUpdate
  | LiveSessionSummary
  | LiveErrorEvent;

/**
 * Pure parser for WebSocket acoustic telemetry messages.
 * Returns typed event or null if the message payload is malformed.
 */
export function parseLiveAcousticMessage(raw: unknown): LiveStreamEvent | null {
  if (!raw) return null;

  let data: unknown = raw;
  if (typeof raw === 'string') {
    try {
      data = JSON.parse(raw);
    } catch {
      return null;
    }
  }

  if (typeof data !== 'object' || data === null || !('type' in data)) {
    return null;
  }

  const rec = data as Record<string, unknown>;
  const type = String(rec.type);

  if (type === 'acoustic_update') {
    const pSynth = Number(rec.synthetic_probability);
    if (Number.isNaN(pSynth) || pSynth < 0 || pSynth > 1) {
      return null;
    }
    return {
      type: 'acoustic_update',
      window_index: Number(rec.window_index ?? 0),
      start_seconds: Number(rec.start_seconds ?? 0),
      end_seconds: Number(rec.end_seconds ?? 0),
      synthetic_probability: pSynth,
      prediction: rec.prediction === 'synthetic' ? 'synthetic' : 'real',
      risk_level:
        rec.risk_level === 'high' || rec.risk_level === 'medium' || rec.risk_level === 'low'
          ? rec.risk_level
          : pSynth >= 0.7
          ? 'high'
          : pSynth >= 0.5
          ? 'medium'
          : 'low',
      action: String(rec.action || (pSynth >= 0.7 ? 'BLOCK' : pSynth >= 0.5 ? 'VERIFY' : 'ALLOW')),
      model_version: String(rec.model_version || 'aasist-v1'),
      confidence: typeof rec.confidence === 'number' ? rec.confidence : pSynth,
      cm_score: typeof rec.cm_score === 'number' ? rec.cm_score : null,
      cumulative_windows: Number(rec.cumulative_windows ?? (Number(rec.window_index ?? 0) + 1)),
    };
  }

  if (type === 'status') {
    return {
      type: 'status',
      state: String(rec.state || 'unknown'),
      buffered_seconds: typeof rec.buffered_seconds === 'number' ? rec.buffered_seconds : undefined,
      required_seconds: typeof rec.required_seconds === 'number' ? rec.required_seconds : undefined,
      samples_buffered: typeof rec.samples_buffered === 'number' ? rec.samples_buffered : undefined,
      samples_required: typeof rec.samples_required === 'number' ? rec.samples_required : undefined,
      windows_analyzed: typeof rec.windows_analyzed === 'number' ? rec.windows_analyzed : undefined,
      engine: typeof rec.engine === 'string' ? rec.engine : undefined,
      sample_rate: typeof rec.sample_rate === 'number' ? rec.sample_rate : undefined,
    };
  }

  if (type === 'session_summary') {
    return {
      type: 'session_summary',
      total_duration_seconds: Number(rec.total_duration_seconds ?? 0),
      windows_analyzed: Number(rec.windows_analyzed ?? 0),
      peak_synthetic_probability:
        typeof rec.peak_synthetic_probability === 'number'
          ? rec.peak_synthetic_probability
          : null,
      final_prediction: String(rec.final_prediction || 'unknown'),
      final_risk_level: String(rec.final_risk_level || 'not_assessed'),
      final_action: String(rec.final_action || 'not_evaluated'),
      model_version: String(rec.model_version || 'aasist-v1'),
    };
  }

  if (type === 'error') {
    return {
      type: 'error',
      code: String(rec.code || 'STREAM_ERROR'),
      message: String(rec.message || 'An error occurred in real-time acoustic analysis.'),
      detail: typeof rec.detail === 'string' ? rec.detail : undefined,
    };
  }

  return null;
}

/**
 * Maps live telemetry state to the standard AcousticAssessment DTO.
 * Guarantees that unassessed or low-risk speech never claims verified authenticity.
 */
export function computeLiveAcousticAssessment(
  update: LiveAcousticUpdate | null,
  statusState?: string,
  error?: string | null
): AcousticAssessment {
  if (error) {
    return {
      status: 'error',
      label: 'Acoustic analysis unavailable — semantic monitoring remains active',
      syntheticProbability: null,
      confidence: null,
      riskLevel: 'not_assessed',
      prediction: null,
      action: null,
      engineType: 'AASIST',
      modelVersion: null,
      errorMessage: error,
    };
  }

  if (!update) {
    if (statusState === 'buffering' || statusState === 'connected') {
      return {
        status: 'analyzing',
        label: 'Analyzing call acoustics… (buffering sliding window)',
        syntheticProbability: null,
        confidence: null,
        riskLevel: 'not_assessed',
        prediction: null,
        action: null,
        engineType: 'AASIST',
        modelVersion: 'aasist-v1',
      };
    }
    return {
      status: 'not_analyzed',
      label: 'Waiting for live audio stream',
      syntheticProbability: null,
      confidence: null,
      riskLevel: 'not_assessed',
      prediction: null,
      action: null,
      engineType: 'AASIST',
      modelVersion: null,
    };
  }

  const pSynth = Number(update.synthetic_probability.toFixed(4));
  const isSynthetic = update.prediction === 'synthetic' || pSynth >= 0.5;
  const isGenuine = update.prediction === 'real' && pSynth < 0.5;

  return {
    status: isSynthetic ? 'synthetic_detected' : isGenuine ? 'likely_genuine' : 'inconclusive',
    label: isSynthetic ? 'Synthetic Voice Detected' : 'Likely Genuine Voice',
    syntheticProbability: pSynth,
    confidence: update.confidence !== undefined ? Number(update.confidence.toFixed(4)) : pSynth,
    riskLevel: update.risk_level,
    prediction: update.prediction,
    action:
      update.action?.toUpperCase() === 'ALLOW' ||
      update.action?.toUpperCase() === 'VERIFY' ||
      update.action?.toUpperCase() === 'BLOCK'
        ? (update.action.toUpperCase() as 'ALLOW' | 'VERIFY' | 'BLOCK')
        : isSynthetic
        ? 'BLOCK'
        : 'ALLOW',
    engineType: 'AASIST',
    modelVersion: update.model_version,
  };
}

/**
 * Builds the default WebSocket URL connecting to backend /api/v1/detections/ws.
 */
export function getWebSocketEndpoint(
  baseUrl?: string,
  options?: { format?: string; engine?: string }
): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const effectiveBase = (baseUrl || envUrl).replace(/\/+$/, '');
  const wsBase = effectiveBase.replace(/^http/, 'ws');
  const params = new URLSearchParams();
  params.set('format', options?.format || 'pcm16');
  if (options?.engine) {
    params.set('engine', options.engine);
  }
  return `${wsBase}/api/v1/detections/ws?${params.toString()}`;
}

export interface StreamCallbacks {
  onStatus?: (status: LiveStatusEvent) => void;
  onAcousticUpdate?: (update: LiveAcousticUpdate) => void;
  onError?: (error: LiveErrorEvent) => void;
  onSummary?: (summary: LiveSessionSummary) => void;
  onClose?: () => void;
}

/**
 * Stateful client managing browser microphone capture and real-time WebSocket streaming.
 */
export class CallAudioStreamClient {
  private ws: WebSocket | null = null;
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private isRunning: boolean = false;
  private callbacks: StreamCallbacks = {};
  private sessionSummary: LiveSessionSummary | null = null;

  public isStreaming(): boolean {
    return this.isRunning;
  }

  public getSummary(): LiveSessionSummary | null {
    return this.sessionSummary;
  }

  /**
   * Start microphone capture and WebSocket connection.
   */
  public async start(
    callbacks: StreamCallbacks,
    options?: { wsUrl?: string; engine?: string }
  ): Promise<void> {
    this.callbacks = callbacks;
    this.sessionSummary = null;

    if (typeof window === 'undefined') {
      this.notifyError('SSR_NOT_SUPPORTED', 'Real-time audio capture is not supported in SSR.');
      return;
    }

    // 1. Request microphone access
    if (!navigator?.mediaDevices?.getUserMedia) {
      this.notifyError(
        'MIC_UNSUPPORTED',
        'Real-time acoustic analysis unavailable — microphone API not supported.'
      );
      return;
    }

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      this.notifyError(
        'MIC_PERMISSION_DENIED',
        'Microphone access denied — semantic monitoring remains active.',
        message
      );
      return;
    }

    // 2. Establish WebSocket connection
    const targetUrl = options?.wsUrl || getWebSocketEndpoint(undefined, { engine: options?.engine });

    try {
      this.ws = new WebSocket(targetUrl);
      this.ws.binaryType = 'arraybuffer';
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      this.notifyError(
        'WS_CONNECT_FAILED',
        'Real-time acoustic analysis unavailable — semantic monitoring remains active.',
        message
      );
      this.stopCaptureTracks();
      return;
    }

    this.ws.onopen = () => {
      this.isRunning = true;
      this.setupAudioPipeline();
    };

    this.ws.onmessage = (event) => {
      const parsed = parseLiveAcousticMessage(event.data);
      if (!parsed) return;

      if (parsed.type === 'acoustic_update') {
        this.callbacks.onAcousticUpdate?.(parsed);
      } else if (parsed.type === 'status') {
        this.callbacks.onStatus?.(parsed);
      } else if (parsed.type === 'session_summary') {
        this.sessionSummary = parsed;
        this.callbacks.onSummary?.(parsed);
      } else if (parsed.type === 'error') {
        this.callbacks.onError?.(parsed);
      }
    };

    this.ws.onerror = (evt) => {
      this.notifyError(
        'WS_CONNECTION_ERROR',
        'Real-time acoustic analysis unavailable — semantic monitoring remains active.',
        String(evt)
      );
    };

    this.ws.onclose = () => {
      this.isRunning = false;
      this.callbacks.onClose?.();
      this.cleanup();
    };
  }

  private setupAudioPipeline(): void {
    if (!this.mediaStream || !this.ws) return;

    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.audioContext = new AudioCtx({ sampleRate: 16000 });

      const source = this.audioContext.createMediaStreamSource(this.mediaStream);
      // 4096 samples at 16 kHz = ~0.256s buffer per chunk
      this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

      this.processor.onaudioprocess = (e) => {
        if (!this.isRunning || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
          return;
        }

        const inputChannel = e.inputBuffer.getChannelData(0);
        // Convert Float32 [-1.0, 1.0] to 16-bit signed PCM
        const pcm16 = new Int16Array(inputChannel.length);
        for (let i = 0; i < inputChannel.length; i++) {
          const s = Math.max(-1, Math.min(1, inputChannel[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        try {
          this.ws.send(pcm16.buffer);
        } catch {
          // Send failed
        }
      };

      source.connect(this.processor);
      this.processor.connect(this.audioContext.destination);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      this.notifyError(
        'AUDIO_PIPELINE_ERROR',
        'Real-time acoustic analysis unavailable — semantic monitoring remains active.',
        message
      );
    }
  }

  private notifyError(code: string, message: string, detail?: string): void {
    this.callbacks.onError?.({
      type: 'error',
      code,
      message,
      detail,
    });
  }

  private stopCaptureTracks(): void {
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
  }

  /**
   * Stop audio capture and request final session summary from backend.
   */
  public async stop(): Promise<LiveSessionSummary | null> {
    this.isRunning = false;
    this.stopCaptureTracks();

    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }

    if (this.audioContext && this.audioContext.state !== 'closed') {
      try {
        await this.audioContext.close();
      } catch {
        // Ignore
      }
      this.audioContext = null;
    }

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      // Send end_call action to retrieve session summary
      try {
        this.ws.send(JSON.stringify({ action: 'end_call' }));
      } catch {
        // Ignore
      }
      // Wait briefly for summary event or close
      await new Promise((resolve) => setTimeout(resolve, 300));
      try {
        this.ws.close();
      } catch {
        // Ignore
      }
    }

    this.cleanup();
    return this.sessionSummary;
  }

  /**
   * Disconnect and release resources immediately.
   */
  public disconnect(): void {
    this.isRunning = false;
    this.stopCaptureTracks();
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }
    if (this.audioContext && this.audioContext.state !== 'closed') {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // Ignore
      }
      this.ws = null;
    }
  }

  private cleanup(): void {
    this.stopCaptureTracks();
    this.ws = null;
  }
}
