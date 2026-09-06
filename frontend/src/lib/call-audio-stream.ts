import type { AcousticAssessment } from './scam-demo';

export interface LiveAcousticUpdate {
  type: 'acoustic_update';
  engine?: string;
  engine_type?: string;
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
  engine_type?: string;
  sample_rate?: number;
}

export interface LiveSessionSummary {
  type: 'session_summary';
  engine?: string;
  engine_type?: string;
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

export interface LiveMultimodalUpdate {
  type: 'multimodal_update';
  overall_risk: 'LOW' | 'VERIFY' | 'HIGH' | 'UNASSESSED';
  recommended_action: string;
  confidence: number;
  headline: string;
  explanation: string;
  evidence_layers: Record<string, unknown>;
}

export type LiveStreamEvent =
  | LiveStatusEvent
  | LiveAcousticUpdate
  | LiveSessionSummary
  | LiveErrorEvent
  | LiveMultimodalUpdate;

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
    const engineStr =
      typeof rec.engine === 'string'
        ? rec.engine
        : typeof rec.engine_type === 'string'
        ? rec.engine_type
        : undefined;


    return {
      type: 'acoustic_update',
      engine: engineStr,
      engine_type: engineStr,
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
      model_version: String(rec.model_version || 'unknown'),
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
      engine_type: typeof rec.engine_type === 'string' ? rec.engine_type : typeof rec.engine === 'string' ? rec.engine : undefined,
      sample_rate: typeof rec.sample_rate === 'number' ? rec.sample_rate : undefined,
    };
  }

  if (type === 'session_summary') {
    const engineStr =
      typeof rec.engine === 'string'
        ? rec.engine
        : typeof rec.engine_type === 'string'
        ? rec.engine_type
        : undefined;


    return {
      type: 'session_summary',
      engine: engineStr,
      engine_type: engineStr,
      total_duration_seconds: Number(rec.total_duration_seconds ?? 0),
      windows_analyzed: Number(rec.windows_analyzed ?? 0),
      peak_synthetic_probability:
        typeof rec.peak_synthetic_probability === 'number'
          ? rec.peak_synthetic_probability
          : null,
      final_prediction: String(rec.final_prediction || 'unknown'),
      final_risk_level: String(rec.final_risk_level || 'not_assessed'),
      final_action: String(rec.final_action || 'not_evaluated'),
      model_version: String(rec.model_version || 'unknown'),
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

  if (type === 'multimodal_update') {
    const risk = String(rec.overall_risk || 'UNASSESSED').toUpperCase();
    const validRisk =
      risk === 'HIGH' || risk === 'VERIFY' || risk === 'LOW' ? risk : 'UNASSESSED';
    return {
      type: 'multimodal_update',
      overall_risk: validRisk as 'LOW' | 'VERIFY' | 'HIGH' | 'UNASSESSED',
      recommended_action: String(rec.recommended_action || 'verify'),
      confidence: typeof rec.confidence === 'number' ? rec.confidence : 0.0,
      headline: String(rec.headline || ''),
      explanation: String(rec.explanation || ''),
      evidence_layers: (rec.evidence_layers as Record<string, unknown>) || {},
    };
  }

  return null;
}

/**
 * Maps live telemetry state to the standard AcousticAssessment DTO.
 * Guarantees truthful engine reporting and ensures low-risk speech never claims verified authenticity.
 */
export function computeLiveAcousticAssessment(
  update: LiveAcousticUpdate | null,
  statusState?: string,
  error?: string | null,
  activeEngine?: string
): AcousticAssessment {
  if (error) {
    const isAasistMissing =
      error.includes('AASIST_UNAVAILABLE') ||
      error.includes('AASIST') ||
      error.includes('checkpoint') ||
      error.toLowerCase().includes('not found');
    return {
      status: 'error',
      label: 'Acoustic analysis unavailable — semantic monitoring remains active',
      syntheticProbability: null,
      confidence: null,
      riskLevel: 'not_assessed',
      prediction: null,
      action: null,
      engineType: isAasistMissing ? 'ACOUSTIC UNAVAILABLE' : 'UNAVAILABLE',
      modelVersion: null,
      errorMessage: error,
    };
  }

  const rawEngine = (update?.engine || update?.engine_type || activeEngine || '').toLowerCase();
  const isAasist = rawEngine === 'aasist' && !(update?.model_version?.toLowerCase().includes('mock') ?? false);
  const isMock =
    !isAasist &&
    (rawEngine === 'mock' ||
      rawEngine === '' ||
      (update?.model_version?.toLowerCase().includes('mock') ?? false));
  const engineDisplay = isAasist ? 'AASIST' : isMock ? 'MOCK ENGINE' : rawEngine.toUpperCase() || 'UNKNOWN';
  const fallbackModelVersion = isAasist ? 'aasist-v1' : 'mock-v1';

  if (!update) {
    if (statusState === 'buffering' || statusState === 'connected') {
      return {
        status: 'analyzing',
        label: isMock
          ? 'Buffering call acoustics (Mock Engine)…'
          : 'Buffering call acoustics… (buffering sliding window)',
        syntheticProbability: null,
        confidence: null,
        riskLevel: 'not_assessed',
        prediction: null,
        action: null,
        engineType: engineDisplay,
        modelVersion: fallbackModelVersion,
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
      engineType: engineDisplay,
      modelVersion: null,
    };
  }

  const pSynth = Number(update.synthetic_probability.toFixed(4));
  const isSynthetic = update.prediction === 'synthetic' || pSynth >= 0.5;
  const isGenuine = update.prediction === 'real' && pSynth < 0.5;

  const label = isMock
    ? isSynthetic
      ? 'Mock Synthetic Voice Detected'
      : isGenuine
      ? 'Mock Genuine Voice'
      : 'Mock Inconclusive'
    : isSynthetic
    ? 'Synthetic speech indicators detected'
    : isGenuine
    ? 'Likely human speech characteristics'
    : 'Inconclusive Voice Telemetry';

  return {
    status: isSynthetic ? 'synthetic_detected' : isGenuine ? 'likely_genuine' : 'inconclusive',
    label,
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
    engineType: engineDisplay,
    modelVersion: update.model_version || fallbackModelVersion,
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
  onDiagnostics?: (value: string) => void;
  onAcousticUpdate?: (update: LiveAcousticUpdate) => void;
  onMultimodalUpdate?: (update: LiveMultimodalUpdate) => void;
  onError?: (error: LiveErrorEvent) => void;
  onSummary?: (summary: LiveSessionSummary) => void;
  onClose?: () => void;
}

/**
 * Linear interpolation resampler from arbitrary hardware sample rate to 16,000 Hz.
 * Enforces explicit 16 kHz mono pcm_s16le audio across disparate browser and OS configurations.
 */
export function resampleTo16k(
  input: Float32Array,
  inputSampleRate: number
): Float32Array {
  if (inputSampleRate === 16000 || input.length === 0) {
    return input;
  }
  const ratio = inputSampleRate / 16000;
  const outputLength = Math.max(1, Math.round(input.length / ratio));
  const result = new Float32Array(outputLength);

  for (let i = 0; i < outputLength; i++) {
    const origIndex = i * ratio;
    const indexFloor = Math.floor(origIndex);
    const indexCeil = Math.min(input.length - 1, indexFloor + 1);
    const fraction = origIndex - indexFloor;
    result[i] = input[indexFloor] * (1 - fraction) + input[indexCeil] * fraction;
  }
  return result;
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

  private isLocalCapture: boolean = true;

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
    this.isLocalCapture = true;

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
      } else if (parsed.type === 'multimodal_update') {
        this.callbacks.onMultimodalUpdate?.(parsed);
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

  /**
   * Start analyzing an existing remote MediaStream (e.g. from WebRTC ontrack)
   * without accessing the local user's microphone.
   */
  public async startFromStream(
    stream: MediaStream,
    callbacks: StreamCallbacks,
    options?: { wsUrl?: string; engine?: string }
  ): Promise<void> {
    this.callbacks = callbacks;
    this.sessionSummary = null;
    this.isLocalCapture = false;
    this.mediaStream = stream;

    if (typeof window === 'undefined') {
      this.notifyError('SSR_NOT_SUPPORTED', 'Real-time audio analysis is not supported in SSR.');
      return;
    }

    const targetUrl = options?.wsUrl || getWebSocketEndpoint(undefined, { engine: options?.engine });

    try {
      this.ws = new WebSocket(targetUrl);
      this.ws.binaryType = 'arraybuffer';
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      this.notifyError('WS_CONNECT_FAILED', 'Failed connecting to acoustic monitoring service.', message);
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
      } else if (parsed.type === 'multimodal_update') {
        this.callbacks.onMultimodalUpdate?.(parsed);
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

  public sendContextUpdate(transcript: string, speakerId?: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(
          JSON.stringify({
            action: 'update_context',
            transcript,
            speaker_id: speakerId || null,
          })
        );
      } catch {
        // Send failed
      }
    }
  }

  public attachMediaStream(stream: MediaStream): void {
    this.stopCaptureTracks();
    this.isLocalCapture = false;
    this.mediaStream = stream;
    if (this.isRunning && this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.setupAudioPipeline();
    }
  }

  private setupAudioPipeline(): void {
    if (!this.mediaStream || !this.ws) return;

    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.audioContext = new AudioCtx({ sampleRate: 16000 });
      void this.audioContext.resume().catch(error => this.notifyError('AUDIO_CONTEXT_BLOCKED', String(error)));

      const source = this.audioContext.createMediaStreamSource(this.mediaStream);
      // 4096 samples buffer
      this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

      this.processor.onaudioprocess = (e) => {
        if (!this.isRunning || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
          return;
        }

        const inputChannel = e.inputBuffer.getChannelData(0);
        const actualSampleRate = e.inputBuffer.sampleRate || this.audioContext?.sampleRate || 16000;
        const resampled = resampleTo16k(inputChannel, actualSampleRate);

        // Convert Float32 [-1.0, 1.0] to 16-bit signed PCM (pcm_s16le)
        const pcm16 = new Int16Array(resampled.length);
        for (let i = 0; i < resampled.length; i++) {
          const s = Math.max(-1, Math.min(1, resampled[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        try {
          this.ws.send(pcm16.buffer);
          this.callbacks.onDiagnostics?.(`AudioContext: ${this.audioContext?.state}; input: ${actualSampleRate} Hz; PCM output: 16000 Hz mono s16le; resampler: ${actualSampleRate === 16000 ? 'native' : 'linear'}; WebSocket: open; frame: ${pcm16.length} samples`);
        } catch {
          // Send failed
        }
      };

      source.connect(this.processor);
      // Route through a muted gain node to satisfy ScriptProcessor graph without echoing
      const silentGain = this.audioContext.createGain();
      silentGain.gain.value = 0;
      this.processor.connect(silentGain);
      silentGain.connect(this.audioContext.destination);
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
    if (this.mediaStream && this.isLocalCapture) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
    }
    this.mediaStream = null;
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
    this.processor?.disconnect();
    this.processor = null;
    if (this.audioContext && this.audioContext.state !== 'closed') void this.audioContext.close();
    this.audioContext = null;
    this.stopCaptureTracks();
    this.ws = null;
  }
}
