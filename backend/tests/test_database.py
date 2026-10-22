from datetime import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.database import Base
from backend.app.db.models import AuditEvent, Device, Session
from backend.app.db.crud import (
    create_session,
    get_session,
    list_sessions,
    update_session,
    soft_delete_session,
    create_audit_event,
    get_session_count,
    get_session_stats,
    create_device,
    get_device,
    list_devices,
)
from backend.app.db.schemas import SessionResponse, SessionCreate, SessionUpdate


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_create_and_get_session(test_db):
    session = create_session(
        test_db,
        session_id="sess-001",
        sensor_type="PIEZO_LDT0_028K",
        profile_id="piezo_butterworth_1_20_default",
        provenance="simulated",
        participant_code="SUBJ_01",
    )
    assert session.id == "sess-001"
    assert session.sensor_type == "PIEZO_LDT0_028K"
    assert session.provenance == "simulated"
    assert session.participant_code == "SUBJ_01"
    assert session.status == "created"
    assert session.is_deleted is False
    assert session.created_at is not None and session.created_at.tzinfo is None

    fetched = get_session(test_db, "sess-001")
    assert fetched is not None
    assert fetched.id == "sess-001"


def test_update_session(test_db):
    create_session(
        test_db,
        session_id="sess-002",
        sensor_type="ADXL345",
        profile_id="adxl_butterworth_default",
    )
    updated = update_session(
        test_db,
        session_id="sess-002",
        status="completed",
        tbr=0.72,
        npi_value=55.4,
        npi_category="ELEVATED",
        duration_sec=10.0,
        sample_count=2500,
    )
    assert updated is not None
    assert updated.status == "completed"
    assert updated.tbr == 0.72
    assert updated.npi_value == 55.4
    assert updated.npi_category == "ELEVATED"
    assert updated.duration_sec == 10.0


def test_soft_delete_and_list_sessions(test_db):
    s1 = create_session(test_db, "sess-003a", "PIEZO_LDT0_028K", "p1")
    s2 = create_session(test_db, "sess-003b", "PIEZO_LDT0_028K", "p1")

    assert get_session_count(test_db) == 2
    active_sessions = list_sessions(test_db)
    assert len(active_sessions) == 2

    # Soft delete s1
    deleted = soft_delete_session(test_db, "sess-003a")
    assert deleted is True

    # By default, soft-deleted sessions are excluded
    assert get_session(test_db, "sess-003a") is None
    assert get_session(test_db, "sess-003a", include_deleted=True) is not None
    assert len(list_sessions(test_db)) == 1
    assert get_session_count(test_db) == 1
    assert get_session_count(test_db, include_deleted=True) == 2


def test_session_stats(test_db):
    create_session(test_db, "sess-stats-1", "PIEZO_LDT0_028K", "p1")
    update_session(test_db, "sess-stats-1", status="completed", tbr=0.5, npi_value=30.0)

    create_session(test_db, "sess-stats-2", "PIEZO_LDT0_028K", "p1")
    update_session(test_db, "sess-stats-2", status="completed", tbr=0.7, npi_value=50.0)

    create_session(test_db, "sess-stats-3", "PIEZO_LDT0_028K", "p1")
    update_session(test_db, "sess-stats-3", status="failed")

    stats = get_session_stats(test_db)
    assert stats["total_count"] == 3
    assert stats["count_by_status"]["completed"] == 2
    assert stats["count_by_status"]["failed"] == 1
    grouped_means = stats["metric_means_by_sensor_profile"]["PIEZO_LDT0_028K|p1"]
    assert pytest.approx(grouped_means["avg_tbr"], 0.01) == 0.6
    assert pytest.approx(grouped_means["avg_npi"], 0.01) == 40.0


def test_audit_event(test_db):
    event = create_audit_event(
        test_db,
        action="session_created",
        session_id="sess-001",
        actor="researcher",
        detail={"ip": "127.0.0.1", "mode": "simulated"},
    )
    assert event.id is not None
    assert event.action == "session_created"
    assert event.actor == "researcher"
    assert "127.0.0.1" in event.detail


def test_device_crud(test_db):
    device = create_device(
        test_db,
        device_id="dev-001",
        sensor_type="PIEZO_LDT0_028K",
        serial_port="COM3",
        baud_rate=115200,
        firmware_version="1.0.0",
        protocol_version="1.0.0",
        is_simulator=False,
    )
    assert device.id == "dev-001"
    fetched = get_device(test_db, "dev-001")
    assert fetched is not None
    assert fetched.serial_port == "COM3"
    assert len(list_devices(test_db)) == 1


def test_pydantic_schemas(test_db):
    session = create_session(
        test_db,
        session_id="sess-schema-1",
        sensor_type="PIEZO_LDT0_028K",
        profile_id="piezo_butterworth_1_20_default",
        provenance="simulated",
        participant_code="SUBJ_SCHEMA",
    )
    response = SessionResponse.model_validate(session)
    assert response.id == "sess-schema-1"
    assert response.sensor_type == "PIEZO_LDT0_028K"
    assert response.status == "created"

    create_data = SessionCreate(
        sensor_type="ADXL345",
        profile_id="adxl_default",
        provenance="device",
    )
    assert create_data.sensor_type == "ADXL345"

    update_data = SessionUpdate(status="completed", tbr=0.62)
    assert update_data.status == "completed"
    assert update_data.tbr == 0.62
