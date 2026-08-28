# Frontend API Integration & Data Contracts: SIH26104

## 1. API Client Overview (`/frontend/src/lib/api.ts`)

The frontend interacts with the FastAPI backend through a typed API client configured with dynamic base URL discovery:

```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

All network calls utilize standard `fetch` with strict TypeScript typing and unified error handling.

---

## 2. API Contract & Function Reference

### 2.1 Submit Audio for Detection (`analyzeAudioFile`)
- **Endpoint**: `POST /api/v1/detections`
- **Method**: Multipart Form-Data
- **Client Signature**:
  ```typescript
  export async function analyzeAudioFile(
    file: File | Blob,
    fileName?: string,
    inputSource: "uploaded_file" | "browser_microphone" = "uploaded_file"
  ): Promise<DetectionResponseDTO>
  ```
- **Payload**:
  - `file`: Audio binary (`Blob` / `File`).
  - `input_source`: Form string (`"uploaded_file"` or `"browser_microphone"`).
- **Return Type**: `DetectionResponseDTO` (HTTP 201).

### 2.2 Retrieve Detection History (`getDetectionsList`)
- **Endpoint**: `GET /api/v1/detections`
- **Query Parameters**:
  - `skip`: `number` (Default: 0)
  - `limit`: `number` (Default: 50, Max: 100)
- **Return Type**: `DetectionResponseDTO[]` (HTTP 200).

### 2.3 Retrieve Detection by ID (`getDetectionById`)
- **Endpoint**: `GET /api/v1/detections/{id}`
- **Parameter**: `id: string` (UUID v4)
- **Return Type**: `DetectionResponseDTO` (HTTP 200).

### 2.4 Download Forensic Evidence Report (`downloadEvidenceReport`)
- **Endpoint**: `GET /api/v1/detections/{id}/report`
- **Parameter**: `id: string` (UUID v4)
- **Return Type**: `AuditEvidenceReportDTO` (JSON formatted audit receipt).

---

## 3. TypeScript Interfaces

```typescript
export interface QualityMetrics {
  snr_db: number | null;
  clipping_ratio: number | null;
  rms_energy: number | null;
  spectral_centroid_hz: number | null;
  zero_crossing_rate: number | null;
  dynamic_range_db: number | null;
  bandwidth_hz: number | null;
}

export interface WindowResult {
  window_index: number;
  start_sec: number;
  end_sec: number;
  synthetic_probability: number;
  countermeasure_score: number;
  is_anomaly: boolean;
}

export interface DetectionResponseDTO {
  id: string;
  filename: string;
  file_size_bytes: number;
  mime_type: string;
  sha256_hash: string;
  prediction: "real" | "synthetic";
  confidence: number;
  risk_level: "low" | "medium" | "high";
  countermeasure_score: number;
  synthetic_probability: number;
  raw_ml_action: "ALLOW" | "VERIFY" | "BLOCK";
  operational_action: "ALLOW" | "VERIFY" | "BLOCK";
  decision_reason: string;
  capture_domain_reliability: "trusted_file" | "unvalidated";
  input_source: "uploaded_file" | "browser_microphone";
  model_version: string;
  created_at: string;
  quality: QualityMetrics | null;
  windows: WindowResult[] | null;
}
```
