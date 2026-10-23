from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.database import Base
from backend.app.db.models import AlgorithmEvaluation, Patient, Session
from backend.app.db.timeutils import utcnow_naive
from backend.app.services.retention import purge_expired_patient_data


def test_expiry_purge_removes_session_linked_algorithm_evaluations(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(Patient(
            id="expired-patient", patient_code="NXI26000001", full_name="Expired",
            chromosome_marker="X", reported_sex="female", age_band="I",
            retain_indefinitely=False, retention_expires_at=utcnow_naive() - timedelta(seconds=1),
        ))
        db.add(Session(
            id="expired-session", participant_code="NXI26000001", sensor_type="PIEZO_LDT0_028K",
            profile_id="piezo_profile", status="completed", provenance="simulated",
        ))
        db.add(AlgorithmEvaluation(
            id="linked-evaluation", formula_id="formula-1", formula_version=1,
            session_id="expired-session", tbr=0.6, quality_status="VALID_FOR_ANALYSIS",
            npi_value=60, parameters_snapshot="{}", source_metadata="{}",
        ))
        db.commit()

        assert purge_expired_patient_data(db, tmp_path) == 1
        assert db.query(Patient).count() == 0
        assert db.query(Session).count() == 0
        assert db.query(AlgorithmEvaluation).count() == 0
    finally:
        db.close()
        engine.dispose()
