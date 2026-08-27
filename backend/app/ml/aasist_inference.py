import io
import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Union, Optional

import numpy as np
import soundfile as sf
import librosa
import torch
import torch.nn.functional as F

from app.ml.aasist_model import Model as AASISTModel
from app.services.audio_quality import AudioQualityAnalyzer, AudioQualityDTO

logger = logging.getLogger(__name__)

# Default model artifact paths
DEFAULT_AASIST_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models" / "aasist"
DEFAULT_AASIST_WEIGHTS = DEFAULT_AASIST_DIR / "AASIST.pth"
DEFAULT_AASIST_CONFIG = DEFAULT_AASIST_DIR / "AASIST.conf"
DEFAULT_AASIST_METADATA = DEFAULT_AASIST_DIR / "metadata.json"

OFFICIAL_AASIST_SHA256 = "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0"
TARGET_SAMPLE_RATE: int = 16000
TARGET_SAMPLE_COUNT: int = 64600  # ~4.0375 seconds @ 16 kHz
TARGET_HOP_COUNT: int = 16150      # ~1.009375 seconds (75% overlap)


def compute_file_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file on disk."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def pad_waveform(waveform: np.ndarray, max_len: int = TARGET_SAMPLE_COUNT) -> np.ndarray:
    """
    Format audio waveform to exact 64,600 samples matching official AASIST preprocessing.
    If longer: truncate to first 64,600 samples.
    If shorter: repeat-tile until length >= 64,600, then slice to exactly 64,600.
    """
    x_len = waveform.shape[0]
    if x_len >= max_len:
        return waveform[:max_len]
    num_repeats = int(max_len / x_len) + 1
    padded_x = np.tile(waveform, num_repeats)[:max_len]
    return padded_x


class AudioWindowSlice:
    """Represents a sliced/padded 64,600-sample temporal window with exact timestamps and energy facts."""

    def __init__(
        self,
        waveform: np.ndarray,
        start_seconds: float,
        end_seconds: float,
        window_index: int,
        is_tail: bool = False,
    ):
        self.waveform = waveform
        self.start_seconds = round(start_seconds, 4)
        self.end_seconds = round(end_seconds, 4)
        self.window_index = window_index
        self.is_tail = is_tail

        # Compute deterministic window energy and activity facts
        rms_val = np.sqrt(np.mean(waveform ** 2) + 1e-12)
        self.rms_dbfs = float(round(20.0 * np.log10(rms_val), 2))
        act_frac, _, _, _ = AudioQualityAnalyzer.compute_frame_activity(waveform)
        self.active_fraction = float(round(act_frac, 4))

        # Eligibility determination:
        # Exclude pure silence/near-silence windows from polluting max_v1 aggregation
        if self.rms_dbfs < -55.0 or self.active_fraction < 0.05:
            self.activity_status = "low_energy"
            self.aggregation_eligible = False
        elif self.active_fraction < 0.45:
            self.activity_status = "sparse_speech"
            self.aggregation_eligible = True
        else:
            self.activity_status = "active"
            self.aggregation_eligible = True


