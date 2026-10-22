"""
Signal Processing Engine — NeuroPulse MVP
Implements configurable pipeline: detrend → filter → Welch PSD → band power → quality gate
"""
import numpy as np
from scipy import signal as scipy_signal
from typing import Dict, List, Any, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# 1. Quality flag definitions
# ─────────────────────────────────────────────────────────────────────────────
class QualityStatus:
    VALID_FOR_ANALYSIS = "VALID_FOR_ANALYSIS"
    WARNING            = "WARNING"
    INVALID            = "INVALID"
    INSUFFICIENT_DATA  = "INSUFFICIENT_DATA"


QUALITY_REASONS = {
    "ADC_CLIPPING",
    "SAMPLE_GAP",
    "RATE_DEVIATION",
    "LOW_SIGNAL",
    "FLATLINE",
    "PACKET_CORRUPTION",
    "INSUFFICIENT_DATA",
}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Processing profile schema (dict-based, loaded from JSON / config)
# ─────────────────────────────────────────────────────────────────────────────
PROFILE_PIEZO_1_20 = {
    "profile_id":    "piezo_butterworth_1_20_default",
    "profile_version": "1.0.0",
    "sensor_type":   "PIEZO_LDT0_028K",
    "sample_unit": "adc_counts",
    "sample_rate_hz": 1000.0,
    "channels":       ["raw_counts"],
    "detrend_mode":   "linear",          # "constant" | "linear" | "none"
    "bandpass": {
        "type":  "butter",
        "order": 4,
        "low_hz":  1.0,
        "high_hz": 20.0,
    },
    "notch": {
        "enabled": True,
        "freq_hz": 50.0,
        "Q":       30.0,
    },
    "window_length_sec": 8.0,
    "window_overlap":    0.5,
    "welch": {
        "window_fn": "hann",
        "nperseg_fraction": 0.5,   # fraction of window length
        "scaling": "density",
    },
    "bands": {
        "tremor": [3.0, 6.0],
        "reference": [1.0, 20.0],
    },
    "quality_thresholds": {
        "min_signal_rms": 0.5,
        "max_clipping_ratio": 0.05,
        "max_flatline_ratio": 0.1,
    },
}

PROFILE_PIEZO_5_20 = {
    **PROFILE_PIEZO_1_20,
    "profile_id": "piezo_butterworth_5_20_candidate",
    "profile_version": "1.0.0",
    "bandpass": {"type": "butter", "order": 4, "low_hz": 5.0, "high_hz": 20.0},
    "bands": {"tremor": [3.0, 6.0], "reference": [5.0, 20.0]},
}

PROFILE_ADXL_100HZ = {
    "profile_id":    "adxl345_triaxial_100hz",
    "profile_version": "1.0.0",
    "sensor_type":   "ADXL345",
    "sample_unit": "register_counts",
    "sample_rate_hz": 100.0,
    "channels":       ["x_counts", "y_counts", "z_counts"],
    "detrend_mode":   "linear",
    "bandpass": {
        "type":  "butter",
        "order": 4,
        "low_hz":  1.0,
        "high_hz": 20.0,
    },
    "notch": {"enabled": False, "freq_hz": 50.0, "Q": 30.0},
    "window_length_sec": 8.0,
    "window_overlap":    0.5,
    "welch": {
        "window_fn": "hann",
        "nperseg_fraction": 0.5,
        "scaling": "density",
    },
    "bands": {
        "tremor": [3.0, 6.0],
        "reference": [1.0, 20.0],
    },
    "quality_thresholds": {
        "min_signal_rms": 0.001,
        "max_clipping_ratio": 0.05,
        "max_flatline_ratio": 0.1,
    },
}

BUILTIN_PROFILES: Dict[str, dict] = {
    PROFILE_PIEZO_1_20["profile_id"]: PROFILE_PIEZO_1_20,
    PROFILE_PIEZO_5_20["profile_id"]: PROFILE_PIEZO_5_20,
    PROFILE_ADXL_100HZ["profile_id"]: PROFILE_ADXL_100HZ,
}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Core processing functions
# ─────────────────────────────────────────────────────────────────────────────

