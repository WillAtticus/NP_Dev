"""
FastAPI Backend — NeuroPulse MVP Local Server
Binds exclusively to 127.0.0.1; CORS restricted to localhost frontend origin.
"""
from __future__ import annotations

import os
import sys
import uuid
import json
import re
import asyncio
import ipaddress
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional

import datetime
import time
import hashlib
import logging
import numpy as np
from sqlalchemy import func
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Header, Request
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

# ── Path bootstrap so project root and shared/ are importable ────────────────
_proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

try:
    from backend.app.db.database import get_db, init_db, SessionLocal
    from backend.app.db import crud
    from backend.app.db.models import AuthSession, LocalUser, Patient, Session
    from backend.app.db.timeutils import utcnow_naive
    from backend.app.db.schemas import (SessionCreate, SessionUpdate, SessionResponse, StudyCreate, StudyResponse,
                                        PatientCreate, PatientResponse, PatientRetentionUpdate)
except ImportError:
    from app.db.database import get_db, init_db, SessionLocal
    from app.db import crud
    from app.db.models import AuthSession, LocalUser, Patient, Session
    from app.db.timeutils import utcnow_naive
    from app.db.schemas import (SessionCreate, SessionUpdate, SessionResponse, StudyCreate, StudyResponse,
                                PatientCreate, PatientResponse, PatientRetentionUpdate)

try:
    from app.services.acquisition.manager import AcquisitionManager
    from app.services.processing.engine import (
        BUILTIN_PROFILES,
        run_pipeline,
        process_session_data,
    )
    from app.services.algorithms.npi import (
        AlgorithmRegistry,
        run_npi,
    )
except ImportError:
    from backend.app.services.acquisition.manager import AcquisitionManager
    from backend.app.services.processing.engine import (
        BUILTIN_PROFILES,
        run_pipeline,
        process_session_data,
    )
    from backend.app.services.algorithms.npi import (
        AlgorithmRegistry,
        run_npi,
    )

try:
    from app.services.auth import ROLES, hash_password, verify_password, issue_session, resolve_session, revoke_session
    from app.services.patients import age_band_for, generate_patient_code
    from app.services.retention import purge_expired_patient_data
except ImportError:
    from backend.app.services.auth import ROLES, hash_password, verify_password, issue_session, resolve_session, revoke_session
    from backend.app.services.patients import age_band_for, generate_patient_code
    from backend.app.services.retention import purge_expired_patient_data

# ─────────────────────────────────────────────────────────────────────────────
# Singleton acquisition manager
# ─────────────────────────────────────────────────────────────────────────────
DATA_ROOT = os.environ.get("DATA_DIR", "./data")
acq = AcquisitionManager(data_root=DATA_ROOT)


def _session_data_dir(session_id: str) -> str:
    """Resolve a safe session directory without allowing path traversal."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID.")
    sessions_root = os.path.abspath(os.path.join(DATA_ROOT, "sessions"))
    session_dir = os.path.abspath(os.path.join(sessions_root, session_id))
    if os.path.commonpath((sessions_root, session_dir)) != sessions_root:
        raise HTTPException(status_code=400, detail="Invalid session ID.")
    return session_dir

# Active WebSocket connections for live-stream broadcast
_ws_clients: List[WebSocket] = []


async def _broadcast(event: Dict[str, Any]):
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


def _on_sample_batch(event: Dict[str, Any]):
    """Sync callback from AcquisitionManager → schedule async broadcast."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_broadcast(event))
    except Exception:
        pass


acq.listeners.append(_on_sample_batch)


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables if not exist
    cleanup_task = asyncio.create_task(_retention_cleanup_loop())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await acq.disconnect_async()


def _purge_expired_records() -> int:
    db = SessionLocal()
    try:
        return purge_expired_patient_data(db, DATA_ROOT)
    finally:
        db.close()


async def _retention_cleanup_loop() -> None:
    """Purge expired local patient data at startup and then hourly."""
    while True:
        try:
            removed = await asyncio.to_thread(_purge_expired_records)
            if removed:
                logging.getLogger(__name__).info("Retention cleanup removed %s expired patient records", removed)
        except Exception:
            logging.getLogger(__name__).exception("Patient retention cleanup failed")
        await asyncio.sleep(3600)


app = FastAPI(
    title="NeuroPulse Research Platform API",
    description=(
        "Local-first research signal processing API.\n\n"
        "⚠ NOT A MEDICAL DIAGNOSTIC TOOL. For research use only."
    ),
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8501",   # Streamlit
        "http://127.0.0.1:8501",
        "neuropulse://app",      # Packaged Windows desktop shell
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────
class ConnectRequest(BaseModel):
    port: str = "SIMULATOR"
    baud_rate: Literal[115200] = 115200
    sensor_type: str = "PIEZO_LDT0_028K"
    simulator_profile: Literal["healthy", "volatile"] = "healthy"


class StartAcquisitionRequest(BaseModel):
    session_id: Optional[str] = None
    sensor_type: str = "PIEZO_LDT0_028K"
    profile_id: str = "piezo_butterworth_1_20_default"
    channel: Optional[str] = None
    participant_code: Optional[str] = None
    study_id: Optional[str] = None


class RunAnalysisRequest(BaseModel):
    session_id: str
    profile_id: str = "piezo_butterworth_1_20_default"
    channel: Optional[str] = None


class RunNPIRequest(BaseModel):
    tbr: float
    quality_status: str = "VALID_FOR_ANALYSIS"
    tbr_min: float = 0.40
    tbr_max: float = 0.85


class SimulateAndAnalyseRequest(BaseModel):
    sensor_type: str = "PIEZO_LDT0_028K"
    profile_id: str = "piezo_butterworth_1_20_default"
    tremor_freq_hz: float = Field(default=5.0, ge=0.5, le=25.0)
    tremor_amp: float = Field(default=250.0, ge=0.0, le=2000.0)
    noise_amp: float = Field(default=25.0, ge=0.0)
    duration_sec: float = Field(default=8.0, ge=2.0, le=120.0)


class BenchmarkImportRequest(BaseModel):
    name: str = "BENCHMARK_DATASET"
    sensor_type: str = "PIEZO_LDT0_028K"
    profile_id: str = "piezo_butterworth_1_20_default"
    sample_rate_hz: float = Field(default=1000.0, gt=0, allow_inf_nan=False)
    channel_name: str = "raw_counts"
    samples: List[float]
    participant_code: Optional[str] = "BENCHMARK_SUBJECT"
    notes: Optional[str] = "Imported research benchmark dataset"


class BootstrapRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=12, max_length=256)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class LocalUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: str


