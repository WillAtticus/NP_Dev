from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class BaseSensorAdapter(ABC):
    @property
    @abstractmethod
    def sensor_type(self) -> str:
        pass

    @property
    @abstractmethod
    def channel_names(self) -> List[str]:
        pass

    @property
    @abstractmethod
    def default_sample_rate_hz(self) -> float:
        pass

    @abstractmethod
    def decode_raw_payload(self, payload: bytes) -> Dict[str, List[float]]:
        pass

    @abstractmethod
    def check_quality(self, data: Dict[str, List[float]]) -> List[str]:
        pass
