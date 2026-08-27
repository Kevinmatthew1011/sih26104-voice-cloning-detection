export type PredictionType = 'real' | 'synthetic' | 'replay' | 'unknown';
export type RiskLevelType = 'low' | 'medium' | 'high';
export type CaseStatusType = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
export type ActionType = 'ALLOW' | 'VERIFY' | 'BLOCK';

export interface SecurityDecision {
  action: ActionType;
  decision_message: string;
  synthetic_probability: number;
  policy_version: string;
  decision_source?: string | null;
  reason_codes: string[];
  recommended_steps: string[];
}

export interface DetectionResult {
  id: string;
  engine_type: string;
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
  action?: ActionType | null;
  decision_message?: string | null;
  decision?: SecurityDecision | null;
}

export interface DetectionCaseSummary {
  id: string;
  filename: string;
  file_size_bytes: number;
  mime_type: string;
  duration_seconds?: number | null;
  sample_rate?: number | null;
  channels?: number | null;
  status: CaseStatusType;
  created_at: string;
  updated_at: string;
  result?: DetectionResult | null;
}

export interface DetectionCaseDetail {
  id: string;
  filename: string;
  file_hash?: string | null;
  file_size_bytes: number;
  mime_type: string;
  duration_seconds?: number | null;
  sample_rate?: number | null;
  channels?: number | null;
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

export interface ReportCaseMetadata {
  case_id: string;
  result_id?: string | null;
  filename: string;
  status: string;
  created_at: string;
}

export interface ReportAudioEvidence {
  file_size_bytes: number;
  mime_type: string;
  duration_seconds?: number | null;
  sample_rate_hz?: number | null;
  channels?: number | null;
  file_sha256?: string | null;
}

export interface SuspiciousSegment {
  segment_index: number;
  start_seconds: number;
  end_seconds: number;
  peak_synthetic_probability: number;
  minimum_cm_score: number;
  contributing_window_indices?: number[];
}

export interface ReportModelEvidence {
  engine_type: string;
  model_version: string;
  architecture?: string | null;
  checkpoint_sha256?: string | null;
  prediction: PredictionType;
  confidence: number;
  synthetic_probability?: number | null;
  real_probability?: number | null;
  cm_score?: number | null;
  analyzed_duration_seconds?: number | null;
  processing_latency_ms: number;
  attack_type?: string | null;
  explanation?: string | null;
  scoring_note?: string | null;
  analysis_mode?: string | null;
  window_count?: number | null;
  window_length_seconds?: number | null;
  hop_seconds?: number | null;
  overlap_fraction?: number | null;
  aggregation_method?: string | null;
  aggregation_version?: string | null;
  file_level_synthetic_probability?: number | null;
  file_level_cm_score?: number | null;
  suspicious_segments?: SuspiciousSegment[] | null;
  persisted_window_count?: number | null;
}

export interface ReportAuditProvenance {
  provenance: string;
  decision_evaluated: boolean;
  device_used?: string | null;
}

export interface DetectionEvidenceReport {
  report_version: string;
  report_type: string;
  case: ReportCaseMetadata;
  audio_evidence: ReportAudioEvidence;
  model_evidence?: ReportModelEvidence | null;
  security_decision?: SecurityDecision | null;
  audit: ReportAuditProvenance;
  limitations: string[];
}
