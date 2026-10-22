import re
from datetime import date
import uuid
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.database import Base
from backend.app.db.schemas import PatientCreate, PatientRetentionUpdate
from backend.app.main import create_patient, lookup_patient, set_patient_retention


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
