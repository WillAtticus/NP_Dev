from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sensor_type: str
    profile_id: str
    status: str
    provenance: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_sec: Optional[float] = None
    tbr: Optional[float] = None
    npi_value: Optional[float] = None
    npi_category: Optional[str] = None
    quality_status: Optional[str] = None
    participant_code: Optional[str] = None
    notes: Optional[str] = None
    sample_rate_hz: Optional[float] = None
    sample_count: Optional[int] = None
    dominant_freq_hz: Optional[float] = None
    sha256_hash: Optional[str] = None
    raw_data_path: Optional[str] = None
    created_at: datetime

    @computed_field
    @property
    def session_id(self) -> str:
        return self.id

    @computed_field
    @property
    def total_samples(self) -> Optional[int]:
        return self.sample_count

    @computed_field
    @property
    def timestamp(self) -> Optional[str]:
        dt = self.start_time or self.created_at
        return dt.isoformat() if dt else None

class _Config:
    from_attributes = True


SessionResponse.Config = _Config  # type: ignore[attr-defined]


class SessionCreate(BaseModel):
    sensor_type: str
    profile_id: str = "piezo_butterworth_1_20_default"
    provenance: str = "simulated"
    participant_code: Optional[str] = None
    study_id: Optional[str] = None


class SessionUpdate(BaseModel):
    status: Optional[str] = None
    tbr: Optional[float] = None
    npi_value: Optional[float] = None
    quality_status: Optional[str] = None
    quality_flags: Optional[str] = None
    duration_sec: Optional[float] = None
    sample_count: Optional[int] = None
    dominant_freq_hz: Optional[float] = None
    notes: Optional[str] = None
    end_time: Optional[datetime] = None
    sha256_hash: Optional[str] = None
    raw_data_path: Optional[str] = None


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    serial_port: Optional[str] = None
    baud_rate: int = 115200
    sensor_type: str
    firmware_version: Optional[str] = None
    protocol_version: Optional[str] = None
    is_simulator: bool = True
    last_connected: Optional[datetime] = None
    created_at: datetime


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    action: str
    actor: str = "operator"
    session_id: Optional[str] = None
    detail: Optional[str] = None


class SessionStats(BaseModel):
    count_by_status: Dict[str, int] = Field(default_factory=dict)
    count_by_provenance: Dict[str, int] = Field(default_factory=dict)
    count_by_sensor: Dict[str, int] = Field(default_factory=dict)
    metric_means_by_sensor_profile: Dict[str, Dict[str, Optional[float]]] = Field(default_factory=dict)
    total_count: int = 0


class StudyCreate(BaseModel):
    id: Optional[str] = None
    name: str
    protocol_version: str = "1.0.0"
    description: Optional[str] = None
    sensor_type: str = "PIEZO_LDT0_028K"
    target_duration_sec: float = 8.0
    tbr_min: float = 0.40
    tbr_max: float = 0.85


class StudyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    protocol_version: str
    description: Optional[str] = None
    sensor_type: str
    target_duration_sec: float
    tbr_min: float
    tbr_max: float
    created_at: datetime


class PatientCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    date_of_birth: Optional[date] = None
    reported_sex: Optional[Literal["female", "male"]] = None
    chromosome_marker: Optional[Literal["X", "Y"]] = None  # legacy clients; mapped from reported sex when provided
    medical_history: Optional[str] = Field(default=None, max_length=4000)
    family_history: Optional[str] = Field(default=None, max_length=4000)
    diet: Optional[Literal["vegetarian", "omnivore"]] = None


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_code: str
    full_name: str
    date_of_birth: Optional[date] = None
    chromosome_marker: str
    reported_sex: Optional[str] = None
    age_band: str
    medical_history: Optional[str] = None
    family_history: Optional[str] = None
    diet: Optional[str] = None
    retain_indefinitely: bool
    retention_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PatientRetentionUpdate(BaseModel):
    retain_indefinitely: bool