class LocalUserActiveUpdate(BaseModel):
    is_active: bool


class LocalPasswordUpdate(BaseModel):
    password: str = Field(min_length=12, max_length=256)


def ensure_local_client(host: Optional[str]):
    if host == "testclient":
        return
    try:
        if host and ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise HTTPException(status_code=403, detail="NeuroPulse local API only accepts loopback connections.")


def current_local_user(request: Request, authorization: Optional[str] = Header(default=None),
                       db: DBSession = Depends(get_db)) -> LocalUser:
    ensure_local_client(request.client.host if request.client else None)
    # The Windows research prototype uses an operation mode on the local workstation,
    # not an account sign-in. This is intentionally not an identity/security boundary.
    requested_mode = request.headers.get("x-neuropulse-mode")
    mode = requested_mode.strip().lower() if requested_mode else ""
    if mode in {"admin", "operator", "researcher", "reviewer", "kiosk", "patient"}:
        return LocalUser(id=f"local-mode-{mode}", username=f"local-{mode}",
                         password_hash="", role=mode, is_active=True)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.", headers={"WWW-Authenticate": "Bearer"})
    user = resolve_session(db, authorization[7:].strip())
    if not user:
        raise HTTPException(status_code=401, detail="Session is invalid or expired.", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_roles(*roles: str):
    def dependency(user: LocalUser = Depends(current_local_user)) -> LocalUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="This local account does not have permission for this operation.")
        return user
    return dependency


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/health", tags=["System"])
def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "disclaimer": "RESEARCH / EXPERIMENTAL — NOT FOR DIAGNOSIS",
    }


@app.get("/api/v1/auth/status", tags=["Authentication"])
def auth_status(request: Request, db: DBSession = Depends(get_db)):
    ensure_local_client(request.client.host if request.client else None)
    return {"bootstrap_required": db.query(LocalUser).count() == 0}


@app.post("/api/v1/auth/bootstrap", tags=["Authentication"])
def bootstrap_admin(req: BootstrapRequest, request: Request, db: DBSession = Depends(get_db)):
    ensure_local_client(request.client.host if request.client else None)
    if db.query(LocalUser).count() != 0:
        raise HTTPException(status_code=409, detail="Initial administrator has already been created.")
    user = LocalUser(id=str(uuid.uuid4()), username=req.username.strip().lower(),
                     password_hash=hash_password(req.password), role="admin", is_active=True)
    db.add(user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="Administrator setup was already completed.")
    crud.create_audit_event(db, action="auth_admin_bootstrapped", actor=user.username)
    token, auth_session = issue_session(db, user)
    return {"access_token": token, "token_type": "bearer", "expires_at": auth_session.expires_at.isoformat(),
            "user": {"id": user.id, "username": user.username, "role": user.role}}


@app.post("/api/v1/auth/login", tags=["Authentication"])
def login(req: LoginRequest, request: Request, db: DBSession = Depends(get_db)):
    ensure_local_client(request.client.host if request.client else None)
    user = db.query(LocalUser).filter(LocalUser.username == req.username.strip().lower()).first()
    if not user or not user.is_active or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.", headers={"WWW-Authenticate": "Bearer"})
    token, auth_session = issue_session(db, user)
    crud.create_audit_event(db, action="auth_login", actor=user.username)
    return {"access_token": token, "token_type": "bearer", "expires_at": auth_session.expires_at.isoformat(),
            "user": {"id": user.id, "username": user.username, "role": user.role}}


@app.get("/api/v1/auth/me", tags=["Authentication"])
def auth_me(user: LocalUser = Depends(current_local_user)):
    return {"id": user.id, "username": user.username, "role": user.role}


@app.post("/api/v1/auth/logout", tags=["Authentication"])
def logout(authorization: Optional[str] = Header(default=None), user: LocalUser = Depends(current_local_user),
           db: DBSession = Depends(get_db)):
    token = authorization[7:].strip()
    revoke_session(db, token)
    crud.create_audit_event(db, action="auth_logout", actor=user.username)
    return {"status": "logged_out"}


@app.get("/api/v1/auth/users", tags=["Authentication"])
def list_local_users(_: LocalUser = Depends(require_roles("admin")), db: DBSession = Depends(get_db)):
    return [{"id": u.id, "username": u.username, "role": u.role, "is_active": u.is_active,
             "created_at": u.created_at.isoformat() if u.created_at else None}
            for u in db.query(LocalUser).order_by(LocalUser.username).all()]


@app.post("/api/v1/auth/users", tags=["Authentication"])
def create_local_user(req: LocalUserCreate, actor: LocalUser = Depends(require_roles("admin")),
                      db: DBSession = Depends(get_db)):
    username = req.username.strip().lower()
    if req.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(sorted(ROLES))}.")
    if db.query(LocalUser).filter(LocalUser.username == username).first():
        raise HTTPException(status_code=409, detail="Username already exists.")
    user = LocalUser(id=str(uuid.uuid4()), username=username, password_hash=hash_password(req.password),
                     role=req.role, is_active=True)
    db.add(user)
    db.commit()
    crud.create_audit_event(db, action="auth_user_created", actor=actor.username,
                             detail={"username": username, "role": req.role})
    return {"id": user.id, "username": user.username, "role": user.role, "is_active": user.is_active}


