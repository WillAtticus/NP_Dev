from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String, Text

try:
    from .database import Base
    from .timeutils import utcnow_naive
except ImportError:
    try:
        from app.db.database import Base
        from app.db.timeutils import utcnow_naive
    except ImportError:
        from backend.app.db.database import Base
        from backend.app.db.timeutils import utcnow_naive


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)  # UUID
    study_id = Column(String, nullable=True)
    participant_code = Column(String, nullable=True)  # pseudonym
    sensor_type = Column(String, nullable=False)  # PIEZO_LDT0_028K / ADXL345
    profile_id = Column(String, nullable=False)
    status = Column(String, default="created")  # created/recording/completed/failed/cancelled
    provenance = Column(String, default="simulated")  # simulated/device/imported_benchmark/reprocessed
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_sec = Column(Float, nullable=True)
    sample_count = Column(Integer, nullable=True)
    sample_rate_hz = Column(Float, nullable=True)
    tbr = Column(Float, nullable=True)
    npi_value = Column(Float, nullable=True)
    npi_category = Column(String, nullable=True)
    quality_status = Column(String, nullable=True)
    quality_flags = Column(String, nullable=True)  # JSON list stored as string
    dominant_freq_hz = Column(Float, nullable=True)
    sha256_hash = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    raw_data_path = Column(String, nullable=True)  # path to HDF5/JSON raw file
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    is_deleted = Column(Boolean, default=False)  # soft delete


class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True)  # UUID
    serial_port = Column(String, nullable=True)
    baud_rate = Column(Integer, default=115200)
    sensor_type = Column(String, nullable=False)
    firmware_version = Column(String, nullable=True)
    protocol_version = Column(String, nullable=True)
    is_simulator = Column(Boolean, default=True)
    last_connected = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utcnow_naive)
    action = Column(String, nullable=False)  # session_created, session_started, session_stopped, etc.
    actor = Column(String, default="operator")  # role
    session_id = Column(String, nullable=True)
    detail = Column(Text, nullable=True)  # JSON string


class LocalUser(Base):
    __tablename__ = "local_users"
    id = Column(String, primary_key=True)
    username = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=utcnow_naive)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive)


class Study(Base):
    __tablename__ = "studies"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    protocol_version = Column(String, default="1.0.0")
    description = Column(Text, nullable=True)
    sensor_type = Column(String, default="PIEZO_LDT0_028K")
    target_duration_sec = Column(Float, default=8.0)
    tbr_min = Column(Float, default=0.40)
    tbr_max = Column(Float, default=0.85)
    created_at = Column(DateTime, default=utcnow_naive)


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True)
    patient_code = Column(String, nullable=False, unique=True, index=True)
    full_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=True)
    chromosome_marker = Column(String, nullable=False)  # X=XX, Y=XY
    age_band = Column(String, nullable=False)
    medical_history = Column(Text, nullable=True)
    family_history = Column(Text, nullable=True)
    diet = Column(String, nullable=True)  # vegetarian / omnivore
    retain_indefinitely = Column(Boolean, nullable=False, default=False, server_default="0")
    retention_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive)
    updated_at = Column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)
