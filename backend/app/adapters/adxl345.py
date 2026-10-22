import struct
from typing import Dict, List
from .base import BaseSensorAdapter

class ADXL345Adapter(BaseSensorAdapter):
    @property
    def sensor_type(self) -> str:
        return "ADXL345"

    @property
    def channel_names(self) -> List[str]:
        return ["x_counts", "y_counts", "z_counts"]

    @property
    def default_sample_rate_hz(self) -> float:
        return 100.0

    def decode_raw_payload(self, payload: bytes) -> Dict[str, List[float]]:
        if len(payload) % 6:
            raise ValueError("ADXL345 payload length must be a multiple of 6 bytes.")
        sample_count = len(payload) // 6
        x_counts, y_counts, z_counts = [], [], []
        for i in range(sample_count):
            xi, yi, zi = struct.unpack_from("<hhh", payload, i * 6)
            x_counts.append(float(xi))
            y_counts.append(float(yi))
            z_counts.append(float(zi))
        return {
            "x_counts": x_counts,
            "y_counts": y_counts,
            "z_counts": z_counts,
        }

    def check_quality(self, data: Dict[str, List[float]]) -> List[str]:
        flags = []
        axes = {name: data.get(name, []) for name in ("x_counts", "y_counts", "z_counts")}
        if not any(axes.values()):
            return ["EMPTY_DATA"]

        # Check for stuck sensor
        for axis, samples in axes.items():
            if len(samples) > 10 and len(set(samples)) == 1:
                flags.append(f"SENSOR_STUCK_{axis[0].upper()}")

        return flags
