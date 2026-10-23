from datetime import datetime
import json
from typing import Any, Dict, List, Optional, Union
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

try:
    from .models import AlgorithmEvaluation, AuditEvent, Device, Session, Study
    from .timeutils import utcnow_naive
except ImportError:
    try:
        from app.db.models import AlgorithmEvaluation, AuditEvent, Device, Session, Study
        from app.db.timeutils import utcnow_naive
    except ImportError:
        from backend.app.db.models import AlgorithmEvaluation, AuditEvent, Device, Session, Study
        from backend.app.db.timeutils import utcnow_naive


def create_session(
    db: DBSession,
    session_id: str,
    sensor_type: str,
    profile_id: str,
    provenance: str = "simulated",
    participant_code: Optional[str] = None,
    **kwargs: Any,
) -> Session:
    session = db.query(Session).filter(Session.id == session_id).first()
    if session:
        session.sensor_type = sensor_type
        session.profile_id = profile_id
        session.provenance = provenance
        session.participant_code = participant_code
        session.is_deleted = False
        session.status = kwargs.get("status", "created")
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        session.updated_at = utcnow_naive()
        db.commit()
        db.refresh(session)
        return session

    session = Session(
        id=session_id,
        sensor_type=sensor_type,
        profile_id=profile_id,
        provenance=provenance,
        participant_code=participant_code,
        **kwargs,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(
    db: DBSession,
    session_id: str,
    include_deleted: bool = False,
) -> Optional[Session]:
    query = db.query(Session).filter(Session.id == session_id)
    if not include_deleted:
        query = query.filter(Session.is_deleted == False)  # noqa: E712
    return query.first()


def list_sessions(
    db: DBSession,
    limit: int = 50,
    offset: int = 0,
    provenance: Optional[str] = None,
    status: Optional[str] = None,
    include_deleted: bool = False,
) -> List[Session]:
    query = db.query(Session)
    if not include_deleted:
        query = query.filter(Session.is_deleted == False)  # noqa: E712
    if provenance:
        query = query.filter(Session.provenance == provenance)
    if status:
        query = query.filter(Session.status == status)
    return query.order_by(Session.created_at.desc()).offset(offset).limit(limit).all()


def update_session(
    db: DBSession,
    session_id: str,
    **kwargs: Any,
) -> Optional[Session]:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        return None
    for key, value in kwargs.items():
        if hasattr(session, key):
            if key in ("start_time", "end_time") and isinstance(value, str):
                try:
                    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except Exception:
                    pass
            setattr(session, key, value)
    session.updated_at = utcnow_naive()
    db.commit()
    db.refresh(session)
    return session


def soft_delete_session(
    db: DBSession,
    session_id: str,
) -> bool:
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        return False
    # Evaluation results cannot remain linked to a session after its deletion.
    db.query(AlgorithmEvaluation).filter(AlgorithmEvaluation.session_id == session_id).delete(synchronize_session=False)
    session.is_deleted = True
    session.updated_at = utcnow_naive()
    db.commit()
    return True


def create_audit_event(
    db: DBSession,
    action: str,
    session_id: Optional[str] = None,
    actor: str = "operator",
    detail: Optional[Union[str, Dict[str, Any], List[Any]]] = None,
) -> AuditEvent:
    if isinstance(detail, (dict, list)):
        detail_str = json.dumps(detail)
    else:
        detail_str = detail
    event = AuditEvent(
        action=action,
        actor=actor,
        session_id=session_id,
        detail=detail_str,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_session_count(
    db: DBSession,
    include_deleted: bool = False,
) -> int:
    query = db.query(func.count(Session.id))
    if not include_deleted:
        query = query.filter(Session.is_deleted == False)  # noqa: E712
    return query.scalar() or 0


def get_session_stats(
    db: DBSession,
    include_deleted: bool = False,
) -> Dict[str, Any]:
    status_query = db.query(Session.status, func.count(Session.id))
    if not include_deleted:
        status_query = status_query.filter(Session.is_deleted == False)  # noqa: E712
    status_rows = status_query.group_by(Session.status).all()
    count_by_status = {status: count for status, count in status_rows if status is not None}

    provenance_query = db.query(Session.provenance, func.count(Session.id))
    sensor_query = db.query(Session.sensor_type, func.count(Session.id))
    if not include_deleted:
        provenance_query = provenance_query.filter(Session.is_deleted == False)  # noqa: E712
        sensor_query = sensor_query.filter(Session.is_deleted == False)  # noqa: E712
    provenance_rows = provenance_query.group_by(Session.provenance).all()
    sensor_rows = sensor_query.group_by(Session.sensor_type).all()
    metric_query = db.query(
        Session.sensor_type,
        Session.profile_id,
        func.avg(Session.tbr),
        func.avg(Session.npi_value),
    )
    if not include_deleted:
        metric_query = metric_query.filter(Session.is_deleted == False)  # noqa: E712
    metric_rows = metric_query.group_by(Session.sensor_type, Session.profile_id).all()

    valid_query = db.query(func.count(Session.id)).filter(Session.quality_status == "VALID_FOR_ANALYSIS")
    if not include_deleted:
        valid_query = valid_query.filter(Session.is_deleted == False)
    valid_quality_count = valid_query.scalar() or 0

    total = sum(count_by_status.values())
    return {
        "count_by_status": count_by_status,
        "count_by_provenance": {key: count for key, count in provenance_rows if key is not None},
        "count_by_sensor": {key: count for key, count in sensor_rows if key is not None},
        "metric_means_by_sensor_profile": {
            f"{sensor_type}|{profile_id}": {
                "avg_tbr": float(avg_tbr) if avg_tbr is not None else None,
                "avg_npi": float(avg_npi) if avg_npi is not None else None,
            }
            for sensor_type, profile_id, avg_tbr, avg_npi in metric_rows
            if sensor_type is not None and profile_id is not None
        },
        "total_count": total,
        "total": total,
        "valid_quality": valid_quality_count,
    }


def create_device(
    db: DBSession,
    device_id: str,
    sensor_type: str,
    serial_port: Optional[str] = None,
    baud_rate: int = 115200,
    firmware_version: Optional[str] = None,
    protocol_version: Optional[str] = None,
    is_simulator: bool = True,
) -> Device:
    device = Device(
        id=device_id,
        sensor_type=sensor_type,
        serial_port=serial_port,
        baud_rate=baud_rate,
        firmware_version=firmware_version,
        protocol_version=protocol_version,
        is_simulator=is_simulator,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def get_device(db: DBSession, device_id: str) -> Optional[Device]:
    return db.query(Device).filter(Device.id == device_id).first()


def list_devices(db: DBSession) -> List[Device]:
    return db.query(Device).all()


def create_study(
    db: DBSession,
    name: str,
    study_id: Optional[str] = None,
    protocol_version: str = "1.0.0",
    description: Optional[str] = None,
    sensor_type: str = "PIEZO_LDT0_028K",
    target_duration_sec: float = 8.0,
    tbr_min: float = 0.40,
    tbr_max: float = 0.85,
) -> Study:
    if not study_id:
        import uuid
        study_id = f"study-{uuid.uuid4().hex[:8]}"
    existing = db.query(Study).filter(Study.id == study_id).first()
    if existing:
        return existing
    study = Study(
        id=study_id,
        name=name,
        protocol_version=protocol_version,
        description=description,
        sensor_type=sensor_type,
        target_duration_sec=target_duration_sec,
        tbr_min=tbr_min,
        tbr_max=tbr_max,
    )
    db.add(study)
    db.commit()
    db.refresh(study)
    return study


def get_study(db: DBSession, study_id: str) -> Optional[Study]:
    return db.query(Study).filter(Study.id == study_id).first()


def list_studies(db: DBSession) -> List[Study]:
    return db.query(Study).all()
