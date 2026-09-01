from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class PhysicalQualityTelemetry(BaseModel):
    clipping_percentage: float = Field(0.0, description="Percentage of audio frames exhibiting saturation clipping")
    peak_amplitude_dbfs: float = Field(-100.0, description="Peak amplitude in dBFS")
    rms_energy_dbfs: float = Field(-100.0, description="RMS energy level in dBFS")
    estimated_snr_db: float = Field(0.0, description="Estimated Signal-to-Noise ratio in dB")
    silence_percentage: float = Field(0.0, description="Percentage of audio containing silence")


class PhysicalCaptureManifestRecord(BaseModel):
    sample_id: str = Field(..., description="Globally unique sample ID, e.g. PHYS_MIC_REC_001")
    ground_truth: Literal["real", "synthetic"] = Field(..., description="Ground truth class")
    human_identity: Optional[str] = Field(None, description="Pseudonymous human speaker ID, e.g. HUMAN_SPK_05")
    source_speaker_identity: Optional[str] = Field(None, description="Original source speaker ID if synthetic/cloned")
    source_id: str = Field(..., description="Utterance identifier or file name")
    parent_source_id: Optional[str] = Field(None, description="Parent source ID if this is a physical recapture")
    source_audio_sha256: Optional[str] = Field(None, description="SHA-256 of parent source audio if synthetic")
    capture_audio_sha256: str = Field(..., description="SHA-256 hash of the captured audio file")
    generator_name: Optional[str] = Field(None, description="Generator model if synthetic, e.g. ElevenLabs, Tacotron")
    generator_version: Optional[str] = Field(None, description="Version of generator if known")
    attack_id: Optional[str] = Field(None, description="Attack algorithm identifier, e.g. A07, A10, zero_shot")
    capture_type: Literal[
        "physical_browser_microphone",
        "physical_recapture",
        "direct_digital_control",
        "simulated_transfer",
    ] = Field("physical_browser_microphone", description="Type of capture mechanism")
    capture_device_category: Literal[
        "laptop", "mobile", "external_microphone", "other"
    ] = Field("laptop", description="Hardware device category")
    capture_device_name: Optional[str] = Field(None, description="Microphone hardware name, e.g. Realtek Array MEMS")
    playback_device: Optional[str] = Field(None, description="Playback device if physical recapture, e.g. Pixel 8 Speaker")
    browser: Optional[str] = Field(None, description="Browser client name, e.g. Google Chrome")
    browser_version: Optional[str] = Field(None, description="Browser version, e.g. 128.0.6613.119")
    os: Optional[str] = Field(None, description="Operating system, e.g. Linux x86_64, Android 14, macOS 14.5")
    requested_getUserMedia_constraints: Optional[Dict[str, Any]] = Field(None, description="Constraints passed to getUserMedia")
    applied_media_track_settings: Optional[Dict[str, Any]] = Field(None, description="Settings returned by MediaStreamTrack.getSettings()")
    media_recorder_mime_type: Optional[str] = Field(None, description="MIME container/codec used by MediaRecorder")
    input_sample_rate: Optional[int] = Field(None, description="Original recording sample rate in Hz")
    decoded_sample_rate: int = Field(16000, description="Normalized sample rate for model inference")
    duration_seconds: float = Field(..., description="Duration of audio clip in seconds")
    room_environment: Optional[str] = Field(None, description="Acoustic room environment description, e.g. quiet_office, living_room")
    capture_session_id: Optional[str] = Field(None, description="Session grouping identifier")
    prompt_id: Optional[str] = Field(None, description="Utterance prompt ID, e.g. PROMPT_01")
    recorded_at: str = Field(..., description="ISO 8601 UTC timestamp of recording")
    split: Literal["incoming_pool", "train", "validation", "dev_test", "locked_test"] = Field(
        "incoming_pool", description="Partition assignment"
    )
    quality_telemetry: Optional[PhysicalQualityTelemetry] = Field(None, description="Automated audio quality measurements")
    relative_path: str = Field(..., description="Relative path within ml_data storage")
    notes: Optional[str] = Field(None, description="Optional observational notes")


class PhysicalDomainPoolManifest(BaseModel):
    dataset_name: str = "SIH26104_PHYSICAL_DOMAIN_POOL"
    version: str = "1.0"
    description: str = "Ingestion and staging pool for multi-speaker, multi-device physical acoustic speech captures."
    updated_at: str
    total_samples: int
    summary_by_class: Dict[str, int]
    summary_by_device: Dict[str, int]
    summary_by_human_speaker: Dict[str, int]
    summary_by_split: Dict[str, int]
    samples: List[PhysicalCaptureManifestRecord]


class IngestionResponse(BaseModel):
    status: str
    sample_id: str
    ground_truth: str
    duration_seconds: float
    sha256: str
    quality_passed: bool
    quality_telemetry: PhysicalQualityTelemetry
    pool_relative_path: str
    message: str


class BalanceDashboardResponse(BaseModel):
    total_samples: int
    human_speaker_count: int
    real_sample_count: int
    synthetic_sample_count: int
    per_human_speaker: Dict[str, Dict[str, Any]]
    per_device_category: Dict[str, Dict[str, Any]]
    per_split: Dict[str, Dict[str, Any]]
    imbalance_flags: List[str]
    confound_flags: List[str]
    leakage_flags: List[str]
    ready_for_stage_2_evaluation: bool
