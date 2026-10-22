# Data Contract Specification — NeuroPulse MVP

---

## 1. Logical Sensor Batch Schema (SensorBatch)

The canonical logical data structure exchanged between acquisition, storage, signal processing, and APIs.

```json
{
  "schema_version": "1.0",
  "device_id": "NP-DEV-001",
  "firmware_version": "0.1.0",
  "sensor_type": "PIEZO_LDT0_028K",
  "signal_type": "voltage",
  "channel_names": ["raw_counts"],
  "raw_unit": "counts",
  "physical_unit": "mV",
  "sample_rate_config_hz": 1000,
  "sample_index_start": 0,
  "timestamp_start_monotonic_us": 1000000,
  "sample_count": 20,
    "data": {
      "raw_counts": [1980, 2010, 2045, 1990]
    },
  "provenance": "simulated",
  "quality_flags": []
}
```

For ADXL345 acquisition, preserve the signed register values in `x_counts`, `y_counts`, and `z_counts`. Scaled `x`, `y`, and `z` acceleration and any derived `mag` channel are derived representations and must not replace the raw count channels. Their scaling configuration and units must be recorded with the session.

---

## 2. Pydantic Model Specification

```python
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class SensorType(str, Enum):
    PIEZO_LDT0_028K = "PIEZO_LDT0_028K"
    ADXL345 = "ADXL345"
    SYNTHETIC = "SYNTHETIC"

class SignalType(str, Enum):
    VOLTAGE = "voltage"
    ACCELERATION = "acceleration"

class ProvenanceType(str, Enum):
    SIMULATED = "simulated"
    DEVICE = "device"
    IMPORTED_BENCHMARK = "imported_benchmark"
    REPROCESSED = "reprocessed"

class SensorBatch(BaseModel):
    schema_version: str = "1.0"
    device_id: str
    firmware_version: str
    sensor_type: SensorType
    signal_type: SignalType
    channel_names: List[str]
    raw_unit: str = "counts"
    physical_unit: Optional[str] = None
    sample_rate_config_hz: float
    sample_index_start: int
    timestamp_start_monotonic_us: int
    sample_count: int
    data: Dict[str, List[float]]
    provenance: ProvenanceType = ProvenanceType.SIMULATED
    quality_flags: List[str] = Field(default_factory=list)
```
