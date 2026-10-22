import struct
from typing import Dict, List
from .base import BaseSensorAdapter

class PiezoAdapter(BaseSensorAdapter):
    @property
    def sensor_type(self) -> str:
        return "PIEZO_LDT0_028K"

    @property
    def channel_names(self) -> List[str]:
        return ["raw_counts"]

    @property
    def default_sample_rate_hz(self) -> float:
        return 1000.0

    def decode_raw_payload(self, payload: bytes) -> Dict[str, List[float]]:
        sample_count = len(payload) // 2
        counts = list(struct.unpack(f"<{sample_count}H", payload))
        return {"raw_counts": [float(c) for c in counts]}

    def check_quality(self, data: Dict[str, List[float]]) -> List[str]:
        flags = []
        counts = data.get("raw_counts", [])
        if not counts:
            return ["EMPTY_DATA"]

        # 12-bit ADC saturation checks
        clipping_low = sum(1 for c in counts if c <= 5)
        clipping_high = sum(1 for c in counts if c >= 4090)
        total = len(counts)

        if (clipping_low + clipping_high) / total > 0.05:
            flags.append("ADC_CLIPPING_SATURATION")

        # Flatline detection
        if len(set(counts)) == 1 and total > 10:
            flags.append("FLATLINE_SIGNAL")

        return flags