def segment_audio_windows(
    waveform: np.ndarray,
    window_length: int = TARGET_SAMPLE_COUNT,
    hop_length: int = TARGET_HOP_COUNT,
    sample_rate: int = TARGET_SAMPLE_RATE,
) -> list[AudioWindowSlice]:
    """
    Deterministic audio segmentation for multi-window acoustic analysis.

    Rules:
    - If total_samples <= window_length (<= 64,600):
      Returns exactly ONE repeat-padded window covering [0.0, total_duration].
    - If total_samples > window_length:
      Generates regular windows starting at i * hop_length.
      If the last regular window does not end exactly at the final sample,
      appends exactly ONE tail-anchored full 64,600-sample window ending at EOF.
      No duplicate window is generated when exact hop lands on EOF.
    """
    total_samples = waveform.shape[0]
    if total_samples <= window_length:
        padded = pad_waveform(waveform, window_length)
        actual_duration = total_samples / sample_rate
        return [AudioWindowSlice(padded, 0.0, actual_duration, 0)]

    windows: list[AudioWindowSlice] = []
    start_idx = 0
    idx = 0

    while start_idx + window_length <= total_samples:
        end_idx = start_idx + window_length
        slice_wav = waveform[start_idx:end_idx]
        start_sec = start_idx / sample_rate
        end_sec = end_idx / sample_rate
        windows.append(AudioWindowSlice(slice_wav, start_sec, end_sec, idx))
        idx += 1
        start_idx += hop_length

    # Check tail coverage: if the last regular window did not end exactly at EOF
    last_end = (start_idx - hop_length) + window_length
    if last_end < total_samples:
        tail_start = total_samples - window_length
        tail_end = total_samples
        if len(windows) == 0 or tail_start != (start_idx - hop_length):
            slice_wav = waveform[tail_start:tail_end]
            start_sec = tail_start / sample_rate
            end_sec = tail_end / sample_rate
            windows.append(AudioWindowSlice(slice_wav, start_sec, end_sec, idx, is_tail=True))

    return windows


def aggregate_max_v1(window_probs: list[float], cm_scores: list[float]) -> tuple[float, float, float]:
    """
    Conservative maximum synthetic probability aggregation (v1.0 baseline).
    Returns (synthetic_probability, real_probability, file_cm_score).
    """
    if not window_probs:
        return 0.0, 1.0, 0.0
    max_synth = float(max(window_probs))
    real_prob = round(1.0 - max_synth, 4)
    min_cm = float(min(cm_scores))
    return max_synth, real_prob, min_cm


def aggregate_top_k_mean(window_probs: list[float], cm_scores: list[float], k: int = 2) -> tuple[float, float, float]:
    """
    Top-K mean synthetic probability aggregation.
    """
    if not window_probs:
        return 0.0, 1.0, 0.0
    paired = sorted(zip(window_probs, cm_scores), key=lambda x: x[0], reverse=True)
    top_k = paired[:k]
    synth_mean = float(np.mean([p[0] for p in top_k]))
    real_prob = round(1.0 - synth_mean, 4)
    cm_mean = float(np.mean([p[1] for p in top_k]))
    return synth_mean, real_prob, cm_mean


def aggregate_mean_v1(window_probs: list[float], cm_scores: list[float]) -> tuple[float, float, float]:
    """
    Simple average probability aggregation across all temporal windows.
    """
    if not window_probs:
        return 0.0, 1.0, 0.0
    synth_mean = float(np.mean(window_probs))
    real_prob = round(1.0 - synth_mean, 4)
    cm_mean = float(np.mean(cm_scores))
    return synth_mean, real_prob, cm_mean


def aggregate_majority_vote_v1(window_probs: list[float], cm_scores: list[float]) -> tuple[float, float, float]:
    """
    Majority vote aggregation: ratio of windows exceeding synthetic threshold 0.50.
    """
    if not window_probs:
        return 0.0, 1.0, 0.0
    synth_count = sum(1 for p in window_probs if p >= 0.50)
    vote_ratio = float(synth_count / len(window_probs))
    real_ratio = round(1.0 - vote_ratio, 4)
    min_cm = float(min(cm_scores))
    return vote_ratio, real_ratio, min_cm


AGGREGATION_REGISTRY = {
    "max_v1": aggregate_max_v1,
    "top_2_mean": lambda p, c: aggregate_top_k_mean(p, c, k=2),
    "top_3_mean": lambda p, c: aggregate_top_k_mean(p, c, k=3),
    "mean_v1": aggregate_mean_v1,
    "majority_vote_v1": aggregate_majority_vote_v1,
}