def detrend(x: np.ndarray, mode: str = "linear") -> np.ndarray:
    if mode == "none":
        return x
    detrend_type = {"constant": "constant", "linear": "linear"}.get(mode, "linear")
    return scipy_signal.detrend(x, type=detrend_type)


def design_bandpass(low_hz: float, high_hz: float, fs: float, order: int = 4):
    nyq = fs / 2.0
    return scipy_signal.butter(order, [low_hz / nyq, high_hz / nyq], btype="band")


def design_notch(freq_hz: float, Q: float, fs: float):
    return scipy_signal.iirnotch(freq_hz / (fs / 2.0), Q)


def apply_filter(x: np.ndarray, b, a) -> np.ndarray:
    return scipy_signal.filtfilt(b, a, x)


def compute_welch_psd(x: np.ndarray, fs: float, nperseg: int, window_fn: str = "hann", scaling: str = "density"):
    freqs, psd = scipy_signal.welch(
        x, fs=fs, window=window_fn, nperseg=nperseg, scaling=scaling
    )
    return freqs, psd


def compute_band_power(freqs: np.ndarray, psd: np.ndarray, f_low: float, f_high: float) -> float:
    mask = (freqs >= f_low) & (freqs <= f_high)
    if not np.any(mask):
        return 0.0
    trapz_fn = getattr(np, "trapezoid", getattr(np, "trapz", None))
    return float(trapz_fn(psd[mask], freqs[mask]))


def compute_dominant_freq(freqs: np.ndarray, psd: np.ndarray) -> float:
    if psd.size == 0:
        return 0.0
    return float(freqs[np.argmax(psd)])


# ─────────────────────────────────────────────────────────────────────────────
# 4. Quality gate
# ─────────────────────────────────────────────────────────────────────────────

def quality_gate(
    raw: np.ndarray,
    profile: dict,
    pre_flags: List[str]
) -> Tuple[str, List[str]]:
    flags = list(pre_flags)
    thresholds = profile.get("quality_thresholds", {})

    # Insufficient data
    req_samples = int(profile["sample_rate_hz"] * profile["window_length_sec"])
    if len(raw) < req_samples:
        flags.append("INSUFFICIENT_DATA")
        return QualityStatus.INSUFFICIENT_DATA, flags

    # Flatline
    flatline_ratio = np.sum(np.abs(np.diff(raw)) < 1e-9) / max(len(raw) - 1, 1)
    if flatline_ratio > thresholds.get("max_flatline_ratio", 0.1):
        flags.append("FLATLINE")

    # ADC clipping (Piezo only: counts near 0 or 4095)
    if profile.get("sensor_type") == "PIEZO_LDT0_028K":
        clip_ratio = float(np.mean((raw <= 5) | (raw >= 4090)))
        if clip_ratio > thresholds.get("max_clipping_ratio", 0.05):
            flags.append("ADC_CLIPPING")

    # Low signal RMS
    rms = float(np.sqrt(np.mean(raw ** 2)))
    if rms < thresholds.get("min_signal_rms", 0.5):
        flags.append("LOW_SIGNAL")

    if any(f in ["ADC_CLIPPING", "FLATLINE", "PACKET_CORRUPTION"] for f in flags):
        return QualityStatus.INVALID, flags
    if flags:
        return QualityStatus.WARNING, flags
    return QualityStatus.VALID_FOR_ANALYSIS, flags


