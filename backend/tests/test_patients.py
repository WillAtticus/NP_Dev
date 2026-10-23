import re
from datetime import date
import uuid
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.db.database import Base, get_db
from backend.app.db.models import AuditEvent, Session
from backend.app.db.schemas import PatientCreate, PatientRetentionUpdate
from backend.app.main import app, create_patient, current_local_user, export_patient_record, lookup_patient, set_patient_retention


def test_patient_profile_code_lookup_and_admin_retention():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    actor = SimpleNamespace(username="test-admin")
    request = SimpleNamespace(client=SimpleNamespace(host="testclient"))
    try:
        patient = create_patient(PatientCreate(
            full_name=f"Demo Patient {uuid.uuid4().hex[:8]}",
            date_of_birth=date(1990, 10, 22),
            chromosome_marker="X",
            medical_history="Research demo history",
            family_history="Not reported",
            diet="vegetarian",
        ), actor, db)
        assert re.fullmatch(r"NXM\d{7}", patient.patient_code)
        assert patient.chromosome_marker == "X"
        assert patient.age_band == "M"
        assert patient.retain_indefinitely is False
        assert patient.retention_expires_at is not None

        lookup = lookup_patient(patient.patient_code.lower(), request, db)
        assert lookup["patient"].full_name == patient.full_name
        assert lookup["sessions"] == []
        assert "chưa được xác nhận lâm sàng" in lookup["screening_notice"]

        retention = set_patient_retention(patient.patient_code,
                                          PatientRetentionUpdate(retain_indefinitely=True), actor, db)
        assert retention.retain_indefinitely is True
        assert retention.retention_expires_at is None
    finally:
        db.close()
        engine.dispose()


def test_reported_sex_maps_to_patient_code_convention():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    actor = SimpleNamespace(username="test-operator")
    try:
        female = create_patient(PatientCreate(full_name="Female demo", reported_sex="female"), actor, db)
        male = create_patient(PatientCreate(full_name="Male demo", reported_sex="male"), actor, db)
        assert female.patient_code.startswith("NXI")
        assert female.reported_sex == "female" and female.chromosome_marker == "X"
        assert male.patient_code.startswith("NYI")
        assert male.reported_sex == "male" and male.chromosome_marker == "Y"
    finally:
        db.close()
        engine.dispose()


def test_patient_age_band_boundaries():
    from datetime import date
    from backend.app.services.patients import age_band_for

    anchor = date(2026, 10, 21)
    assert age_band_for(None, anchor) == "I"
    assert age_band_for(date(2016, 10, 22), anchor) == "C"
    assert age_band_for(date(2008, 10, 22), anchor) == "J"
    assert age_band_for(date(1996, 10, 22), anchor) == "Y"
    assert age_band_for(date(1976, 10, 22), anchor) == "M"
    assert age_band_for(date(1976, 10, 21), anchor) == "E"


def test_patient_export_contains_only_selected_patient_summaries():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    actor = SimpleNamespace(username="local-patient")
    try:
        first = create_patient(PatientCreate(full_name="First Person", chromosome_marker="X"), actor, db)
        second = create_patient(PatientCreate(full_name="Second Person", chromosome_marker="Y"), actor, db)
        db.add_all([
            Session(id="first-session", participant_code=first.patient_code, sensor_type="PIEZO_LDT0_028K",
                    profile_id="piezo_profile", status="completed", provenance="simulated", duration_sec=9.0,
                    npi_value=82.0, npi_category="experimental_reference_range", quality_status="VALID_FOR_ANALYSIS",
                    notes="internal technical detail", raw_data_path="private/raw.h5"),
            Session(id="second-session", participant_code=second.patient_code, sensor_type="ADXL345",
                    profile_id="adxl_profile", status="completed", provenance="device", duration_sec=10.0,
                    npi_value=20.0, npi_category="outside_experimental_reference_range"),
        ])
        db.commit()
        request = SimpleNamespace(
            client=SimpleNamespace(host="127.0.0.1"),
            headers={"x-neuropulse-patient-code": first.patient_code},
        )

        exported = export_patient_record(first.patient_code, request, actor, db)

        assert exported["patient"]["patient_code"] == first.patient_code
        assert len(exported["sessions"]) == 1
        summary = exported["sessions"][0]
        assert summary["experimental_npi"] == 82.0
        assert summary["data_origin"] == "Dữ liệu mô phỏng"
        assert "raw_counts" not in summary
        assert "profile_id" not in summary
        assert "raw_data_path" not in str(exported)
        assert "internal technical detail" not in str(exported)
        assert db.query(AuditEvent).filter_by(action="patient_personal_data_exported").count() == 1

        original_overrides = app.dependency_overrides.copy()
        def override_db():
            yield db
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[current_local_user] = lambda: SimpleNamespace(
            id="test-patient", username="local-patient", role="patient", is_active=True
        )
        client = TestClient(app)
        try:
            response = client.get(
                f"/api/v1/patients/lookup/{first.patient_code}/export",
                headers={"X-NeuroPulse-Mode": "patient", "X-NeuroPulse-Patient-Code": first.patient_code},
            )
            assert response.status_code == 200
            assert len(response.json()["sessions"]) == 1
            assert "raw sensor samples" in response.json()["export_scope"]

            app.dependency_overrides[current_local_user] = lambda: SimpleNamespace(
                id="test-researcher", username="local-researcher", role="researcher", is_active=True
            )
            denied = client.get(
                f"/api/v1/patients/lookup/{first.patient_code}/export",
                headers={"X-NeuroPulse-Mode": "researcher", "X-NeuroPulse-Patient-Code": first.patient_code},
            )
            assert denied.status_code == 403
        finally:
            client.close()
            app.dependency_overrides.clear()
            app.dependency_overrides.update(original_overrides)

        request.headers["x-neuropulse-patient-code"] = second.patient_code
        with pytest.raises(HTTPException) as mismatch:
            export_patient_record(first.patient_code, request, actor, db)
        assert mismatch.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
