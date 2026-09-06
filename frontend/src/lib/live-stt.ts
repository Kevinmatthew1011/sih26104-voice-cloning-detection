/**
 * Live Speech-to-Text (STT) Client.
 *
 * Utilizes standard Web Speech API (SpeechRecognition / webkitSpeechRecognition)
 * for immediate, zero-latency continuous transcription during live calls.
 * Gracefully reports availability and errors without blocking acoustic monitoring.
 */

// SpeechRecognition type declarations for browser environment
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      length: number;
      [index: number]: {
        transcript: string;
        confidence: number;
      };
    };
  };
}

interface SpeechRecognitionErrorEventLike {
  error: string;
  message?: string;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
}

export interface LiveSTTCallbacks {
  onTranscriptSegment?: (text: string, isFinal: boolean) => void;
  onFullTranscriptChange?: (fullText: string) => void;
  onError?: (error: string) => void;
  onStatusChange?: (status: 'idle' | 'listening' | 'stopped' | 'unsupported') => void;
}

export class LiveSTTClient {
  private recognition: SpeechRecognitionLike | null = null;
  private isListening: boolean = false;
  private fullTranscript: string[] = [];
  private callbacks: LiveSTTCallbacks = {};

  constructor() {
    this.initRecognition();
  }

  public isSupported(): boolean {
    if (typeof window === 'undefined') return false;
    return !!(
      (window as unknown as { SpeechRecognition?: unknown }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition
    );
  }

  private initRecognition(): void {
    if (typeof window === 'undefined') return;

    const SpeechRec =
      (window as unknown as { SpeechRecognition?: new () => SpeechRecognitionLike }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognitionLike }).webkitSpeechRecognition;

    if (!SpeechRec) {
      return;
    }

    try {
      const rec = new SpeechRec();
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = 'en-US';

      rec.onresult = (event: SpeechRecognitionEventLike) => {
        let currentInterim = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const res = event.results[i];
          const text = res[0].transcript.trim();
          if (res.isFinal) {
            if (text) {
              this.fullTranscript.push(text);
              this.callbacks.onTranscriptSegment?.(text, true);
              this.callbacks.onFullTranscriptChange?.(this.getFullText());
            }
          } else {
            currentInterim += ` ${text}`;
          }
        }
        if (currentInterim.trim()) {
          this.callbacks.onTranscriptSegment?.(currentInterim.trim(), false);
        }
      };

      rec.onerror = (event: SpeechRecognitionErrorEventLike) => {
        if (event.error !== 'no-speech') {
          this.callbacks.onError?.(`STT Notice: ${event.error}`);
        }
      };

      rec.onend = () => {
        // Auto restart if still marked as listening
        if (this.isListening) {
          try {
            rec.start();
          } catch {
            this.isListening = false;
            this.callbacks.onStatusChange?.('stopped');
          }
        } else {
          this.callbacks.onStatusChange?.('stopped');
        }
      };

      this.recognition = rec;
    } catch {
      this.recognition = null;
    }
  }

  public start(callbacks: LiveSTTCallbacks): boolean {
    this.callbacks = callbacks;
    if (!this.recognition) {
      callbacks.onStatusChange?.('unsupported');
      callbacks.onError?.('Live Web Speech API not supported in this browser; manual input or backend STT active.');
      return false;
    }

    try {
      this.isListening = true;
      this.recognition.start();
      callbacks.onStatusChange?.('listening');
      return true;
    } catch (err: unknown) {
      this.isListening = false;
      const msg = err instanceof Error ? err.message : String(err);
      callbacks.onError?.(`Could not start live STT: ${msg}`);
      return false;
    }
  }

  public stop(): void {
    this.isListening = false;
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch {
        // Ignore
      }
    }
    this.callbacks.onStatusChange?.('stopped');
  }

  public clear(): void {
    this.fullTranscript = [];
    this.callbacks.onFullTranscriptChange?.('');
  }

  public getFullText(): string {
    return this.fullTranscript.join(' \n');
  }

  public appendExternalText(text: string): void {
    const clean = text.trim();
    if (clean) {
      this.fullTranscript.push(clean);
      this.callbacks.onFullTranscriptChange?.(this.getFullText());
    }
  }
}