# ─────────────────────────────────────────────────────────────────────────────
# 5. Full pipeline — processes a single channel window
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    raw_samples: np.ndarray,
    profile: dict,
    pre_quality_flags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Runs the complete signal processing pipeline for a single channel.
    Returns a rich dict of features, PSD, quality status, and metadata.
    """
    pre_flags = pre_quality_flags or []
    fs = profile["sample_rate_hz"]
    bp_cfg = profile["bandpass"]
    notch_cfg = profile.get("notch", {})
    welch_cfg = profile["welch"]
    bands = profile["bands"]

    # ── Quality gate (on raw data) ──────────────────────────────────────────
    quality_status, quality_flags = quality_gate(raw_samples, profile, pre_flags)
    if quality_status == QualityStatus.INSUFFICIENT_DATA:
        raw_array = np.asarray(raw_samples)
        stride = max(1, int(np.ceil(len(raw_array) / 2000)))
        return {
            "quality_status": quality_status,
            "quality_flags": quality_flags,
            # Keep an honest visual trace available even before the analysis window
            # is long enough for spectral features. This is display-only raw data;
            # it does not weaken the quality gate or create an NPI result.
            "raw_signal_preview": raw_array[::stride].astype(float).tolist(),
            "raw_signal_preview_stride": stride,
            "sample_count": int(len(raw_array)),
            "tbr": None, "npi": None,
        }

    # ── Detrend ─────────────────────────────────────────────────────────────
    x = detrend(raw_samples.copy(), mode=profile.get("detrend_mode", "linear"))

    # ── Bandpass filter ─────────────────────────────────────────────────────
    b_bp, a_bp = design_bandpass(bp_cfg["low_hz"], bp_cfg["high_hz"], fs, bp_cfg.get("order", 4))
    x_filtered = apply_filter(x, b_bp, a_bp)

    # ── Optional 50 Hz notch ────────────────────────────────────────────────
    if notch_cfg.get("enabled", False):
        b_n, a_n = design_notch(notch_cfg["freq_hz"], notch_cfg["Q"], fs)
        x_filtered = apply_filter(x_filtered, b_n, a_n)

    # ── Welch PSD ───────────────────────────────────────────────────────────
    nperseg = int(len(x_filtered) * welch_cfg.get("nperseg_fraction", 0.5))
    nperseg = max(nperseg, 64)
    freqs, psd = compute_welch_psd(
        x_filtered, fs, nperseg,
        window_fn=welch_cfg.get("window_fn", "hann"),
        scaling=welch_cfg.get("scaling", "density")
    )

    # ── Band powers ─────────────────────────────────────────────────────────
    tremor_band = bands["tremor"]
    ref_band    = bands["reference"]
    p_tremor = compute_band_power(freqs, psd, tremor_band[0], tremor_band[1])
    p_ref    = compute_band_power(freqs, psd, ref_band[0], ref_band[1])
    tbr = p_tremor / p_ref if p_ref > 0 else None

    # ── Signal features ──────────────────────────────────────────────────────
    rms              = float(np.sqrt(np.mean(raw_samples ** 2)))
    peak_to_peak     = float(np.ptp(raw_samples))
    mean_val         = float(np.mean(raw_samples))
    std_val          = float(np.std(raw_samples))
    dominant_freq_hz = compute_dominant_freq(freqs, psd)

    return {
        "quality_status":     quality_status,
        "quality_flags":      quality_flags,
        "profile_id":         profile["profile_id"],
        "profile_version":    profile["profile_version"],
        "sample_count":       len(raw_samples),
        "sample_rate_hz":     fs,
        "sample_unit":        profile.get("sample_unit", "unspecified"),
        # Features
        "rms":                round(rms, 4),
        "peak_to_peak":       round(peak_to_peak, 4),
        "mean":               round(mean_val, 4),
        "std":                round(std_val, 4),
        "dominant_freq_hz":   round(dominant_freq_hz, 4),
        # Spectral
        "band_power_tremor":  round(p_tremor, 8),
        "band_power_ref":     round(p_ref, 8),
        "tbr":                round(tbr, 6) if tbr is not None else None,
        # Waveforms for charting (downsampled if needed)
        "freqs":              freqs.tolist(),
        "psd":                psd.tolist(),
        "filtered_signal":    x_filtered.tolist(),
    }


def process_session_data(
    all_samples: Dict[str, List[float]],
    profile: dict,
) -> Dict[str, Any]:
    """
    Process all channels of a session using the given profile.
    Returns per-channel pipeline results.
    """
    results = {}
    for channel, samples in all_samples.items():
        if channel not in profile.get("channels", []):
            continue
        arr = np.asarray(samples, dtype=np.float64)
        results[channel] = run_pipeline(arr, profile)
    return results
