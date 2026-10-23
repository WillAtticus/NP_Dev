from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
from fastapi import HTTPException

from backend.app.db.database import Base
from backend.app.db import crud
from backend.app.db.models import AlgorithmEvaluation, AuditEvent, Session
from backend.app.main import FormulaCreateRequest, FormulaEvaluateRequest, FormulaSessionEvaluateRequest, create_formula, evaluate_formula, evaluate_formula_on_session, export_algorithm_evaluations, list_algorithm_evaluations, list_formulas, retire_formula


def test_formula_versions_are_persisted_evaluated_and_retired_not_deleted(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    actor = SimpleNamespace(username="research-test")
    try:
        first = create_formula(FormulaCreateRequest(name="NPI demo", tbr_min=0.4, tbr_max=0.85,
            change_note="Initial experimental version"), db, actor)
        second = create_formula(FormulaCreateRequest(name="NPI demo", tbr_min=0.35, tbr_max=0.9,
            change_note="Explore wider bounds"), db, actor)
        assert first["version"] == 1
        assert second["version"] == 2
        assert second["tbr_min"] == 0.35
        assert len(list_formulas(db, actor)) == 2
        result = retire_formula(second["id"], db, actor)
        assert result["status"] == "retired"
        assert len(list_formulas(db, actor)) == 2
        custom = create_formula(FormulaCreateRequest(name="Custom bounded", expression="clip(100 * tbr, 0, 100)",
            tbr_min=0.4, tbr_max=0.85, change_note="Explore alternate mapping"), db, actor)
        evaluated = evaluate_formula(custom["id"], FormulaEvaluateRequest(tbr=0.6), db, actor)
        assert evaluated["npi_value"] == 60
        assert evaluated["formula_version"] == 1
        assert evaluated["parameter_snapshot"] == {"tbr_min": 0.4, "tbr_max": 0.85}
        assert evaluated["evaluation_id"]
        assert db.query(AuditEvent).filter_by(action="algorithm_formula_evaluated").count() == 1
        no_tbr = evaluate_formula(custom["id"], FormulaEvaluateRequest(tbr=None, quality_status="WARNING"), db, actor)
        assert no_tbr["npi_value"] is None and no_tbr["tbr"] is None
        db.add(Session(id="saved-session", sensor_type="PIEZO_LDT0_028K", profile_id="piezo_butterworth_1_20_default",
            status="completed", provenance="simulated", participant_code="NXI26000001"))
        db.commit()
        monkeypatch.setattr("backend.app.main.analyse_session", lambda req, request, user: {"sensor_type": "PIEZO_LDT0_028K", "profile_id": "piezo_butterworth_1_20_default", "provenance": "simulated", "channel": "raw_counts", "analysis": {
            "tbr": 0.6, "quality_status": "VALID_FOR_ANALYSIS", "quality_flags": [], "sample_count": 8000,
            "sample_rate_hz": 1000,
        }})
        on_session = evaluate_formula_on_session(custom["id"], FormulaSessionEvaluateRequest(session_id="saved-session"), db, actor)
        assert on_session["session_id"] == "saved-session"
        assert on_session["npi_value"] == 60
        assert db.query(AuditEvent).filter_by(action="algorithm_formula_evaluated", session_id="saved-session").count() == 1
        evaluations = list_algorithm_evaluations(limit=100, offset=0, db=db)
        assert len(evaluations) == 3
        assert evaluations[0]["session_id"] == "saved-session"
        assert db.query(AlgorithmEvaluation).count() == 3
        exported = export_algorithm_evaluations(format="csv", db=db, actor=actor)
        assert b"evaluation_id,formula_id,formula_name" in exported.body
        assert b"Custom bounded" in exported.body
        injection_formula = create_formula(FormulaCreateRequest(name="=1+1", tbr_min=0.4, tbr_max=0.85,
            change_note="CSV safety check"), db, actor)
        evaluate_formula(injection_formula["id"], FormulaEvaluateRequest(tbr=0.6), db, actor)
        safe_export = export_algorithm_evaluations(format="csv", db=db, actor=actor)
        assert b"'=1+1" in safe_export.body
        json_export = export_algorithm_evaluations(format="json", db=db, actor=actor)
        assert json_export["count"] == 4
        saved_reanalysis = next(row for row in json_export["evaluations"] if row["session_id"] == "saved-session")
        assert saved_reanalysis["source_metadata"]["sensor_type"] == "PIEZO_LDT0_028K"
        assert crud.soft_delete_session(db, "saved-session") is True
        assert db.query(AlgorithmEvaluation).count() == 3
        with pytest.raises(HTTPException) as blocked:
            create_formula(FormulaCreateRequest(name="Unsafe", expression="__import__('os')", tbr_min=0.4,
                tbr_max=0.85, change_note="Should be rejected"), db, actor)
        assert blocked.value.status_code == 422
    finally:
        db.close()
        engine.dispose()