@app.patch("/api/v1/auth/users/{user_id}/active", tags=["Authentication"])
def set_local_user_active(user_id: str, req: LocalUserActiveUpdate,
                          actor: LocalUser = Depends(require_roles("admin")), db: DBSession = Depends(get_db)):
    user = db.query(LocalUser).filter(LocalUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Local user not found.")
    if user.id == actor.id and not req.is_active:
        raise HTTPException(status_code=400, detail="The active administrator cannot disable their own account.")
    if user.role == "admin" and user.is_active and not req.is_active:
        admins = db.query(LocalUser).filter(LocalUser.role == "admin", LocalUser.is_active.is_(True)).count()
        if admins <= 1:
            raise HTTPException(status_code=400, detail="At least one active administrator must remain.")
    user.is_active = req.is_active
    if not req.is_active:
        db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).update(
            {AuthSession.revoked_at: utcnow_naive()}, synchronize_session=False)
    db.commit()
    crud.create_audit_event(db, action="auth_user_activation_changed", actor=actor.username,
                             detail={"username": user.username, "is_active": user.is_active})
    return {"id": user.id, "username": user.username, "role": user.role, "is_active": user.is_active}


@app.put("/api/v1/auth/users/{user_id}/password", tags=["Authentication"])
def reset_local_user_password(user_id: str, req: LocalPasswordUpdate,
                              actor: LocalUser = Depends(require_roles("admin")), db: DBSession = Depends(get_db)):
    user = db.query(LocalUser).filter(LocalUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Local user not found.")
    user.password_hash = hash_password(req.password)
    db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).update(
        {AuthSession.revoked_at: utcnow_naive()}, synchronize_session=False)
    db.commit()
    crud.create_audit_event(db, action="auth_user_password_reset", actor=actor.username,
                             detail={"username": user.username})
    return {"status": "password_updated"}


# ── Device & Connection ───────────────────────────────────────────────────────

