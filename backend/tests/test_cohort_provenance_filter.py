import datetime
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.models import Base, Patient, Session, Study
from backend.app.main import cohort_analytics


@pytest.fixture
def analytics_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_cohort_source_filter_excludes_other_provenance_from_counts_and_metrics(analytics_db):
    patient_code = f"NXM26001{uuid.uuid4().hex[:5]}"
    analytics_db.add(Patient(
        id=str(uuid.uuid4()), patient_code=patient_code, full_name="Research Participant",
        chromosome_marker="X", reported_sex="female", age_band="M", diet="vegetarian",
    ))
    simulation_only_code = f"NXM26002{uuid.uuid4().hex[:5]}"
    analytics_db.add(Patient(
        id=str(uuid.uuid4()), patient_code=simulation_only_code, full_name="Simulation Only Participant",
        chromosome_marker="Y", reported_sex="male", age_band="Y", diet="omnivore",
    ))
    analytics_db.add_all([
        Session(id="simulated-session", participant_code=patient_code, sensor_type="PIEZO_LDT0_028K",
                profile_id="profile-a", status="completed", provenance="simulated", npi_value=20.0, tbr=0.8),
        Session(id="device-session", participant_code=patient_code, sensor_type="PIEZO_LDT0_028K",
                profile_id="profile-a", status="completed", provenance="device", npi_value=80.0, tbr=0.2),
        Session(id="simulation-only-session", participant_code=simulation_only_code, sensor_type="PIEZO_LDT0_028K",
                profile_id="profile-a", status="completed", provenance="simulated", npi_value=25.0, tbr=0.7),
    ])
    analytics_db.commit()

    admin = SimpleNamespace(role="admin")
    device = cohort_analytics(analytics_db, provenance="device", actor=admin)
    assert device["selected_provenance"] == "device"
    assert device["participant_count"] == 1
    assert device["session_count"] == 1
    assert device["completed_session_count"] == 1
    assert device["by_age_band"][0]["avg_npi"] == 80.0
    assert len(device["by_age_band"]) == 1
    assert device["by_reported_sex"][0]["group"] == "Nữ"
    assert device["provenance_counts"] == {"device": 1, "simulated": 2}

    all_sources = cohort_analytics(analytics_db, actor=admin)
    assert all_sources["session_count"] == 3
    averages = {row["group"]: row["avg_npi"] for row in all_sources["by_age_band"]}
    assert averages == {"M": 50.0, "Y": 25.0}
    assert {row["group"] for row in all_sources["by_reported_sex"]} == {"Nữ", "Nam"}


def test_cohort_source_filter_rejects_unknown_values(analytics_db):
    with pytest.raises(HTTPException) as error:
        cohort_analytics(analytics_db, provenance="human", actor=SimpleNamespace(role="admin"))
    assert error.value.status_code == 400


def test_cohort_filters_apply_study_sensor_quality_and_inclusive_utc_dates(analytics_db):
    patient_code = f"NXM26003{uuid.uuid4().hex[:5]}"
    analytics_db.add(Patient(
        id=str(uuid.uuid4()), patient_code=patient_code, full_name="Filtered Participant",
        chromosome_marker="X", age_band="M", diet="vegetarian",
    ))
    analytics_db.add_all([
        Study(id="study-a", name="Study A"),
        Study(id="study-b", name="Study B"),
        Session(id="included", study_id="study-a", participant_code=patient_code,
                sensor_type="PIEZO_LDT0_028K", profile_id="p1", status="completed",
                provenance="device", quality_status="VALID_FOR_ANALYSIS", npi_value=72.0, tbr=0.31,
                start_time=datetime.datetime(2026, 3, 10, 23, 30)),
        Session(id="wrong-sensor", study_id="study-a", participant_code=patient_code,
                sensor_type="ADXL345", profile_id="p2", status="completed", provenance="device",
                quality_status="VALID_FOR_ANALYSIS", npi_value=50.0, tbr=0.58,
                start_time=datetime.datetime(2026, 3, 10, 12, 0)),
        Session(id="outside-date", study_id="study-a", participant_code=patient_code,
                sensor_type="PIEZO_LDT0_028K", profile_id="p1", status="completed", provenance="device",
                quality_status="VALID_FOR_ANALYSIS", npi_value=20.0, tbr=0.76,
                start_time=datetime.datetime(2026, 3, 11, 0, 0)),
        Session(id="wrong-study", study_id="study-b", participant_code=patient_code,
                sensor_type="PIEZO_LDT0_028K", profile_id="p1", status="completed", provenance="device",
                quality_status="WARNING", npi_value=30.0, tbr=0.72,
                start_time=datetime.datetime(2026, 3, 10, 9, 0)),
    ])
    analytics_db.commit()

    result = cohort_analytics(
        analytics_db,
        provenance="device",
        study_id="study-a",
        sensor_type="PIEZO_LDT0_028K",
        quality_status="VALID_FOR_ANALYSIS",
        date_from=datetime.date(2026, 3, 10),
        date_to=datetime.date(2026, 3, 10),
        actor=SimpleNamespace(role="admin"),
    )

    assert result["participant_count"] == 1
    assert result["session_count"] == 1
    assert result["completed_session_count"] == 1
    assert result["by_diet"][0]["avg_npi"] == 72.0
    assert result["by_diet"][0]["avg_tbr"] == 0.31
    assert {study["id"] for study in result["filter_options"]["studies"]} == {"study-a", "study-b"}


def test_cohort_filter_rejects_reversed_date_range(analytics_db):
    with pytest.raises(HTTPException) as error:
        cohort_analytics(analytics_db, date_from=datetime.date(2026, 3, 11), date_to=datetime.date(2026, 3, 10), actor=SimpleNamespace(role="admin"))
    assert error.value.status_code == 400


def test_reviewer_does_not_receive_technical_sensor_filter_options(analytics_db):
    reviewer = cohort_analytics(analytics_db, actor=SimpleNamespace(role="reviewer"))
    assert reviewer["filter_options"]["sensor_types"] == []
    with pytest.raises(HTTPException) as error:
        cohort_analytics(analytics_db, sensor_type="PIEZO_LDT0_028K", actor=SimpleNamespace(role="reviewer"))
    assert error.value.status_code == 403