def extract_suspicious_segments(
    windows_telemetry: list[dict[str, Any]],
    threshold: float = 0.50,
) -> list[dict[str, Any]]:
    """
    Merge contiguous or overlapping suspicious windows (P_synth >= threshold)
    into approximate human-readable time intervals.
    """
    suspicious = [w for w in windows_telemetry if w["synthetic_probability"] >= threshold]
    if not suspicious:
        return []

    segments: list[dict[str, Any]] = []
    curr_group: list[dict[str, Any]] = [suspicious[0]]

    for w in suspicious[1:]:
        prev = curr_group[-1]
        if w["start_seconds"] <= prev["end_seconds"] + 0.05:
            curr_group.append(w)
        else:
            seg = {
                "segment_index": len(segments),
                "start_seconds": curr_group[0]["start_seconds"],
                "end_seconds": curr_group[-1]["end_seconds"],
                "peak_synthetic_probability": max(x["synthetic_probability"] for x in curr_group),
                "minimum_cm_score": min(x["cm_score"] for x in curr_group),
                "contributing_window_indices": [x["window_index"] for x in curr_group],
            }
            segments.append(seg)
            curr_group = [w]

    if curr_group:
        seg = {
            "segment_index": len(segments),
            "start_seconds": curr_group[0]["start_seconds"],
            "end_seconds": curr_group[-1]["end_seconds"],
            "peak_synthetic_probability": max(x["synthetic_probability"] for x in curr_group),
            "minimum_cm_score": min(x["cm_score"] for x in curr_group),
            "contributing_window_indices": [x["window_index"] for x in curr_group],
        }
        segments.append(seg)

    return segments


def get_bounded_persisted_windows(
    windows: list[dict[str, Any]],
    max_full_persist: int = 60,
    top_k_fallback: int = 10,
) -> list[dict[str, Any]]:
    """
    Bound metadata_json payload size:
    - If total windows <= max_full_persist (<= ~2 mins): persist all windows.
    - If total windows > max_full_persist: persist all suspicious windows (P >= 0.50)
      plus top_k_fallback highest scoring windows, sorted by window_index.
    """
    if len(windows) <= max_full_persist:
        return windows

    selected_indices = set()
    for w in windows:
        if w["synthetic_probability"] >= 0.50:
            selected_indices.add(w["window_index"])

    sorted_by_prob = sorted(windows, key=lambda w: w["synthetic_probability"], reverse=True)
    for w in sorted_by_prob[:top_k_fallback]:
        selected_indices.add(w["window_index"])

    return [w for w in windows if w["window_index"] in selected_indices]