@app.get("/api/v1/devices/ports", tags=["Device"])
def list_ports(_: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer"))):
    return acq.get_available_ports()


@app.post("/api/v1/devices/connect", tags=["Device"])
def connect(req: ConnectRequest, _: LocalUser = Depends(require_roles("admin", "operator"))):
    try:
        result = acq.connect(
            port=req.port, baud_rate=req.baud_rate, sensor_type=req.sensor_type,
            simulator_profile=req.simulator_profile,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/devices/disconnect", tags=["Device"])
async def disconnect(_: LocalUser = Depends(require_roles("admin", "operator"))):
    return await acq.disconnect_async()


@app.get("/api/v1/devices/status", tags=["Device"])
def device_status(_: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer", "patient"))):
    return acq.get_status()


# ── Acquisition ───────────────────────────────────────────────────────────────

@app.post("/api/v1/acquisition/start", tags=["Acquisition"])
async def start_acquisition(req: StartAcquisitionRequest, request: Request, actor: LocalUser = Depends(require_roles("admin", "operator", "patient"))):
    if actor.role == "patient":
        code = (request.headers.get("x-neuropulse-patient-code") or "").strip().upper()
        if not code or code != (req.participant_code or "").strip().upper():
            raise HTTPException(status_code=403, detail="Mã hồ sơ phiên đo không khớp mã đang chọn.")
        db = next(get_db())
        try:
            if not db.query(Patient).filter(Patient.patient_code == code).first():
                raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ theo mã bệnh nhân.")
        finally:
            db.close()
    session_id = req.session_id or str(uuid.uuid4())
    if req.profile_id not in BUILTIN_PROFILES:
        raise HTTPException(status_code=400, detail=f"Profile '{req.profile_id}' not found.")
    profile = BUILTIN_PROFILES[req.profile_id]
    if profile.get("sensor_type") != req.sensor_type:
        raise HTTPException(status_code=400, detail="Processing profile sensor type does not match the requested sensor.")
    if req.sensor_type == "ADXL345" and req.channel not in {"x_counts", "y_counts", "z_counts", "x", "y", "z", "mag"}:
        raise HTTPException(status_code=400, detail="Choose an ADXL345 axis channel explicitly: x, y, z, or mag.")
    db = next(get_db())
    if crud.get_session(db, session_id):
        db.close()
        raise HTTPException(status_code=409, detail="Session ID already exists.")
    db.close()
    try:
        result = acq.start_acquisition(session_id=session_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    status = acq.get_status()
    if status.get("sensor_type") != req.sensor_type:
        await acq.stop_acquisition_async()
        raise HTTPException(status_code=400, detail="Connected device sensor type does not match the requested session.")
    db = next(get_db())
    try:
        started_at = utcnow_naive()
        crud.create_session(
            db, session_id=session_id, sensor_type=req.sensor_type,
            profile_id=req.profile_id,
            provenance="simulated" if status.get("is_simulated") else "device",
            participant_code=req.participant_code, study_id=req.study_id,
            status="recording", start_time=started_at,
            sample_rate_hz=status.get("effective_sample_rate"),
            notes=(f"Kịch bản mô phỏng: {status.get('simulator_profile')} — dữ liệu tổng hợp"
                   if status.get("is_simulated") else None),
        )
        acq.analysis_channel = req.channel
        crud.create_audit_event(db, action="session_started", session_id=session_id, actor=actor.username)
    except HTTPException:
        raise
    except Exception as exc:
        await acq.stop_acquisition_async()
        raise HTTPException(status_code=500, detail=f"Could not create session record: {exc}")
    finally:
        db.close()
    result.update({"session_id": session_id, "status": "streaming_started"})
    return result


@app.post("/api/v1/acquisition/stop", tags=["Acquisition"])
async def stop_acquisition(request: Request, actor: LocalUser = Depends(require_roles("admin", "operator", "patient"))):
    if actor.role == "patient":
        code = (request.headers.get("x-neuropulse-patient-code") or "").strip().upper()
        db = next(get_db())
        try:
            active = db.query(Session).filter(Session.id == acq.active_session_id).first()
            if not code or not active or active.participant_code != code:
                raise HTTPException(status_code=403, detail="Phiên đang chạy không thuộc mã hồ sơ đang chọn.")
        finally:
            db.close()
    result = await acq.stop_acquisition_async()
    saved = result.get("saved_recording")
    if saved:
        db = next(get_db())
        try:
            session_id = saved.get("session_id") or acq.last_saved_session_id
            session = crud.get_session(db, session_id) if session_id else None
            if session:
                ended_at = utcnow_naive()
                started_at = session.start_time or ended_at
                patch = {
                    "status": "completed", "end_time": ended_at,
                    "duration_sec": max(0.0, (ended_at - started_at).total_seconds()),
                    "sample_count": saved.get("total_samples"),
                    "sample_rate_hz": saved.get("sample_rate_hz") or session.sample_rate_hz,
                    "sha256_hash": saved.get("sha256"),
                    "raw_data_path": saved.get("file_path"),
                    "quality_status": "ANALYSIS_PENDING",
                }
                crud.update_session(db, session_id, **patch)
                crud.create_audit_event(db, action="session_stopped", session_id=session_id, actor=actor.username,
                                         detail={"sha256": saved.get("sha256"), "sample_count": saved.get("total_samples")})
                channel = getattr(acq, "analysis_channel", None)
                try:
                    analysis = analyse_session(RunAnalysisRequest(
                        session_id=session_id, profile_id=session.profile_id, channel=channel
                    ))
                    metrics = analysis.get("analysis", {})
                    npi = metrics.get("npi") or {}
                    crud.update_session(db, session_id,
                        tbr=metrics.get("tbr"), npi_value=npi.get("npi_value"),
                        npi_category=npi.get("category"),
                        quality_status=metrics.get("quality_status"),
                        quality_flags=json.dumps(metrics.get("quality_flags", [])),
                        dominant_freq_hz=metrics.get("dominant_freq_hz"),
                    )
                    result["analysis"] = analysis.get("analysis")
                except Exception as exc:
                    crud.update_session(db, session_id, quality_status="ANALYSIS_FAILED",
                                        quality_flags=json.dumps(["POST_STOP_ANALYSIS_FAILED"]))
                    result["finalization_error"] = f"Raw recording was saved and linked, but analysis failed: {exc}"
                result["session"] = SessionResponse.model_validate(crud.get_session(db, session_id)).model_dump(mode="json")
        except HTTPException as exc:
            result["finalization_error"] = exc.detail
        except Exception as exc:
            result["finalization_error"] = str(exc)
        finally:
            db.close()
    return result


@app.get("/api/v1/acquisition/status", tags=["Acquisition"])
def acquisition_status(_: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer", "patient"))):
    return acq.get_status()


@app.get("/api/v1/acquisition/live-buffer", tags=["Acquisition"])
def live_buffer(request: Request, channel: str = "raw_counts", max_samples: int = 1000,
                user: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer", "patient"))):
    if user.role == "patient":
        code = (request.headers.get("x-neuropulse-patient-code") if request else "") or ""
        db = next(get_db())
        try:
            active = db.query(Session).filter(Session.id == acq.active_session_id).first()
            if not code or not active or active.participant_code != code.strip().upper():
                raise HTTPException(status_code=403, detail="Không có luồng live cho mã hồ sơ này.")
        finally:
            db.close()
    buf = acq.live_channels.get(channel, None)
    if buf is None:
        raise HTTPException(status_code=404, detail=f"Channel '{channel}' not in live buffer.")
    samples = list(buf)[-max_samples:]
    return {
        "channel": channel,
        "samples": samples,
        "count": len(samples),
        "is_simulated": acq.is_simulated,
        "sensor_type": acq.selected_sensor,
    }


# ── Signal Analysis ───────────────────────────────────────────────────────────

@app.get("/api/v1/processing/profiles", tags=["Processing"])
def list_profiles(_: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer"))):
    return [
        {
            "profile_id": pid,
            "sensor_type": p["sensor_type"],
            "bandpass": p["bandpass"],
            "bands": p["bands"],
            "profile_version": p["profile_version"],
        }
        for pid, p in BUILTIN_PROFILES.items()
    ]


@app.post("/api/v1/processing/analyse", tags=["Processing"])
def analyse_session(req: RunAnalysisRequest, request: Request, user: LocalUser = Depends(require_roles("admin", "operator", "researcher", "patient"))):
    """Run signal processing pipeline on a stored session's raw data."""
    if user.role == "patient":
        code = (request.headers.get("x-neuropulse-patient-code") or "").strip().upper()
        db = next(get_db())
        try:
            session = crud.get_session(db, req.session_id)
            if not code or not session or session.participant_code != code:
                raise HTTPException(status_code=403, detail="Phiên không thuộc mã hồ sơ đang chọn.")
        finally:
            db.close()
    if req.profile_id not in BUILTIN_PROFILES:
        raise HTTPException(status_code=400, detail=f"Profile '{req.profile_id}' not found.")

    profile = BUILTIN_PROFILES[req.profile_id]
    session_dir = _session_data_dir(req.session_id)
    raw_h5_path = os.path.join(session_dir, "raw.h5")
    raw_json_path = os.path.join(session_dir, "raw.json")

    sensor_type = None
    provenance = None
    channel_data = None
    sample_rate_hz = None
    selected_channel = req.channel

    if os.path.exists(raw_h5_path):
        try:
            import h5py
            with h5py.File(raw_h5_path, "r") as h5f:
                sensor_type = str(h5f.attrs.get("sensor_type", ""))
                provenance = str(h5f.attrs.get("provenance", ""))
                sample_rate_hz = float(h5f.attrs.get("sample_rate_hz", 0)) or None
                if selected_channel is None and sensor_type == "PIEZO_LDT0_028K":
                    selected_channel = "raw_counts"
                if selected_channel is None and sensor_type == "ADXL345":
                    raise HTTPException(status_code=400, detail="Choose an ADXL345 axis channel explicitly: x, y, or z.")
                if "channels" in h5f and selected_channel in h5f["channels"]:
                    channel_data = h5f["channels"][selected_channel][:]
        except Exception:
            channel_data = None

    if channel_data is None:
        if not os.path.exists(raw_json_path):
            raise HTTPException(status_code=404, detail=f"Session '{req.session_id}' not found.")
        with open(raw_json_path, "r") as f:
            session_data = json.load(f)
        sensor_type = session_data.get("sensor_type")
        provenance = session_data.get("provenance")
        sample_rate_hz = float(session_data.get("sample_rate_hz") or 0) or None
        channels = session_data.get("channels", {})
        if selected_channel is None and sensor_type == "PIEZO_LDT0_028K":
            selected_channel = "raw_counts"
        if selected_channel is None and sensor_type == "ADXL345":
            raise HTTPException(status_code=400, detail="Choose an ADXL345 axis channel explicitly: x, y, or z.")
        channel_data = channels.get(selected_channel)
        if channel_data is None:
            raise HTTPException(status_code=404, detail=f"Channel '{selected_channel}' not found in session.")

    if profile.get("sensor_type") != sensor_type:
        raise HTTPException(status_code=400, detail="Processing profile sensor type does not match the stored session.")
    if sample_rate_hz:
        profile = {**profile, "sample_rate_hz": sample_rate_hz}
    if sensor_type == "PIEZO_LDT0_028K" and selected_channel != "raw_counts":
        raise HTTPException(status_code=400, detail="Piezo analysis requires the raw_counts channel.")
    if sensor_type == "ADXL345" and selected_channel not in {"x_counts", "y_counts", "z_counts", "x", "y", "z", "mag"}:
        raise HTTPException(status_code=400, detail="Choose an available ADXL345 axis channel explicitly.")

    arr = np.asarray(channel_data, dtype=np.float64)
    result = run_pipeline(arr, profile)

    # Compute NPI if TBR is available
    npi_result = run_npi(result.get("tbr"), quality_status=result.get("quality_status", "VALID_FOR_ANALYSIS"))
    result["npi"] = npi_result

    return {
        "session_id": req.session_id,
        "channel": selected_channel,
        "profile_id": req.profile_id,
        "sensor_type": sensor_type,
        "provenance": provenance,
        "analysis": result,
        "disclaimer": "RESEARCH / EXPERIMENTAL — NOT FOR DIAGNOSIS",
    }


@app.post("/api/v1/simulate-and-analyse", tags=["Processing"])
def simulate_and_analyse(req: SimulateAndAnalyseRequest, _: LocalUser = Depends(require_roles("admin", "researcher"))):
    """
    One-shot: generate synthetic data, run full pipeline, return NPI result.
    Useful for Algorithm Lab and Streamlit dashboard.
    """

    if req.profile_id not in BUILTIN_PROFILES:
        raise HTTPException(status_code=400, detail=f"Profile '{req.profile_id}' not found.")

    profile = BUILTIN_PROFILES[req.profile_id]
    fs = profile["sample_rate_hz"]
    total = int(req.duration_sec * fs)
    t = np.linspace(0, req.duration_sec, total, endpoint=False)

    # Generate synthetic signal
    signal_arr = (
        req.tremor_amp * np.sin(2 * np.pi * req.tremor_freq_hz * t)
        + 40.0 * np.sin(2 * np.pi * 0.3 * t)
        + np.random.normal(0, req.noise_amp, total)
    )

    if req.sensor_type == "PIEZO_LDT0_028K":
        raw = np.clip(2048.0 + signal_arr, 0, 4095)
    else:
        raw = signal_arr

    result = run_pipeline(raw, profile)
    npi_result = run_npi(result.get("tbr"), quality_status=result.get("quality_status"))
    result["npi"] = npi_result

    return {
        "sensor_type": req.sensor_type,
        "profile_id":  req.profile_id,
        "provenance":  "simulated",
        "input_params": req.model_dump(),
        "analysis":    result,
        "disclaimer":  "RESEARCH / EXPERIMENTAL — NOT FOR DIAGNOSIS",
    }


# ── Algorithm Lab ─────────────────────────────────────────────────────────────

@app.get("/api/v1/algorithms", tags=["Algorithm Lab"])
def list_algorithms(_: LocalUser = Depends(require_roles("admin", "researcher"))):
    return AlgorithmRegistry.list_all()


@app.post("/api/v1/algorithms/npi/compute", tags=["Algorithm Lab"])
def compute_npi(req: RunNPIRequest, _: LocalUser = Depends(require_roles("admin", "researcher"))):
    result = run_npi(
        tbr=req.tbr,
        parameters={"tbr_min": req.tbr_min, "tbr_max": req.tbr_max},
        quality_status=req.quality_status,
    )
    return result


# ── Session Management ───────────────────────────────────────────────────────

@app.post("/api/v1/patients", tags=["Patients"])
def create_patient(req: PatientCreate, actor: LocalUser = Depends(require_roles("admin", "operator", "researcher", "patient")),
                   db: DBSession = Depends(get_db)):
    first_measurement_date = datetime.date.today()
    try:
        age_band = age_band_for(req.date_of_birth, first_measurement_date)
        patient_code = generate_patient_code(db, req.chromosome_marker, age_band, first_measurement_date)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    created_at = utcnow_naive()
    patient = Patient(
        id=str(uuid.uuid4()), patient_code=patient_code, full_name=req.full_name.strip(),
        date_of_birth=req.date_of_birth, chromosome_marker=req.chromosome_marker,
        age_band=age_band, medical_history=req.medical_history, family_history=req.family_history,
        diet=req.diet, retain_indefinitely=False,
        retention_expires_at=created_at + datetime.timedelta(days=21),
        created_at=created_at, updated_at=created_at,
    )
    db.add(patient)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Patient code collision; retry profile creation.") from exc
    db.refresh(patient)
    crud.create_audit_event(db, action="patient_created", actor=actor.username,
                             detail={"patient_code": patient.patient_code})
    return PatientResponse.model_validate(patient)


@app.get("/api/v1/patients", tags=["Patients"])
def list_patients(db: DBSession = Depends(get_db),
                  _: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer"))):
    patients = db.query(Patient).order_by(Patient.created_at.desc()).all()
    return [PatientResponse.model_validate(patient) for patient in patients]


@app.get("/api/v1/patients/lookup/{patient_code}", tags=["Patients"])
def lookup_patient(patient_code: str, request: Request, db: DBSession = Depends(get_db)):
    # Prototype flow: patient code is the lookup credential on the local machine.
    ensure_local_client(request.client.host if request.client else None)
    code = patient_code.strip().upper()
    patient = db.query(Patient).filter(Patient.patient_code == code).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ theo mã bệnh nhân.")
    sessions = (db.query(Session).filter(Session.participant_code == code, Session.is_deleted.is_(False))
                .order_by(Session.created_at.desc()).all())
    return {
        "patient": PatientResponse.model_validate(patient),
        "sessions": [SessionResponse.model_validate(session) for session in sessions],
        "screening_notice": "Các dải NPI là giả thuyết demo thử nghiệm, chưa được xác nhận lâm sàng.",
    }


@app.patch("/api/v1/patients/{patient_code}/retention", tags=["Patients"])
def set_patient_retention(patient_code: str, req: PatientRetentionUpdate,
                          actor: LocalUser = Depends(require_roles("admin")), db: DBSession = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.patient_code == patient_code.upper()).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")
    patient.retain_indefinitely = req.retain_indefinitely
    patient.retention_expires_at = None if req.retain_indefinitely else utcnow_naive() + datetime.timedelta(days=21)
    patient.updated_at = utcnow_naive()
    db.commit()
    db.refresh(patient)
    crud.create_audit_event(db, action="patient_retention_updated", actor=actor.username,
                             detail={"patient_code": patient.patient_code,
                                     "retain_indefinitely": patient.retain_indefinitely})
    return PatientResponse.model_validate(patient)

@app.post("/api/v1/sessions", response_model=SessionResponse, tags=["Sessions"])
def create_session_endpoint(req: SessionCreate, actor: LocalUser = Depends(require_roles("admin", "operator")), db: DBSession = Depends(get_db)):
    session_id = str(uuid.uuid4())
    session = crud.create_session(
        db,
        session_id=session_id,
        sensor_type=req.sensor_type,
        profile_id=req.profile_id,
        provenance=req.provenance,
        participant_code=req.participant_code,
        study_id=req.study_id,
    )
    crud.create_audit_event(db, action='session_created', session_id=session_id, actor=actor.username)
    return session

@app.get("/api/v1/sessions", tags=["Sessions"])
def list_sessions_endpoint(
    limit: int = 50,
    offset: int = 0,
    provenance: Optional[str] = None,
    status: Optional[str] = None,
    db: DBSession = Depends(get_db),
    _: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer")),
):
    sessions = crud.list_sessions(db, limit=limit, offset=offset, provenance=provenance, status=status)
    stats = crud.get_session_stats(db)
    return {
        "sessions": [SessionResponse.model_validate(s) for s in sessions],
        "total": crud.get_session_count(db),
        "stats": stats,
    }

# ── Studies & Protocols ───────────────────────────────────────────────────────

@app.get("/api/v1/studies", response_model=List[StudyResponse], tags=["Studies"])
def list_studies_endpoint(db: DBSession = Depends(get_db), _: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer"))):
    studies = crud.list_studies(db)
    if not studies:
        # Seed default clinical research study protocol if empty
        default_study = crud.create_study(
            db,
            study_id="STUDY-PILOT-01",
            name="Nghiên cứu Thử nghiệm Dấu ấn Vi rung Cổ tay",
            protocol_version="1.0.0",
            description="Đề cương nghiên cứu vi rung 3-6 Hz sử dụng cảm biến Piezo/ADXL345 trên người tham gia đối chứng và theo dõi.",
            sensor_type="PIEZO_LDT0_028K",
            target_duration_sec=8.0,
            tbr_min=0.40,
            tbr_max=0.85,
        )
        return [StudyResponse.model_validate(default_study)]
    return [StudyResponse.model_validate(st) for st in studies]


@app.post("/api/v1/studies", response_model=StudyResponse, tags=["Studies"])
def create_study_endpoint(req: StudyCreate, actor: LocalUser = Depends(require_roles("admin", "operator")), db: DBSession = Depends(get_db)):
    st = crud.create_study(
        db,
        name=req.name,
        study_id=req.id,
        protocol_version=req.protocol_version,
        description=req.description,
        sensor_type=req.sensor_type,
        target_duration_sec=req.target_duration_sec,
        tbr_min=req.tbr_min,
        tbr_max=req.tbr_max,
    )
    crud.create_audit_event(db, action="study_created", session_id=st.id, actor=actor.username, detail=f"Study created: {req.name}")
    return StudyResponse.model_validate(st)


@app.get("/api/v1/sessions/stats/summary", tags=["Sessions"])
def session_stats(db: DBSession = Depends(get_db), _: LocalUser = Depends(require_roles("admin", "researcher"))):
    return crud.get_session_stats(db)


@app.get("/api/v1/analytics/cohorts", tags=["Analytics"])
def cohort_analytics(db: DBSession = Depends(get_db),
                     _: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer"))):
    """Descriptive summaries computed from locally stored patient/session records."""
    total_patients = db.query(func.count(Patient.id)).scalar() or 0
    total_sessions = crud.get_session_count(db)
    completed_sessions = db.query(func.count(Session.id)).filter(
        Session.is_deleted.is_(False), Session.status == "completed").scalar() or 0
    provenance_rows = db.query(Session.provenance, func.count(Session.id)).filter(
        Session.is_deleted.is_(False)).group_by(Session.provenance).all()

    link = (Session.participant_code == Patient.patient_code) & \
        Session.is_deleted.is_(False) & (Session.status == "completed")

    def cohort_rows(field):
        rows = (db.query(field.label("group"), func.count(func.distinct(Patient.id)).label("participants"),
                          func.count(Session.id).label("sessions"), func.avg(Session.npi_value).label("avg_npi"),
                          func.avg(Session.tbr).label("avg_tbr"))
                .select_from(Patient).outerjoin(Session, link).group_by(field).order_by(field).all())
        return [{"group": group or "Chưa ghi nhận", "participants": participants, "sessions": sessions,
                 "avg_npi": float(avg_npi) if avg_npi is not None else None,
                 "avg_tbr": float(avg_tbr) if avg_tbr is not None else None}
                for group, participants, sessions, avg_npi, avg_tbr in rows]

    return {
        "source": "local_sqlite_records",
        "participant_count": total_patients,
        "session_count": total_sessions,
        "completed_session_count": completed_sessions,
        "provenance_counts": {key: count for key, count in provenance_rows if key is not None},
        "by_age_band": cohort_rows(Patient.age_band),
        "by_chromosome_marker": cohort_rows(Patient.chromosome_marker),
        "by_diet": cohort_rows(Patient.diet),
        "metric_note": "NPI/TBR averages are descriptive per stored completed session; groups may include simulated or imported benchmark sessions and are not clinical comparisons.",
    }

@app.get("/api/v1/sessions/{session_id}", tags=["Sessions"])
def get_session_endpoint(session_id: str, db: DBSession = Depends(get_db), _: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer"))):
    s = crud.get_session(db, session_id)
    if not s:
        raise HTTPException(404, detail=f"Session {session_id} not found")
    return SessionResponse.model_validate(s)

@app.patch("/api/v1/sessions/{session_id}", tags=["Sessions"])
def update_session_endpoint(session_id: str, req: SessionUpdate, actor: LocalUser = Depends(require_roles("admin", "operator", "researcher")), db: DBSession = Depends(get_db)):
    updated = crud.update_session(db, session_id, **req.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(404, detail=f"Session {session_id} not found")
    crud.create_audit_event(db, action='session_updated', session_id=session_id, actor=actor.username, detail=str(req.model_dump(exclude_none=True)))
    return SessionResponse.model_validate(updated)

@app.delete("/api/v1/sessions/{session_id}", tags=["Sessions"])
def delete_session_endpoint(session_id: str, actor: LocalUser = Depends(require_roles("admin")), db: DBSession = Depends(get_db)):
    ok = crud.soft_delete_session(db, session_id)
    if not ok:
        raise HTTPException(404, detail=f"Session {session_id} not found")
    crud.create_audit_event(db, action='session_deleted', session_id=session_id, actor=actor.username)
    return {"status": "deleted", "session_id": session_id}


@app.get("/api/v1/sessions/{session_id}/export", tags=["Sessions"])
def export_session_endpoint(session_id: str, format: str = "json", db: DBSession = Depends(get_db),
                            actor: LocalUser = Depends(require_roles("admin", "operator", "researcher"))):
    s = crud.get_session(db, session_id)
    if not s:
        raise HTTPException(404, detail=f"Session {session_id} not found")

    session_dir = _session_data_dir(session_id)
    raw_h5_path = os.path.join(session_dir, "raw.h5")
    raw_json_path = os.path.join(session_dir, "raw.json")

    channel_samples: Dict[str, List[float]] = {}
    if os.path.exists(raw_h5_path):
        try:
            import h5py
            with h5py.File(raw_h5_path, "r") as h5f:
                if "channels" in h5f:
                    for ch_name in h5f["channels"]:
                        channel_samples[ch_name] = h5f["channels"][ch_name][:].tolist()
        except Exception:
            pass

    if not channel_samples and os.path.exists(raw_json_path):
        try:
            with open(raw_json_path, "r") as f:
                raw_payload = json.load(f)
                channel_samples = raw_payload.get("channels", {})
        except Exception:
            pass

    session_dict = {
        "session_id": s.id,
        "study_id": s.study_id,
        "participant_code": s.participant_code,
        "sensor_type": s.sensor_type,
        "profile_id": s.profile_id,
        "provenance": s.provenance,
        "status": s.status,
        "start_time": s.start_time.isoformat() if s.start_time else None,
        "end_time": s.end_time.isoformat() if s.end_time else None,
        "duration_sec": s.duration_sec,
        "sample_count": s.sample_count,
        "sample_rate_hz": s.sample_rate_hz,
        "tbr": s.tbr,
        "npi_value": s.npi_value,
        "npi_category": s.npi_category,
        "screening_rule_version": "NPI_DEMO_BANDS_40_70_v1" if s.npi_category else None,
        "quality_status": s.quality_status,
        "quality_flags": s.quality_flags,
        "dominant_freq_hz": s.dominant_freq_hz,
        "sha256_hash": s.sha256_hash,
        "notes": s.notes,
        "disclaimer": "RESEARCH / EXPERIMENTAL — NOT FOR DIAGNOSIS",
    }

    if format.lower() == "csv":
        lines = [
            "# NeuroPulse Session Export (CSV)",
            f"# Session ID: {s.id}",
            f"# Sensor Type: {s.sensor_type}",
            f"# Provenance: {s.provenance}",
            f"# Sample Rate: {s.sample_rate_hz} Hz",
            f"# NPI (experimental, not clinically validated): {s.npi_value}",
            f"# Experimental screening band: {s.npi_category or 'not available'}",
            "# Screening rule: NPI_DEMO_BANDS_40_70_v1 (research hypothesis; not clinically validated)",
            f"# TBR: {s.tbr}",
            f"# Disclaimer: RESEARCH / EXPERIMENTAL — NOT FOR DIAGNOSIS",
            "",
        ]
        if channel_samples:
            headers = ["sample_index"] + list(channel_samples.keys())
            lines.append(",".join(headers))
            num_rows = max(len(v) for v in channel_samples.values())
            for i in range(num_rows):
                row = [str(i)]
                for ch in channel_samples.keys():
                    vals = channel_samples[ch]
                    row.append(str(vals[i]) if i < len(vals) else "")
                lines.append(",".join(row))
        return PlainTextResponse("\n".join(lines), media_type="text/csv", headers={
            "Content-Disposition": f"attachment; filename=neuropulse_{session_id}.csv"
        })

    return {
        "metadata": session_dict,
        "channels": channel_samples,
    }


@app.post("/api/v1/benchmark/import", tags=["Benchmark"])
def import_benchmark_endpoint(req: BenchmarkImportRequest, actor: LocalUser = Depends(require_roles("admin", "researcher")), db: DBSession = Depends(get_db)):
    if len(req.samples) < 50:
        raise HTTPException(400, detail="Benchmark sample count too low (must be at least 50 samples).")

    if req.profile_id not in BUILTIN_PROFILES:
        raise HTTPException(400, detail=f"Profile '{req.profile_id}' not found.")

    session_id = f"bench-{uuid.uuid4().hex[:12]}"
    arr = np.asarray(req.samples, dtype=np.float64)
    profile = BUILTIN_PROFILES[req.profile_id]
    if profile.get("sensor_type") != req.sensor_type:
        raise HTTPException(400, detail="Processing profile sensor type does not match the benchmark sensor type.")
    if not np.all(np.isfinite(arr)):
        raise HTTPException(400, detail="Benchmark samples must all be finite numbers.")
    if req.sensor_type == "PIEZO_LDT0_028K" and req.channel_name != "raw_counts":
        raise HTTPException(400, detail="Piezo benchmark data must use channel_name='raw_counts'.")
    if req.sensor_type == "ADXL345" and req.channel_name not in {"x_counts", "y_counts", "z_counts", "x", "y", "z", "mag"}:
        raise HTTPException(400, detail="ADXL345 benchmark data must identify an explicit axis channel.")
    profile = {**profile, "sample_rate_hz": req.sample_rate_hz}

    pipeline_res = run_pipeline(arr, profile)
    npi_res = run_npi(pipeline_res.get("tbr"), quality_status=pipeline_res.get("quality_status"))

    duration_sec = len(arr) / float(req.sample_rate_hz)
    now = datetime.datetime.now(datetime.timezone.utc)

    # Persist files
    session_dir = _session_data_dir(session_id)
    os.makedirs(session_dir, exist_ok=False)
    raw_json_path = os.path.join(session_dir, "raw.json")
    raw_h5_path = os.path.join(session_dir, "raw.h5")

    payload = {
        "session_id": session_id,
        "sensor_type": req.sensor_type,
        "provenance": "imported_benchmark",
        "sample_rate_hz": req.sample_rate_hz,
        "timestamp_start_monotonic_us": int(time.time() * 1_000_000),
        "total_samples": len(req.samples),
        "channels": {req.channel_name: req.samples}
    }
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sha256_hash = hashlib.sha256(canonical_payload).hexdigest()
    payload["sha256"] = sha256_hash
    data_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    with open(raw_json_path, "xb") as f:
        f.write(data_bytes)

    try:
        import h5py
        with h5py.File(raw_h5_path, "x") as h5f:
            h5f.attrs["session_id"] = session_id
            h5f.attrs["sensor_type"] = req.sensor_type
            h5f.attrs["provenance"] = "imported_benchmark"
            h5f.attrs["sample_rate_hz"] = float(req.sample_rate_hz)
            h5f.attrs["total_samples"] = len(req.samples)
            h5f.attrs["sha256_json"] = sha256_hash
            chan_grp = h5f.create_group("channels")
            chan_grp.create_dataset(req.channel_name, data=np.asarray(req.samples, dtype=np.float32), compression="gzip")
        primary_file = raw_h5_path
    except Exception:
        if os.path.exists(raw_h5_path):
            try:
                os.remove(raw_h5_path)
            except OSError:
                pass
        primary_file = raw_json_path

    # Create session record in database
    session = crud.create_session(
        db,
        session_id=session_id,
        sensor_type=req.sensor_type,
        profile_id=req.profile_id,
        provenance="imported_benchmark",
        participant_code=req.participant_code,
        study_id="BENCHMARK_SUITE",
    )
    crud.update_session(
        db,
        session_id=session_id,
        status="completed",
        start_time=now,
        end_time=now,
        duration_sec=duration_sec,
        sample_count=len(req.samples),
        sample_rate_hz=req.sample_rate_hz,
        tbr=pipeline_res.get("tbr"),
        npi_value=npi_res.get("npi_value"),
        npi_category=npi_res.get("category"),
        quality_status=pipeline_res.get("quality_status"),
        quality_flags=json.dumps(pipeline_res.get("quality_flags", [])),
        dominant_freq_hz=pipeline_res.get("dominant_freq_hz"),
        sha256_hash=sha256_hash,
        notes=f"Dataset: {req.name}. {req.notes or ''}",
        raw_data_path=primary_file,
    )
    crud.create_audit_event(db, action="benchmark_imported", session_id=session_id, detail=json.dumps({"name": req.name, "sample_count": len(req.samples)}))

    return {
        "status": "imported",
        "session_id": session_id,
        "name": req.name,
        "provenance": "imported_benchmark",
        "sample_count": len(req.samples),
        "duration_sec": round(duration_sec, 2),
        "tbr": pipeline_res.get("tbr"),
        "npi": npi_res,
        "quality_status": pipeline_res.get("quality_status"),
        "dominant_freq_hz": pipeline_res.get("dominant_freq_hz"),
        "disclaimer": "RESEARCH / EXPERIMENTAL — NOT FOR DIAGNOSIS",
    }


# ── WebSocket realtime stream ─────────────────────────────────────────────────

@app.websocket("/ws/live-stream")
async def websocket_live_stream(ws: WebSocket, token: Optional[str] = None):
    try:
        ensure_local_client(ws.client.host if ws.client else None)
    except HTTPException:
        await ws.close(code=4403)
        return
    db = SessionLocal()
    user = resolve_session(db, token or "")
    db.close()
    if not user or user.role not in {"admin", "operator", "researcher", "reviewer"}:
        await ws.close(code=4401)
        return
    await ws.accept()
    _ws_clients.append(ws)
    try:
        while True:
            # Keep connection alive; data is pushed via listeners
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in _ws_clients:
            _ws_clients.remove(ws)
