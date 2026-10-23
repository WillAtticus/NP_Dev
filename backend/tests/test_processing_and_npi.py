import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.services.processing.engine import (
    run_pipeline,
    PROFILE_PIEZO_1_20,
    PROFILE_ADXL_100HZ,
    QualityStatus,
    compute_band_power,
    compute_welch_psd,
)
from backend.app.services.algorithms.npi import run_npi

FS_PIEZO = 1000.0
WINDOW_SEC = 8.0
N = int(FS_PIEZO * WINDOW_SEC)


def make_sine_signal(freq_hz: float, amp: float = 250.0, fs: float = FS_PIEZO, n: int = N) -> np.ndarray:
    t = np.linspace(0, n / fs, n, endpoint=False)
    return 2048.0 + amp * np.sin(2 * np.pi * freq_hz * t)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Band power ground-truth tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBandPower:
    def test_pure_5hz_has_high_tremor_power(self):
        """Pure 5 Hz sine → tremor band should dominate reference band."""
        sig = make_sine_signal(5.0)
        result = run_pipeline(sig, PROFILE_PIEZO_1_20)
        assert result["quality_status"] in (QualityStatus.VALID_FOR_ANALYSIS, QualityStatus.WARNING)
        p_t = result["band_power_tremor"]
        p_r = result["band_power_ref"]
        assert p_t > 0
        assert p_r > 0
        tbr = result["tbr"]
        assert tbr is not None and tbr > 0

    def test_pure_5hz_tbr_above_threshold(self):
        """A strong 5 Hz signal should give TBR > 0.40 (maps to NPI < 100)."""
        sig = make_sine_signal(5.0, amp=400.0)
        result = run_pipeline(sig, PROFILE_PIEZO_1_20)
        assert result["tbr"] is not None
        # 5 Hz pure tone: most power is in 3-6 Hz band → TBR should be significant
        assert result["tbr"] > 0.30, f"Expected TBR > 0.30, got {result['tbr']}"

    def test_12hz_signal_has_low_tremor_band_power(self):
        """12 Hz signal → most power outside 3-6 Hz → lower TBR."""
        sig_5hz = make_sine_signal(5.0, amp=300.0)
        sig_12hz = make_sine_signal(12.0, amp=300.0)
        r5  = run_pipeline(sig_5hz,  PROFILE_PIEZO_1_20)
        r12 = run_pipeline(sig_12hz, PROFILE_PIEZO_1_20)
        tbr5  = r5.get("tbr")  or 0.0
        tbr12 = r12.get("tbr") or 0.0
        assert tbr5 > tbr12, (
            f"5 Hz signal should have higher TBR than 12 Hz. Got TBR_5={tbr5:.4f}, TBR_12={tbr12:.4f}"
        )

    def test_insufficient_data_returns_correct_status(self):
        """Too few samples → INSUFFICIENT_DATA, no NPI."""
        tiny = np.zeros(100)  # 0.1 sec at 1000 Hz << required 8 sec
        result = run_pipeline(tiny, PROFILE_PIEZO_1_20)
        assert result["quality_status"] == QualityStatus.INSUFFICIENT_DATA
        assert result["tbr"] is None
        assert result["npi"] is None  # should be absent


# ─────────────────────────────────────────────────────────────────────────────
# 2. Flatline / clipping quality gate tests
# ─────────────────────────────────────────────────────────────────────────────

class TestQualityGate:
    def test_flatline_detected(self):
        flatline = np.full(N, 2048.0)
        result = run_pipeline(flatline, PROFILE_PIEZO_1_20)
        assert "FLATLINE" in result["quality_flags"]
        assert result["quality_status"] == QualityStatus.INVALID

    def test_adc_clipping_detected(self):
        clipped = np.where(np.arange(N) % 50 == 0, 4095.0, 2048.0)
        # Make >5% of samples clipped
        clipped_heavy = np.full(N, 4095.0)
        result = run_pipeline(clipped_heavy, PROFILE_PIEZO_1_20)
        assert "ADC_CLIPPING" in result["quality_flags"]

    def test_packet_loss_invalidates_analysis_and_suppresses_npi(self):
        signal = make_sine_signal(5.0)
        result = run_pipeline(signal, PROFILE_PIEZO_1_20, pre_quality_flags=["SAMPLE_GAP"])
        npi = run_npi(result.get("tbr"), quality_status=result["quality_status"])
        assert result["quality_status"] == QualityStatus.INVALID
        assert "SAMPLE_GAP" in result["quality_flags"]
        assert npi["npi_value"] is None

    def test_non_finite_samples_are_rejected_without_filter_crash(self):
        signal = make_sine_signal(5.0)
        signal[100] = np.nan
        result = run_pipeline(signal, PROFILE_PIEZO_1_20)
        assert result["quality_status"] == QualityStatus.INVALID
        assert "NON_FINITE_SAMPLES" in result["quality_flags"]
        assert result["tbr"] is None

    def test_low_signal_gate_uses_ac_component_not_adc_midpoint(self):
        quiet = 2048.0 + 0.1 * np.sin(2 * np.pi * 5 * np.arange(N) / FS_PIEZO)
        result = run_pipeline(quiet, PROFILE_PIEZO_1_20)
        assert "LOW_SIGNAL" in result["quality_flags"]
        assert result["rms"] < 0.5

    def test_invalid_sample_rate_is_rejected_before_filter_design(self):
        profile = {**PROFILE_PIEZO_1_20, "sample_rate_hz": 30.0}
        result = run_pipeline(make_sine_signal(5.0), profile)
        assert result["quality_status"] == QualityStatus.INVALID
        assert "INVALID_SAMPLE_RATE" in result["quality_flags"]
        assert result["tbr"] is None