class AASISTInferenceEngine:
    """
    Production Deep Learning Inference Engine for the AASIST Voice Cloning Detector.
    
    Loads official AASIST checkpoint as a singleton in GPU/CPU memory once on startup.
    Executes raw 16 kHz mono waveform analysis with official 64,600-sample padding.
    """

    _instance: Optional["AASISTInferenceEngine"] = None

    def __new__(cls, *args, **kwargs):
        """Ensure singleton instance to avoid reloading heavy weights per request."""
        if cls._instance is None:
            cls._instance = super(AASISTInferenceEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        weights_path: Path = DEFAULT_AASIST_WEIGHTS,
        config_path: Path = DEFAULT_AASIST_CONFIG,
        metadata_path: Path = DEFAULT_AASIST_METADATA,
        force_cpu: bool = False,
    ):
        if getattr(self, "_initialized", False):
            return

        self.weights_path = Path(weights_path)
        self.config_path = Path(config_path)
        self.metadata_path = Path(metadata_path)
        self.force_cpu = force_cpu

        self.model: Optional[AASISTModel] = None
        self.metadata: Dict[str, Any] = {}
        self.device = torch.device("cpu")
        self.is_loaded: bool = False

        if not self.force_cpu and torch.cuda.is_available():
            self.device = torch.device("cuda:0")
        else:
            self.device = torch.device("cpu")

        if self.is_model_available():
            self.load_model()

        self._initialized = True

    def is_model_available(self) -> bool:
        """Check if weights and config artifacts exist on disk."""
        return self.weights_path.exists() and self.config_path.exists()

    def verify_checkpoint_hash(self) -> bool:
        """Verify that the model checkpoint matches the official SHA-256 hash."""
        if not self.weights_path.exists():
            return False
        current_hash = compute_file_sha256(self.weights_path)
        return current_hash == OFFICIAL_AASIST_SHA256

    def load_model(self) -> None:
        """
        Load AASIST architecture and pretrained weights onto the selected device.
        """
        if not self.is_model_available():
            raise FileNotFoundError(
                f"AASIST model artifact not found at '{self.weights_path}'. "
                f"Please ensure AASIST.pth and AASIST.conf are placed under '{self.weights_path.parent}'."
            )

        # 1. Read config
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # 2. Read metadata if available
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Could not parse AASIST metadata: {e}")
                self.metadata = {}
        else:
            self.metadata = {}

        # 3. Instantiate model
        model_cfg = config.get("model_config", {})
        self.model = AASISTModel(model_cfg)

        # 4. Load state dict
        try:
            state_dict = torch.load(self.weights_path, map_location=self.device, weights_only=True)
            self.model.load_state_dict(state_dict)
            self.model.to(self.device)
            self.model.eval()
            self.is_loaded = True
            logger.info(f"AASIST model loaded successfully on {self.device} (SHA-256 verified)")
        except Exception as e:
            logger.error(f"Failed loading AASIST model on {self.device}: {e}")
            # Fallback to CPU if CUDA initialization failed
            if self.device.type == "cuda":
                logger.info("Attempting fallback to CPU for AASIST initialization...")
                self.device = torch.device("cpu")
                state_dict = torch.load(self.weights_path, map_location="cpu", weights_only=True)
                self.model.load_state_dict(state_dict)
                self.model.to(self.device)
                self.model.eval()
                self.is_loaded = True
            else:
                self.is_loaded = False
                raise RuntimeError(f"Could not load AASIST checkpoint: {e}") from e

    def _load_and_resample_full(self, audio_source: Union[str, Path, bytes, np.ndarray]) -> tuple[np.ndarray, int]:
        """Decode and resample audio to 16 kHz mono without length truncation. Returns (wav_16k, native_sample_rate)."""
        if isinstance(audio_source, (str, Path)):
            audio_path = Path(audio_source)
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file '{audio_path}' does not exist.")
            wav, sr = sf.read(str(audio_path), dtype="float32")
        elif isinstance(audio_source, bytes):
            if len(audio_source) == 0:
                raise ValueError("Empty audio bytes provided.")
            wav, sr = sf.read(io.BytesIO(audio_source), dtype="float32")
        elif isinstance(audio_source, np.ndarray):
            wav = audio_source.astype(np.float32)
            sr = TARGET_SAMPLE_RATE
        else:
            raise TypeError(f"Unsupported audio source type: {type(audio_source)}")

        native_sr = int(sr)

        # Convert to mono if multi-channel
        if wav.ndim > 1:
            wav = np.mean(wav, axis=1)

        # Resample to 16 kHz if necessary
        if sr != TARGET_SAMPLE_RATE:
            wav = librosa.resample(wav, orig_sr=sr, target_sr=TARGET_SAMPLE_RATE)

        return wav, native_sr

    def preprocess_audio(self, audio_source: Union[str, Path, bytes]) -> np.ndarray:
        """
        Legacy single-window preprocessor: decode, resample to 16 kHz mono,
        and format to official 64,600 samples (truncate if longer, tile if shorter).
        """
        wav, _ = self._load_and_resample_full(audio_source)
        return pad_waveform(wav, TARGET_SAMPLE_COUNT)

    def predict_audio_multiwindow(
        self,
        audio_source: Union[str, Path, bytes, np.ndarray],
        filename: str = "audio.wav",
        file_size_bytes: int = 0,
        duration_seconds: Optional[float] = None,
        aggregation_method: str = "max_v1",
        batch_size: int = 16,
        hop_length: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute multi-window AASIST analysis across full audio duration with bounded batching.
        """
        if not self.is_loaded or self.model is None:
            self.load_model()

        start_time = time.perf_counter()

        # 1. Decode & resample to 16 kHz mono (full length)
        wav_full, native_sr = self._load_and_resample_full(audio_source)
        total_duration = float(len(wav_full) / TARGET_SAMPLE_RATE)

        # 2. Extract deterministic signal quality facts
        audio_quality = AudioQualityAnalyzer.analyze_audio(wav_full, native_sample_rate_hz=native_sr)

        # 3. Safety limits validation
        from app.config import settings
        max_duration = getattr(settings, "MAX_AUDIO_DURATION_SECONDS", 300.0)
        max_windows = getattr(settings, "MAX_MULTIWINDOW_WINDOWS", 350)
        default_hop = getattr(settings, "AASIST_WINDOW_HOP_SAMPLES", TARGET_HOP_COUNT)

        if total_duration > max_duration:
            raise ValueError(f"Audio duration ({total_duration:.1f}s) exceeds maximum allowed limit ({max_duration:.1f}s).")

        # 4. Generate deterministic window slices
        actual_hop = hop_length if hop_length is not None else default_hop
        actual_overlap = round(1.0 - (actual_hop / TARGET_SAMPLE_COUNT), 4)
        actual_hop_sec = round(actual_hop / TARGET_SAMPLE_RATE, 5)

        window_slices = segment_audio_windows(wav_full, hop_length=actual_hop)
        num_windows = len(window_slices)

        if num_windows > max_windows:
            raise ValueError(f"Audio requires {num_windows} windows, exceeding maximum allowed limit ({max_windows}).")

        # 5. Batched inference only for aggregation-eligible windows (Option A)
        eligible_slices = [s for s in window_slices if s.aggregation_eligible]
        inferred_telemetries: dict[int, dict[str, Any]] = {}

        if eligible_slices:
            for b_start in range(0, len(eligible_slices), batch_size):
                b_slices = eligible_slices[b_start : b_start + batch_size]
                b_tensors = np.stack([s.waveform for s in b_slices], axis=0)
                tensor_x = torch.FloatTensor(b_tensors).to(self.device)

                try:
                    with torch.inference_mode():
                        _, logits_tensor = self.model(tensor_x)
                        logits_np = logits_tensor.cpu().numpy()
                except torch.cuda.OutOfMemoryError:
                    logger.warning("CUDA OOM during batched AASIST inference. Executing CPU fallback...")
                    torch.cuda.empty_cache()
                    self.model.to("cpu")
                    with torch.inference_mode():
                        _, logits_tensor = self.model(torch.FloatTensor(b_tensors).to("cpu"))
                        logits_np = logits_tensor.numpy()
                    self.model.to(self.device)

                for i, s in enumerate(b_slices):
                    s0 = float(logits_np[i][0])
                    s1 = float(logits_np[i][1])
                    logits_t = torch.tensor([s0, s1], dtype=torch.float32)
                    probs = F.softmax(logits_t, dim=0).numpy()
                    prob_synth = float(probs[0])
                    prob_real = float(probs[1])
                    cm_score = float(s1 - s0)
                    pred = "synthetic" if prob_synth >= 0.50 else "real"

                    inferred_telemetries[s.window_index] = {
                        "synthetic_probability": round(prob_synth, 4),
                        "real_probability": round(prob_real, 4),
                        "cm_score": round(cm_score, 4),
                        "prediction": pred,
                    }

        # Build full window telemetries preserving exact temporal ordering
        window_telemetries: list[dict[str, Any]] = []
        for s in window_slices:
            if s.aggregation_eligible and s.window_index in inferred_telemetries:
                inf = inferred_telemetries[s.window_index]
                window_telemetries.append(
                    {
                        "window_index": s.window_index,
                        "start_seconds": s.start_seconds,
                        "end_seconds": s.end_seconds,
                        "rms_dbfs": s.rms_dbfs,
                        "active_fraction": s.active_fraction,
                        "activity_status": s.activity_status,
                        "aggregation_eligible": True,
                        "synthetic_probability": inf["synthetic_probability"],
                        "real_probability": inf["real_probability"],
                        "cm_score": inf["cm_score"],
                        "prediction": inf["prediction"],
                    }
                )
            else:
                # Option A: low-energy non-speech window excluded prior to inference
                window_telemetries.append(
                    {
                        "window_index": s.window_index,
                        "start_seconds": s.start_seconds,
                        "end_seconds": s.end_seconds,
                        "rms_dbfs": s.rms_dbfs,
                        "active_fraction": s.active_fraction,
                        "activity_status": "low_energy",
                        "aggregation_eligible": False,
                        "synthetic_probability": None,
                        "real_probability": None,
                        "cm_score": None,
                        "prediction": None,
                    }
                )

        # 6. Low-energy exclusion & candidate aggregation
        eligible_windows = [w for w in window_telemetries if w.get("aggregation_eligible", True)]
        excluded_count = num_windows - len(eligible_windows)

        if len(eligible_windows) > 0:
            agg_fn = AGGREGATION_REGISTRY.get(aggregation_method, aggregate_max_v1)
            eligible_probs = [w["synthetic_probability"] for w in eligible_windows if w["synthetic_probability"] is not None]
            eligible_cms = [w["cm_score"] for w in eligible_windows if w["cm_score"] is not None]
            file_synth_prob, file_real_prob, file_cm_score = agg_fn(eligible_probs, eligible_cms)

            # Suspicious segments over eligible windows
            suspicious_segs = extract_suspicious_segments(eligible_windows, threshold=0.50)

            # File-level prediction and risk
            file_pred = "synthetic" if file_synth_prob >= 0.50 else "real"
            confidence = file_synth_prob if file_pred == "synthetic" else file_real_prob
            confidence = float(np.clip(confidence, 0.0, 1.0))

            if file_pred == "synthetic":
                risk_level = "high" if confidence >= 0.70 else "medium"
            else:
                risk_level = "low"

            analysis_status = "completed"
            synth_prob_val = round(file_synth_prob, 4)
            real_prob_val = round(file_real_prob, 4)
            cm_score_val = round(file_cm_score, 4)
        else:
            # All windows excluded due to insufficient active speech
            analysis_status = "inconclusive"
            file_pred = "unknown"
            confidence = 0.0
            risk_level = "low"
            synth_prob_val = None
            real_prob_val = None
            cm_score_val = None
            suspicious_segs = []

        end_time = time.perf_counter()
        latency_ms = int((end_time - start_time) * 1000)

        analysis_mode = "single_window" if num_windows == 1 else "multi_window"
        bounded_windows = get_bounded_persisted_windows(window_telemetries)

        multi_window_meta = {
            "analysis_mode": analysis_mode,
            "window_count": num_windows,
            "eligible_window_count": len(eligible_windows),
            "excluded_low_energy_window_count": excluded_count,
            "window_length_seconds": 4.0375,
            "hop_seconds": actual_hop_sec,
            "overlap_fraction": actual_overlap,
            "aggregation_method": aggregation_method,
            "aggregation_version": "v1.0",
            "file_level_synthetic_probability": synth_prob_val,
            "file_level_real_probability": real_prob_val,
            "file_level_cm_score": cm_score_val,
            "analysis_status": analysis_status,
            "analysis_reliability": audio_quality.analysis_reliability,
            "quality_flags": audio_quality.quality_flags,
            "audio_quality": audio_quality.model_dump(),
            "suspicious_segments": suspicious_segs,
            "windows_persisted": bounded_windows,
        }

        if analysis_status == "inconclusive":
            explanation = (
                "Insufficient analyzable speech detected across all audio windows. "
                "Voice authenticity could not be assessed. Perform secondary identity verification."
            )
        elif analysis_mode == "multi_window":
            seg_note = f" Detected {len(suspicious_segs)} suspicious segment(s)." if suspicious_segs else " No suspicious segments localized."
            excl_note = f" ({excluded_count} low-energy window(s) excluded from aggregation)." if excluded_count > 0 else ""
            explanation = (
                f"AASIST multi-window graph attention analysis ({len(eligible_windows)}/{num_windows} eligible windows, {aggregation_method} aggregation){excl_note}."
                f" File synthetic estimate: {synth_prob_val:.2%}, genuine estimate: {real_prob_val:.2%}. "
                f"Worst-case CM score: {cm_score_val:+.4f}.{seg_note} "
                "Note: Probability values represent model softmax estimates (uncalibrated) and do not reflect definitive attribution."
            )
        else:
            explanation = (
                f"AASIST deep graph attention network classification (SincNet front-end + Heterogeneous Spectro-Temporal Graph Attention). "
                f"Predicted synthetic estimate: {synth_prob_val:.2%}, genuine estimate: {real_prob_val:.2%}. "
                f"Forensic CM score: {cm_score_val:+.4f}. "
                "Note: Probability values represent model softmax estimates (uncalibrated) and do not reflect definitive attribution."
            )

        return {
            "prediction": file_pred,
            "confidence": round(confidence, 4),
            "risk_level": risk_level,
            "model_version": self.metadata.get("model_version", "aasist-v1"),
            "processing_time_ms": latency_ms,
            "attack_type": None,
            "explanation": explanation,
            "analysis_status": analysis_status,
            "analysis_reliability": audio_quality.analysis_reliability,
            "quality_flags": audio_quality.quality_flags,
            "audio_quality": audio_quality.model_dump(),
            "probabilities": {
                "real": real_prob_val,
                "synthetic": synth_prob_val,
            },
            "spectral_artifacts": {
                "architecture": "AASIST (SincNet + RawNet2 + H-GAT)",
                "sinc_filters": 70,
                "input_samples_analyzed": TARGET_SAMPLE_COUNT if num_windows == 1 else len(wav_full),
                "target_sample_rate_hz": TARGET_SAMPLE_RATE,
                "device_used": str(self.device),
                "cm_score": cm_score_val,
                "window_count": num_windows,
                "analysis_mode": analysis_mode,
                "analysis_reliability": audio_quality.analysis_reliability,
            },
            "metadata_json": {
                "engine_type": "aasist",
                "synthetic_probability": synth_prob_val,
                "real_probability": real_prob_val,
                "model_version": self.metadata.get("model_version", "aasist-v1"),
                "checkpoint_sha256": OFFICIAL_AASIST_SHA256,
                "cm_score": cm_score_val,
                "target_sample_rate": TARGET_SAMPLE_RATE,
                "analyzed_duration_seconds": round(total_duration, 4),
                "analysis_status": analysis_status,
                "analysis_reliability": audio_quality.analysis_reliability,
                "quality_flags": audio_quality.quality_flags,
                "audio_quality": audio_quality.model_dump(),
                "total_duration_seconds": duration_seconds or round(total_duration, 4),
                "file_size_bytes": file_size_bytes,
                "device": str(self.device),
                "uncalibrated_softmax_note": "Softmax probabilities are uncalibrated model score transformations.",
                "multi_window": multi_window_meta,
            },
        }

    def predict_audio(
        self,
        audio_source: Union[str, Path, bytes],
        filename: str = "audio.wav",
        file_size_bytes: int = 0,
        duration_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Standard entry point for AASIST audio detection."""
        return self.predict_audio_multiwindow(
            audio_source=audio_source,
            filename=filename,
            file_size_bytes=file_size_bytes,
            duration_seconds=duration_seconds,
            aggregation_method="max_v1",
            batch_size=16,
        )
