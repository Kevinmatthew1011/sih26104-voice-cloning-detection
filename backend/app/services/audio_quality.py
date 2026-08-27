import numpy as np
from typing import List, Tuple, Optional
from pydantic import BaseModel, Field


class AudioQualityDTO(BaseModel):
    """Deterministic, model-independent acoustic signal quality facts."""
    native_sample_rate_hz: int = Field(..., description="Original sample rate of the audio file in Hz")
    effective_bandwidth_class: str = Field(..., description="Bandwidth class: 'fullband' (>=16kHz) | 'narrowband' (<16kHz)")
    rms_dbfs: float = Field(..., description="Whole-signal root mean square energy in dBFS")
    peak_amplitude: float = Field(..., description="Peak absolute waveform amplitude in [0.0, 1.0+]")
    clipped_sample_fraction: float = Field(..., description="Fraction of samples reaching digital clipping threshold (|x| >= 0.999)")
    active_speech_fraction: float = Field(..., description="Fraction of 25ms frames exceeding the -55 dBFS energy threshold")
    low_energy_fraction: float = Field(..., description="Fraction of 25ms frames below the -55 dBFS energy threshold")
    quality_flags: List[str] = Field(default_factory=list, description="Deterministic quality warning flags")
    analysis_reliability: str = Field(..., description="Analysis reliability: 'reliable' | 'degraded' | 'insufficient_speech'")


class AudioQualityAnalyzer:
    """
    Model-independent deterministic signal analyzer.
    Evaluates acoustic integrity facts without altering raw audio or predicting authenticity.
    """

    FRAME_LENGTH_SAMPLES: int = 400  # 25 ms @ 16 kHz
    FRAME_HOP_SAMPLES: int = 160     # 10 ms @ 16 kHz
    PROVISIONAL_ENERGY_THRESH_DBFS: float = -55.0  # -55 dBFS activity threshold
    PROVISIONAL_CLIPPING_THRESH: float = 0.05      # 5% severe clipping threshold
    PROVISIONAL_LOW_SIGNAL_DBFS: float = -45.0     # -45 dBFS low signal threshold
    PROVISIONAL_SPARSE_THRESH: float = 0.45        # <45% active frames indicates sparse speech
    PROVISIONAL_INSUFFICIENT_THRESH: float = 0.05  # <5% active frames indicates all-silence/insufficient speech

    @classmethod
    def compute_frame_activity(
        cls,
        wav_16k: np.ndarray,
        frame_length: int = FRAME_LENGTH_SAMPLES,
        frame_hop: int = FRAME_HOP_SAMPLES,
        energy_thresh_dbfs: float = PROVISIONAL_ENERGY_THRESH_DBFS,
    ) -> Tuple[float, float, int, int]:
        """
        Compute deterministic frame energy and active speech fraction.
        Returns: (active_fraction, low_energy_fraction, active_frames, total_frames)
        """
        total_samples = len(wav_16k)
        if total_samples < frame_length:
            rms_single = np.sqrt(np.mean(wav_16k ** 2) + 1e-12)
            dbfs_single = float(20.0 * np.log10(rms_single))
            is_active = 1 if dbfs_single >= energy_thresh_dbfs else 0
            act_frac = float(is_active)
            return act_frac, round(1.0 - act_frac, 4), is_active, 1

        num_frames = 1 + (total_samples - frame_length) // frame_hop
        active_frames = 0

        for i in range(num_frames):
            start = i * frame_hop
            end = start + frame_length
            frame = wav_16k[start:end]
            power = np.mean(frame ** 2)
            dbfs = 10.0 * np.log10(power + 1e-12)
            if dbfs >= energy_thresh_dbfs:
                active_frames += 1

        # Partial trailing frame if >= 80 samples (5ms)
        rem_start = num_frames * frame_hop
        if rem_start < total_samples:
            rem_frame = wav_16k[rem_start:]
            if len(rem_frame) >= 80:
                num_frames += 1
                power = np.mean(rem_frame ** 2)
                dbfs = 10.0 * np.log10(power + 1e-12)
                if dbfs >= energy_thresh_dbfs:
                    active_frames += 1

        active_fraction = float(round(active_frames / max(1, num_frames), 4))
        low_energy_fraction = float(round(1.0 - active_fraction, 4))
        return active_fraction, low_energy_fraction, active_frames, num_frames

    @classmethod
    def analyze_audio(
        cls,
        wav_16k: np.ndarray,
        native_sample_rate_hz: int = 16000,
    ) -> AudioQualityDTO:
        """
        Analyze audio signal facts and extract deterministic quality flags.
        """
        # 1. Whole-signal RMS and Peak
        rms_val = np.sqrt(np.mean(wav_16k ** 2) + 1e-12)
        rms_dbfs = float(round(20.0 * np.log10(rms_val), 2))
        peak_amp = float(round(float(np.max(np.abs(wav_16k))) if len(wav_16k) > 0 else 0.0, 4))

        # 2. Clipping Fraction
        if len(wav_16k) > 0:
            clipped_samples = int(np.sum(np.abs(wav_16k) >= 0.999))
            clipped_fraction = float(round(clipped_samples / len(wav_16k), 4))
        else:
            clipped_fraction = 0.0

        # 3. Frame-Level Active Speech Fraction
        act_frac, low_frac, _, _ = cls.compute_frame_activity(wav_16k)

        # 4. Bandwidth classification
        if native_sample_rate_hz >= 16000:
            bandwidth_class = "fullband"
        else:
            bandwidth_class = "narrowband"

        # 5. Deterministic Quality Flags
        quality_flags: List[str] = []

        if native_sample_rate_hz < 16000:
            quality_flags.append("SOURCE_SAMPLE_RATE_BELOW_MODEL_TARGET")

        if clipped_fraction >= cls.PROVISIONAL_CLIPPING_THRESH:
            quality_flags.append("SEVERE_CLIPPING")

        if act_frac < cls.PROVISIONAL_INSUFFICIENT_THRESH:
            quality_flags.append("INSUFFICIENT_ACTIVE_SPEECH")
        elif act_frac < cls.PROVISIONAL_SPARSE_THRESH:
            quality_flags.append("SPARSE_SPEECH_DILUTION")

        if rms_dbfs < cls.PROVISIONAL_LOW_SIGNAL_DBFS and "INSUFFICIENT_ACTIVE_SPEECH" not in quality_flags:
            quality_flags.append("LOW_SIGNAL")

        # 6. Analysis Reliability Rating
        if "INSUFFICIENT_ACTIVE_SPEECH" in quality_flags:
            reliability = "insufficient_speech"
        elif any(f in quality_flags for f in ["SOURCE_SAMPLE_RATE_BELOW_MODEL_TARGET", "SEVERE_CLIPPING", "SPARSE_SPEECH_DILUTION"]):
            reliability = "degraded"
        else:
            reliability = "reliable"

        return AudioQualityDTO(
            native_sample_rate_hz=native_sample_rate_hz,
            effective_bandwidth_class=bandwidth_class,
            rms_dbfs=rms_dbfs,
            peak_amplitude=peak_amp,
            clipped_sample_fraction=clipped_fraction,
            active_speech_fraction=act_frac,
            low_energy_fraction=low_frac,
            quality_flags=quality_flags,
            analysis_reliability=reliability,
        )
