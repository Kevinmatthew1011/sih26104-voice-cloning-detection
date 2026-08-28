import { DetectionResult, DetectionCaseDetail, DetectionListResponse, HealthStatus, DetectionEvidenceReport } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_BASE_URL.replace(/\/+$/, '');
  }

  getAudioUrl(caseId: string): string {
    return `${this.baseUrl}/api/v1/detections/${caseId}/audio`;
  }

  async getHealth(): Promise<HealthStatus> {
    try {
      const res = await fetch(`${this.baseUrl}/api/v1/health`, {
        cache: 'no-store',
      });
      if (!res.ok) {
        throw new Error(`Health check failed with HTTP ${res.status}`);
      }
      return await res.json();
    } catch (err: any) {
      return {
        status: 'unreachable',
        environment: 'unknown',
        version: '1.0.0',
        database: 'disconnected',
        detection_engine: 'unknown',
        model_version: 'offline',
        timestamp: new Date().toISOString(),
        details: {
          supported_extensions: ['.wav', '.mp3', '.ogg', '.flac', '.m4a', '.aac', '.webm'],
          max_file_size_bytes: 25 * 1024 * 1024,
          engine_info: { error: err?.message || 'Backend server is offline' },
        },
      };
    }
  }

  async uploadAndDetect(
    file: File,
    inputSource: 'uploaded_file' | 'browser_microphone' = 'uploaded_file'
  ): Promise<DetectionResult> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    formData.append('input_source', inputSource);

    const res = await fetch(`${this.baseUrl}/api/v1/detections`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      let errorMessage = `Upload failed with status ${res.status}`;
      try {
        const errorData = await res.json();
        if (errorData.detail) {
          errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
        }
      } catch {
        // Fallback to text status
      }
      throw new Error(errorMessage);
    }

    return await res.json();
  }

  async listDetections(params?: {
    skip?: number;
    limit?: number;
    prediction?: string;
    risk_level?: string;
    search?: string;
  }): Promise<DetectionListResponse> {
    const query = new URLSearchParams();
    if (params?.skip !== undefined) query.set('skip', params.skip.toString());
    if (params?.limit !== undefined) query.set('limit', params.limit.toString());
    if (params?.prediction && params.prediction !== 'all') query.set('prediction', params.prediction);
    if (params?.risk_level && params.risk_level !== 'all') query.set('risk_level', params.risk_level);
    if (params?.search) query.set('search', params.search);

    const url = `${this.baseUrl}/api/v1/detections?${query.toString()}`;
    const res = await fetch(url, {
      cache: 'no-store',
    });

    if (!res.ok) {
      throw new Error(`Failed to load detection cases (HTTP ${res.status})`);
    }

    return await res.json();
  }

  async getDetection(id: string): Promise<DetectionCaseDetail> {
    const res = await fetch(`${this.baseUrl}/api/v1/detections/${id}`, {
      cache: 'no-store',
    });

    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Detection case '${id}' not found.`);
      }
      throw new Error(`Failed to fetch detection case (HTTP ${res.status})`);
    }

    const data = await res.json();
    // Ensure full URL for audio
    if (data.audio_url && !data.audio_url.startsWith('http')) {
      data.audio_url = `${this.baseUrl}${data.audio_url}`;
    }
    return data;
  }

  async getDetectionReport(id: string): Promise<DetectionEvidenceReport> {
    const res = await fetch(`${this.baseUrl}/api/v1/detections/${id}/report`, {
      cache: 'no-store',
    });

    if (!res.ok) {
      if (res.status === 404) {
        throw new Error(`Detection evidence report for '${id}' not found.`);
      }
      throw new Error(`Failed to fetch detection evidence report (HTTP ${res.status})`);
    }

    return await res.json();
  }
}

export const api = new ApiClient();