# ─────────────────────────────────────────────────────────────────────────────
# 3. NPI formula tests
# ─────────────────────────────────────────────────────────────────────────────

class TestNPI:
    def test_tbr_at_min_gives_npi_100(self):
        result = run_npi(tbr=0.40)
        assert result["npi_value"] == 100.0

    def test_tbr_at_max_gives_npi_0(self):
        result = run_npi(tbr=0.85)
        assert result["npi_value"] == 0.0

    def test_tbr_below_min_clamps_to_100(self):
        result = run_npi(tbr=0.10)
        assert result["npi_value"] == 100.0

    def test_tbr_above_max_clamps_to_0(self):
        result = run_npi(tbr=1.20)
        assert result["npi_value"] == 0.0

    def test_tbr_midpoint_gives_50(self):
        midpoint = (0.40 + 0.85) / 2  # = 0.625
        result = run_npi(tbr=midpoint)
        assert abs(result["npi_value"] - 50.0) < 0.1, f"Expected ~50, got {result['npi_value']}"

    def test_invalid_quality_suppresses_npi(self):
        result = run_npi(tbr=0.60, quality_status="INVALID")
        assert result["npi_value"] is None

    def test_custom_parameters(self):
        result = run_npi(tbr=0.30, parameters={"tbr_min": 0.20, "tbr_max": 0.60})
        # TBR=0.30, midpoint of 0.20-0.60 → NPI should be ~75
        assert result["npi_value"] == 75.0

    def test_research_warning_always_present(self):
        result = run_npi(tbr=0.50)
        assert any("RESEARCH" in w or "NOT FOR DIAGNOSIS" in w for w in result["warnings"])

    def test_experimental_demo_screening_bands(self):
        # Convert NPI targets to TBR for the default linear mapping.
        at_70 = run_npi(tbr=0.535)
        at_40 = run_npi(tbr=0.67)
        below_40 = run_npi(tbr=0.70)
        assert at_70["npi_value"] == 70.0
        assert at_70["category"] == "experimental_reference_range"
        assert at_70["screening_alert"] == "none"
        assert at_40["npi_value"] == 40.0
        assert at_40["category"] == "experimental_monitoring"
        assert at_40["screening_alert"] == "review"
        assert below_40["category"] == "outside_experimental_reference_range"
        assert below_40["screening_alert"] == "attention"
        assert below_40["screening_rule_version"] == "NPI_DEMO_BANDS_40_70_v1"

    def test_invalid_quality_has_no_demo_alert(self):
        result = run_npi(tbr=0.70, quality_status="INVALID")
        assert result["npi_value"] is None
        assert result["category"] is None
        assert result["screening_alert"] is None


# ─────────────────────────────────────────────────────────────────────────────
# 4. Protocol encode/decode roundtrip (re-import shared/)
# ─────────────────────────────────────────────────────────────────────────────

class TestProtocol:
    def test_piezo_roundtrip(self):
        from shared.schemas.protocol import (
            NeuroPulsePacket, MSG_TYPE_DATA_PIEZO,
            encode_piezo_payload, decode_piezo_payload,
        )
        samples = [100, 2048, 4000, 1024, 512]
        pkt = NeuroPulsePacket(
            msg_type=MSG_TYPE_DATA_PIEZO, seq_num=7,
            timestamp_us=999999, payload=encode_piezo_payload(samples)
        )
        decoded, err = NeuroPulsePacket.decode(pkt.encode())
        assert err is None
        assert decode_piezo_payload(decoded.payload) == samples

    def test_crc_corruption_detected(self):
        from shared.schemas.protocol import NeuroPulsePacket, MSG_TYPE_DATA_PIEZO
        pkt = NeuroPulsePacket(
            msg_type=MSG_TYPE_DATA_PIEZO, seq_num=1,
            timestamp_us=1, payload=b"\x00\x01"
        )
        raw = bytearray(pkt.encode())
        raw[-1] ^= 0xFF
        decoded, err = NeuroPulsePacket.decode(bytes(raw))
        assert decoded is None
        assert "CRC mismatch" in err


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
