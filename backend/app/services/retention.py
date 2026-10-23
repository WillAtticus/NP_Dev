"""Expiry cleanup for local prototype patient records and their recordings."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.orm import Session as DBSession

try:
    from ..db.models import AlgorithmEvaluation, AuditEvent, Patient, Session
    from ..db.timeutils import utcnow_naive
except ImportError:
    from backend.app.db.models import AlgorithmEvaluation, AuditEvent, Patient, Session
    from backend.app.db.timeutils import utcnow_naive


def purge_expired_patient_data(db: DBSession, data_root: str | os.PathLike[str]) -> int:
    """Hard-delete expired patient records and linked raw recording files.

    Active recordings are skipped. File paths are only removed when they resolve
    inside the application's sessions directory.
    """
    now = utcnow_naive()
    expired = (
        db.query(Patient)
        .filter(
            Patient.retain_indefinitely.is_(False),
            Patient.retention_expires_at.is_not(None),
            Patient.retention_expires_at <= now,
        )
        .all()
    )
    if not expired:
        return 0

    sessions_root = (Path(data_root) / "sessions").resolve()
    for patient in expired:
        patient_sessions = (
            db.query(Session)
            .filter(Session.participant_code == patient.patient_code)
            .all()
        )
        for session in patient_sessions:
            if session.status == "recording":
                continue
            if session.raw_data_path:
                raw_path = Path(session.raw_data_path).resolve()
                try:
                    raw_path.relative_to(sessions_root)
                except ValueError:
                    raw_path = None
                if raw_path is not None and raw_path.name in {"raw.h5", "raw.json"}:
                    raw_path.unlink(missing_ok=True)
                    try:
                        raw_path.parent.rmdir()
                    except OSError:
                        pass
            db.query(AuditEvent).filter(AuditEvent.session_id == session.id).delete(synchronize_session=False)
            db.query(AlgorithmEvaluation).filter(AlgorithmEvaluation.session_id == session.id).delete(synchronize_session=False)
            db.delete(session)

        # The patient remains until an active session has finished; a later pass
        # will remove both the completed recording and its profile.
        if any(session.status == "recording" for session in patient_sessions):
            continue
        db.query(AuditEvent).filter(
            AuditEvent.detail.contains(patient.patient_code),
            AuditEvent.action.in_(["patient_created", "patient_retention_updated"]),
        ).delete(synchronize_session=False)
        db.delete(patient)

    db.commit()
    return len(expired)
