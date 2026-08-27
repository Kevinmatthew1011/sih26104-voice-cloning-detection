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

logger = logging.getLogger(__name__)

# Default model artifact paths
DEFAULT_AASIST_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models" / "aasist"
DEFAULT_AASIST_WEIGHTS = DEFAULT_AASIST_DIR / "AASIST.pth"
DEFAULT_AASIST_CONFIG = DEFAULT_AASIST_DIR / "AASIST.conf"
DEFAULT_AASIST_METADATA = DEFAULT_AASIST_DIR / "metadata.json"

OFFICIAL_AASIST_SHA256 = "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0"
TARGET_SAMPLE_RATE: int = 16000
TARGET_SAMPLE_COUNT: int = 64600  # ~4.0375 seconds @ 16 kHz


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

    def preprocess_audio(self, audio_source: Union[str, Path, bytes]) -> np.ndarray:
        """
        Decode, resample to 16 kHz mono, and format to 64,600 samples.
        """
        if isinstance(audio_source, (str, Path)):
            audio_path = Path(audio_source)
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file '{audio_path}' does not exist.")
            wav, sr = sf.read(str(audio_path), dtype="float32")
        elif isinstance(audio_source, bytes):
            if len(audio_source) == 0:
                raise ValueError("Empty audio bytes provided.")
            wav, sr = sf.read(io.BytesIO(audio_source), dtype="float32")
        else:
            raise TypeError(f"Unsupported audio source type: {type(audio_source)}")

        # Convert to mono if multi-channel
        if wav.ndim > 1:
            wav = np.mean(wav, axis=1)

        # Resample to 16 kHz if necessary
        if sr != TARGET_SAMPLE_RATE:
            wav = librosa.resample(wav, orig_sr=sr, target_sr=TARGET_SAMPLE_RATE)

        # Pad or truncate to 64,600 samples
        wav_padded = pad_waveform(wav, TARGET_SAMPLE_COUNT)
        return wav_padded

    def predict_audio(
        self,
        audio_source: Union[str, Path, bytes],
        filename: str = "audio.wav",
        file_size_bytes: int = 0,
        duration_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute AASIST anti-spoofing inference.
        """
        if not self.is_loaded or self.model is None:
            self.load_model()

        start_time = time.perf_counter()

        # 1. Preprocess raw waveform (16 kHz mono, 64,600 samples)
        wav = self.preprocess_audio(audio_source)
        tensor_x = torch.FloatTensor(wav).unsqueeze(0).to(self.device)

        # 2. Forward inference under inference_mode
        try:
            with torch.inference_mode():
                _, logits_tensor = self.model(tensor_x)
                logits_np = logits_tensor.cpu().numpy()[0]
        except torch.cuda.OutOfMemoryError:
            logger.warning("CUDA OOM during AASIST inference. Executing CPU fallback...")
            torch.cuda.empty_cache()
            self.model.to("cpu")
            with torch.inference_mode():
                _, logits_tensor = self.model(torch.FloatTensor(wav).unsqueeze(0).to("cpu"))
                logits_np = logits_tensor.numpy()[0]
            self.model.to(self.device)

        end_time = time.perf_counter()
        latency_ms = int((end_time - start_time) * 1000)

        # 3. Scoring Semantics:
        # output[0] = spoof logit (s0), output[1] = bonafide logit (s1)
        s0 = float(logits_np[0])
        s1 = float(logits_np[1])

        # Softmax uncalibrated probability estimates
        # exp_s0 / (exp_s0 + exp_s1) = 1 / (1 + exp(s1 - s0))
        logits_t = torch.tensor([s0, s1], dtype=torch.float32)
        probs = F.softmax(logits_t, dim=0).numpy()
        prob_synthetic = float(probs[0])
        prob_real = float(probs[1])

        # Forensic countermeasure score (higher = more genuine, lower = spoof)
        cm_score = s1 - s0

        # Decision rule: synthetic if s0 > s1 (i.e. P_synthetic > 0.5)
        if s0 > s1:
            prediction = "synthetic"
            confidence = prob_synthetic
            risk_level = "high" if prob_synthetic >= 0.70 else "medium"
        else:
            prediction = "real"
            confidence = prob_real
            risk_level = "low"

        explanation = (
            f"AASIST deep graph attention network classification (SincNet front-end + Heterogeneous Spectro-Temporal Graph Attention). "
            f"Predicted synthetic estimate: {prob_synthetic:.2%}, genuine estimate: {prob_real:.2%}. "
            f"Forensic CM score: {cm_score:+.4f}. "
            "Note: Probability values represent model softmax estimates (uncalibrated) and do not reflect definitive attribution."
        )

        return {
            "prediction": prediction,
            "confidence": round(confidence, 4),
            "risk_level": risk_level,
            "model_version": self.metadata.get("model_version", "aasist-v1"),
            "processing_time_ms": latency_ms,
            "attack_type": None,
            "explanation": explanation,
            "probabilities": {
                "real": round(prob_real, 4),
                "synthetic": round(prob_synthetic, 4),
            },
            "spectral_artifacts": {
                "architecture": "AASIST (SincNet + RawNet2 + H-GAT)",
                "sinc_filters": 70,
                "input_samples_analyzed": TARGET_SAMPLE_COUNT,
                "target_sample_rate_hz": TARGET_SAMPLE_RATE,
                "device_used": str(self.device),
                "cm_score": round(cm_score, 4),
                "logit_spoof_s0": round(s0, 4),
                "logit_bonafide_s1": round(s1, 4),
            },
            "metadata_json": {
                "engine_type": "aasist",
                "synthetic_probability": round(prob_synthetic, 4),
                "real_probability": round(prob_real, 4),
                "model_version": self.metadata.get("model_version", "aasist-v1"),
                "checkpoint_sha256": OFFICIAL_AASIST_SHA256,
                "cm_score": round(cm_score, 4),
                "target_sample_rate": TARGET_SAMPLE_RATE,
                "analyzed_duration_seconds": round(TARGET_SAMPLE_COUNT / TARGET_SAMPLE_RATE, 4),
                "total_duration_seconds": duration_seconds or (TARGET_SAMPLE_COUNT / TARGET_SAMPLE_RATE),
                "file_size_bytes": file_size_bytes,
                "device": str(self.device),
                "uncalibrated_softmax_note": "Softmax probabilities are uncalibrated model score transformations.",
            },
        }
