export type PredictionType = 'real' | 'synthetic' | 'replay' | 'unknown';
export type RiskLevelType = 'low' | 'medium' | 'high';
export type CaseStatusType = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

export interface DetectionResult {
  id: string;
  prediction: PredictionType;
  confidence: number;
  risk_level: RiskLevelType;
  model_version: string;
  processing_time_ms: number;
  created_at: string;
  attack_type?: string | null;
  explanation?: string | null;
  spectral_artifacts?: Record<string, any> | null;
  metadata_json?: Record<string, any> | null;
}

export interface DetectionCaseSummary {
  id: string;
  filename: string;
  file_size_bytes: number;
  mime_type: string;
  duration_seconds?: number | null;
  status: CaseStatusType;
  created_at: string;
  updated_at: string;
  result?: DetectionResult | null;
}

export interface DetectionCaseDetail {
  id: string;
  filename: string;
  file_size_bytes: number;
  mime_type: string;
  duration_seconds?: number | null;
  status: CaseStatusType;
  created_at: string;
  updated_at: string;
  audio_url: string;
  result?: DetectionResult | null;
}

export interface DetectionListResponse {
  total: number;
  items: DetectionCaseSummary[];
  limit: number;
  skip: number;
}

export interface HealthStatus {
  status: string;
  environment: string;
  version: string;
  database: string;
  detection_engine: string;
  model_version: string;
  timestamp: string;
  details: {
    supported_extensions: string[];
    max_file_size_bytes: number;
    engine_info: Record<string, any>;
  };
}
