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
import ast
import math
import csv
import io
import numpy as np
from sqlalchemy import case, func
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
    from backend.app.db.models import AlgorithmEvaluation, AlgorithmFormula, AuthSession, LocalUser, Patient, Session, Study
    from backend.app.db.timeutils import utcnow_naive
    from backend.app.db.schemas import (SessionCreate, SessionUpdate, SessionResponse, StudyCreate, StudyResponse,
                                        PatientCreate, PatientResponse, PatientRetentionUpdate)
except ImportError:
    from app.db.database import get_db, init_db, SessionLocal
    from app.db import crud
    from app.db.models import AlgorithmEvaluation, AlgorithmFormula, AuthSession, LocalUser, Patient, Session, Study
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
AUTO_STOP_SECONDS = 30.0
_auto_stop_task: Optional[asyncio.Task] = None


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
def list_ports(_: LocalUser = Depends(require_roles("admin", "operator", "researcher"))):
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
def device_status(_: LocalUser = Depends(require_roles("admin", "operator", "researcher", "patient"))):
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
    global _auto_stop_task
    if _auto_stop_task and not _auto_stop_task.done():
        _auto_stop_task.cancel()
    _auto_stop_task = asyncio.create_task(_auto_stop_after(session_id))
    return result


async def _auto_stop_after(session_id: str) -> None:
    """Finalize a recording after the fixed patient-demo duration, even if the UI is closed."""
    try:
        await asyncio.sleep(AUTO_STOP_SECONDS)
        if acq.is_streaming and acq.active_session_id == session_id:
            request = Request(scope={"type": "http", "headers": [], "client": ("127.0.0.1", 0)})
            system_actor = LocalUser(id="system-auto-stop", username="system-auto-stop",
                                     password_hash="", role="admin", is_active=True)
            await stop_acquisition(request, system_actor)
    except asyncio.CancelledError:
        raise
    except Exception:
        logging.getLogger(__name__).exception("Automatic session stop failed for %s", session_id)


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
    global _auto_stop_task
    if _auto_stop_task and _auto_stop_task is not asyncio.current_task() and not _auto_stop_task.done():
        _auto_stop_task.cancel()
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
                    ), request=request, user=actor)
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


@app.get("/api/v1/acquisition/live-analysis", tags=["Acquisition"])
def live_analysis(request: Request, user: LocalUser = Depends(require_roles("patient")),
                  db: DBSession = Depends(get_db)):
    """Return only patient-safe rolling results from the active in-memory signal window."""
    code = (request.headers.get("x-neuropulse-patient-code") or "").strip().upper()
    if not code or not acq.is_streaming or not acq.active_session_id:
        raise HTTPException(status_code=404, detail="Không có phiên đo live cho mã hồ sơ đang chọn.")
    session = crud.get_session(db, acq.active_session_id)
    if not session or session.participant_code != code:
        raise HTTPException(status_code=403, detail="Phiên live không thuộc mã hồ sơ đang chọn.")
    profile = BUILTIN_PROFILES.get(session.profile_id)
    if not profile or profile.get("sensor_type") != acq.selected_sensor:
        raise HTTPException(status_code=409, detail="Không khớp cấu hình phân tích của phiên đo.")

    channel = getattr(acq, "analysis_channel", None)
    if not channel:
        channel = "raw_counts" if acq.selected_sensor == "PIEZO_LDT0_028K" else "x_counts"
    buffer = acq.live_channels.get(channel)
    if buffer is None:
        raise HTTPException(status_code=400, detail="Kênh tín hiệu của phiên đo không khả dụng.")

    sample_rate = float(acq.effective_sample_rate or 0.0)
    profile_window = float(profile["window_length_sec"])
    if not acq.is_simulated and (sample_rate <= 0 or acq.sample_timing_status == "INVALID_DEVICE_TIMESTAMPS"):
        return {"elapsed_sec": _live_elapsed_seconds(), "quality_status": "INSUFFICIENT_DATA",
                "npi": run_npi(None, quality_status="INSUFFICIENT_DATA"),
                "disclaimer": "RESEARCH / EXPERIMENTAL — NOT FOR DIAGNOSIS"}

    window_samples = int(sample_rate * profile_window) if sample_rate > 0 else 0
    available = list(buffer)
    if not window_samples or len(available) < window_samples:
        return {"elapsed_sec": _live_elapsed_seconds(), "quality_status": "INSUFFICIENT_DATA",
                "npi": run_npi(None, quality_status="INSUFFICIENT_DATA"),
                "disclaimer": "RESEARCH / EXPERIMENTAL — NOT FOR DIAGNOSIS"}

    live_profile = {**profile, "sample_rate_hz": sample_rate}
    raw_window = np.asarray(available[-window_samples:], dtype=np.float64)
    pre_flags = []
    if not acq.is_simulated:
        if acq.sequence_gaps:
            pre_flags.append("SAMPLE_GAP")
        if acq.packet_crc_errors or acq.malformed_packets:
            pre_flags.append("PACKET_CORRUPTION")
        if acq.sample_timing_status == "INVALID_DEVICE_TIMESTAMPS":
            pre_flags.append("INVALID_DEVICE_TIMESTAMPS")
        if acq.timestamp_errors:
            pre_flags.append("INVALID_DEVICE_TIMESTAMPS")
    metrics = run_pipeline(raw_window, live_profile, pre_quality_flags=pre_flags)
    npi = run_npi(metrics.get("tbr"), quality_status=metrics.get("quality_status", "INSUFFICIENT_DATA"))
    return {"elapsed_sec": _live_elapsed_seconds(), "quality_status": metrics.get("quality_status"),
            "npi": npi, "disclaimer": "RESEARCH / EXPERIMENTAL — NOT FOR DIAGNOSIS"}


def _live_elapsed_seconds() -> float:
    if not acq.start_stream_time:
        return 0.0
    return round(max(0.0, time.perf_counter() - acq.start_stream_time), 1)


@app.get("/api/v1/acquisition/status", tags=["Acquisition"])
def acquisition_status(_: LocalUser = Depends(require_roles("admin", "operator", "researcher", "patient"))):
    return acq.get_status()


@app.get("/api/v1/acquisition/live-buffer", tags=["Acquisition"])
def live_buffer(request: Request, channel: str = "raw_counts", max_samples: int = 1000,
                user: LocalUser = Depends(require_roles("admin", "operator", "researcher", "patient"))):
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
def list_profiles(_: LocalUser = Depends(require_roles("admin", "operator", "researcher"))):
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
    acquisition_quality_flags = []

    if os.path.exists(raw_h5_path):
        try:
            import h5py
            with h5py.File(raw_h5_path, "r") as h5f:
                sensor_type = str(h5f.attrs.get("sensor_type", ""))
                provenance = str(h5f.attrs.get("provenance", ""))
                sample_rate_hz = float(h5f.attrs.get("sample_rate_hz", 0)) or None
                if int(h5f.attrs.get("sequence_gaps", 0)) > 0:
                    acquisition_quality_flags.append("SAMPLE_GAP")
                if int(h5f.attrs.get("packet_crc_errors", 0)) > 0 or int(h5f.attrs.get("malformed_packets", 0)) > 0:
                    acquisition_quality_flags.append("PACKET_CORRUPTION")
                if int(h5f.attrs.get("timestamp_errors", 0)) > 0:
                    acquisition_quality_flags.append("INVALID_DEVICE_TIMESTAMPS")
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
        if int(session_data.get("sequence_gaps", 0)) > 0:
            acquisition_quality_flags.append("SAMPLE_GAP")
        if int(session_data.get("packet_crc_errors", 0)) > 0 or int(session_data.get("malformed_packets", 0)) > 0:
            acquisition_quality_flags.append("PACKET_CORRUPTION")
        if int(session_data.get("timestamp_errors", 0)) > 0:
            acquisition_quality_flags.append("INVALID_DEVICE_TIMESTAMPS")
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
    elif provenance == "device":
        acquisition_quality_flags.append("SAMPLE_RATE_UNVERIFIED")
    if sensor_type == "PIEZO_LDT0_028K" and selected_channel != "raw_counts":
        raise HTTPException(status_code=400, detail="Piezo analysis requires the raw_counts channel.")
    if sensor_type == "ADXL345" and selected_channel not in {"x_counts", "y_counts", "z_counts", "x", "y", "z", "mag"}:
        raise HTTPException(status_code=400, detail="Choose an available ADXL345 axis channel explicitly.")

    arr = np.asarray(channel_data, dtype=np.float64)
    if provenance == "device" and not sample_rate_hz:
        stride = max(1, int(np.ceil(len(arr) / 2000)))
        result = {
            "quality_status": "INSUFFICIENT_DATA",
            "quality_flags": list(dict.fromkeys(acquisition_quality_flags)),
            "sample_count": int(len(arr)),
            "sample_rate_hz": None,
            "raw_signal_preview": arr[::stride].astype(float).tolist(),
            "raw_signal_preview_stride": stride,
            "tbr": None,
        }
    else:
        result = run_pipeline(arr, profile, pre_quality_flags=acquisition_quality_flags)

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
def list_algorithms(_: LocalUser = Depends(require_roles("admin", "operator", "researcher"))):
    return AlgorithmRegistry.list_all()


class FormulaCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    expression: str = Field(default="100 * (1 - clip((tbr - tbr_min) / (tbr_max - tbr_min), 0, 1))", max_length=300)
    tbr_min: float = Field(ge=0, le=1, allow_inf_nan=False)
    tbr_max: float = Field(gt=0, le=1, allow_inf_nan=False)
    change_note: str = Field(min_length=1, max_length=1000)


@app.get("/api/v1/algorithms/formulas", tags=["Algorithm Lab"])
def list_formulas(db: DBSession = Depends(get_db), _: LocalUser = Depends(require_roles("admin", "operator", "researcher"))):
    formulas = db.query(AlgorithmFormula).order_by(AlgorithmFormula.created_at.desc()).all()
    return [{"id": f.id, "version": f.version, "name": f.name, "expression": f.expression, "tbr_min": f.tbr_min, "tbr_max": f.tbr_max, "status": f.status, "change_note": f.change_note, "created_at": f.created_at} for f in formulas]


@app.get("/api/v1/algorithms/evaluations", tags=["Algorithm Lab"])
def list_algorithm_evaluations(limit: int = 100, offset: int = 0, db: DBSession = Depends(get_db), _: LocalUser = Depends(require_roles("admin", "operator", "researcher"))):
    limit = max(1, min(limit, 500)); offset = max(0, offset)
    rows = (db.query(AlgorithmEvaluation).order_by(AlgorithmEvaluation.created_at.desc())
            .offset(offset).limit(limit).all())
    return [{"id": row.id, "formula_id": row.formula_id, "formula_version": row.formula_version,
             "session_id": row.session_id, "tbr": row.tbr, "quality_status": row.quality_status,
             "npi_value": row.npi_value, "parameters_snapshot": json.loads(row.parameters_snapshot),
             "source_metadata": json.loads(row.source_metadata), "created_at": row.created_at}
            for row in rows]


@app.get("/api/v1/algorithms/evaluations/export", tags=["Algorithm Lab"])
def export_algorithm_evaluations(format: str = "csv", db: DBSession = Depends(get_db), actor: LocalUser = Depends(require_roles("admin", "operator", "researcher"))):
    if format.lower() not in {"csv", "json"}:
        raise HTTPException(status_code=400, detail="format must be json or csv")
    rows = db.query(AlgorithmEvaluation).order_by(AlgorithmEvaluation.created_at.asc()).all()
    formula_ids = {row.formula_id for row in rows}
    formulas = {formula.id: formula for formula in db.query(AlgorithmFormula).filter(AlgorithmFormula.id.in_(formula_ids)).all()} if formula_ids else {}
    records = [{
        "evaluation_id": row.id, "formula_id": row.formula_id,
        "formula_name": formulas[row.formula_id].name if row.formula_id in formulas else None,
        "formula_version": row.formula_version, "session_id": row.session_id,
        "tbr": row.tbr, "quality_status": row.quality_status, "npi_value": row.npi_value,
        "parameters_snapshot": json.loads(row.parameters_snapshot),
        "source_metadata": json.loads(row.source_metadata), "created_at": row.created_at,
    } for row in rows]
    crud.create_audit_event(db, action="algorithm_evaluations_exported", actor=actor.username,
                            detail={"format": format, "record_count": len(records)})
    if format.lower() == "json":
        return {"export_scope": "experimental formula evaluations; not clinical results", "count": len(records), "evaluations": records}
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    fields = ["evaluation_id", "formula_id", "formula_name", "formula_version", "session_id", "tbr", "quality_status", "npi_value", "parameters_snapshot", "source_metadata", "created_at"]
    writer.writerow(fields)
    for record in records:
        values = []
        for field in fields:
            value = json.dumps(record[field], ensure_ascii=False) if isinstance(record[field], (dict, list)) else record[field]
            # Spreadsheet programs may execute untrusted text beginning with formula characters.
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return PlainTextResponse(output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=neuropulse_algorithm_evaluations.csv"})


@app.post("/api/v1/algorithms/formulas", tags=["Algorithm Lab"])
def create_formula(req: FormulaCreateRequest, db: DBSession = Depends(get_db), actor: LocalUser = Depends(require_roles("admin", "operator", "researcher"))):
    if not req.name.strip() or not req.change_note.strip():
        raise HTTPException(status_code=422, detail="Nhập tên công thức và ghi chú thay đổi.")
    try:
        _validate_formula_expression(req.expression)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    canonical = req.expression.strip()
    if req.tbr_max <= req.tbr_min:
        raise HTTPException(status_code=422, detail="TBR max phải lớn hơn TBR min.")
    prior = db.query(AlgorithmFormula).filter(AlgorithmFormula.name == req.name.strip()).order_by(AlgorithmFormula.version.desc()).first()
    version = prior.version + 1 if prior else 1
    db.query(AlgorithmFormula).filter(AlgorithmFormula.name == req.name.strip(), AlgorithmFormula.status != "retired").update({"status": "retired"}, synchronize_session=False)
    formula = AlgorithmFormula(id=str(uuid.uuid4()), version=version, name=req.name.strip(), expression=canonical, tbr_min=req.tbr_min, tbr_max=req.tbr_max, status="experimental", change_note=req.change_note.strip())
    db.add(formula); db.commit(); db.refresh(formula)
    crud.create_audit_event(db, action="algorithm_formula_created", actor=actor.username, detail={"formula_id": formula.id, "version": version})
    return {"id": formula.id, "version": formula.version, "name": formula.name, "expression": formula.expression, "tbr_min": formula.tbr_min, "tbr_max": formula.tbr_max, "status": formula.status, "change_note": formula.change_note, "created_at": formula.created_at}


def _validate_formula_expression(expression: str) -> ast.Expression:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Biểu thức không đúng cú pháp.") from exc
    if len(list(ast.walk(tree))) > 80:
        raise ValueError("Biểu thức quá phức tạp.")
    allowed_names = {"tbr", "tbr_min", "tbr_max"}
    allowed_binops = (ast.Add, ast.Sub, ast.Mult, ast.Div)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in allowed_names | {"clip"}:
            raise ValueError(f"Tên không được phép trong công thức: {node.id}")
        if isinstance(node, ast.BinOp) and not isinstance(node.op, allowed_binops):
            raise ValueError("Chỉ cho phép phép cộng, trừ, nhân và chia.")
        if isinstance(node, ast.UnaryOp) and not isinstance(node.op, (ast.UAdd, ast.USub)):
            raise ValueError("Phép toán một ngôi không được hỗ trợ.")
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id != "clip" or node.keywords or len(node.args) != 3):
            raise ValueError("Chỉ hỗ trợ hàm clip(value, min, max) với đúng 3 tham số.")
        if isinstance(node, (ast.Attribute, ast.Subscript, ast.Lambda, ast.Dict, ast.List, ast.Tuple, ast.Compare, ast.BoolOp, ast.IfExp)):
            raise ValueError("Cấu trúc biểu thức này không được phép.")
        if isinstance(node, ast.Constant) and (not isinstance(node.value, (int, float)) or isinstance(node.value, bool)):
            raise ValueError("Chỉ cho phép hằng số số học.")
    return tree


def _evaluate_formula_node(node: ast.AST, values: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate_formula_node(node.body, values)
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.UnaryOp):
        value = _evaluate_formula_node(node.operand, values)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left, right = _evaluate_formula_node(node.left, values), _evaluate_formula_node(node.right, values)
        if isinstance(node.op, ast.Add): value = left + right
        elif isinstance(node.op, ast.Sub): value = left - right
        elif isinstance(node.op, ast.Mult): value = left * right
        elif isinstance(node.op, ast.Div):
            if right == 0: raise ValueError("Không thể chia cho 0.")
            value = left / right
        else: raise ValueError("Phép toán không hỗ trợ.")
        if not math.isfinite(value) or abs(value) > 1e9: raise ValueError("Giá trị trung gian vượt giới hạn an toàn.")
        return value
    if isinstance(node, ast.Call):
        value, low, high = (_evaluate_formula_node(arg, values) for arg in node.args)
        if low > high: raise ValueError("Giới hạn clip không hợp lệ.")
        return max(low, min(high, value))
    raise ValueError("Node trong công thức không được hỗ trợ.")


class FormulaEvaluateRequest(BaseModel):
    tbr: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    quality_status: str = "VALID_FOR_ANALYSIS"
    session_id: Optional[str] = None


@app.post("/api/v1/algorithms/formulas/{formula_id}/compute", tags=["Algorithm Lab"])
def evaluate_formula(formula_id: str, req: FormulaEvaluateRequest, db: DBSession = Depends(get_db), actor: LocalUser = Depends(require_roles("admin", "operator", "researcher"))):
    formula = db.query(AlgorithmFormula).filter(AlgorithmFormula.id == formula_id).first()
    if not formula or formula.status == "retired":
        raise HTTPException(status_code=404, detail="Không tìm thấy công thức đang hoạt động.")
    if req.quality_status in {"INVALID", "INSUFFICIENT_DATA"} or req.tbr is None:
        evaluation = AlgorithmEvaluation(
            id=str(uuid.uuid4()), formula_id=formula.id, formula_version=formula.version,
            session_id=req.session_id, tbr=req.tbr, quality_status=req.quality_status,
            npi_value=None, parameters_snapshot=json.dumps({"tbr_min": formula.tbr_min, "tbr_max": formula.tbr_max}),
            source_metadata="{}",
        )
        db.add(evaluation); db.commit(); db.refresh(evaluation)
        crud.create_audit_event(db, action="algorithm_formula_evaluated", actor=actor.username,
                                 session_id=req.session_id,
                                 detail={"formula_id": formula.id, "version": formula.version, "tbr": req.tbr,
                                         "quality_status": req.quality_status, "npi_value": None})
        return {"evaluation_id": evaluation.id, "npi_value": None, "tbr": req.tbr, "quality_status": req.quality_status, "formula_id": formula.id, "formula_name": formula.name, "formula_version": formula.version, "parameter_snapshot": {"tbr_min": formula.tbr_min, "tbr_max": formula.tbr_max}, "warnings": ["Cửa sổ dữ liệu không đủ điều kiện."]}
    try:
        expression = _validate_formula_expression(formula.expression)
        value = _evaluate_formula_node(expression, {"tbr": req.tbr, "tbr_min": formula.tbr_min, "tbr_max": formula.tbr_max})
        if not 0 <= value <= 100:
            raise ValueError("Giá trị kết quả nằm ngoài miền 0–100.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    evaluation = AlgorithmEvaluation(
        id=str(uuid.uuid4()), formula_id=formula.id, formula_version=formula.version,
        session_id=req.session_id, tbr=req.tbr, quality_status=req.quality_status,
        npi_value=round(value, 2), parameters_snapshot=json.dumps({"tbr_min": formula.tbr_min, "tbr_max": formula.tbr_max}),
        source_metadata="{}",
    )
    db.add(evaluation); db.commit(); db.refresh(evaluation)
    crud.create_audit_event(db, action="algorithm_formula_evaluated", actor=actor.username,
                            session_id=req.session_id,
                            detail={"formula_id": formula.id, "version": formula.version, "tbr": req.tbr,
                                    "quality_status": req.quality_status, "npi_value": round(value, 2),
                                    "parameters": {"tbr_min": formula.tbr_min, "tbr_max": formula.tbr_max}})
    return {"evaluation_id": evaluation.id, "npi_value": round(value, 2), "tbr": req.tbr, "quality_status": req.quality_status, "formula_id": formula.id, "formula_name": formula.name, "formula_version": formula.version, "parameter_snapshot": {"tbr_min": formula.tbr_min, "tbr_max": formula.tbr_max}, "warnings": ["Chỉ đánh giá công thức thử nghiệm trong Lab; không phải kết quả lâm sàng."]}


class FormulaSessionEvaluateRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=80)
    channel: Optional[str] = None


@app.post("/api/v1/algorithms/formulas/{formula_id}/evaluate-session", tags=["Algorithm Lab"])
def evaluate_formula_on_session(formula_id: str, req: FormulaSessionEvaluateRequest, db: DBSession = Depends(get_db), actor: LocalUser = Depends(require_roles("admin", "operator", "researcher"))):
    formula = db.query(AlgorithmFormula).filter(AlgorithmFormula.id == formula_id, AlgorithmFormula.status != "retired").first()
    session = crud.get_session(db, req.session_id)
    if not formula:
        raise HTTPException(status_code=404, detail="Không tìm thấy công thức đang hoạt động.")
    if not session or session.is_deleted or session.status != "completed":
        raise HTTPException(status_code=404, detail="Chỉ có thể phân tích phiên đã lưu và chưa bị xóa.")
    local_request = Request(scope={"type": "http", "headers": [], "client": ("127.0.0.1", 0)})
    analysis_response = analyse_session(RunAnalysisRequest(session_id=session.id, profile_id=session.profile_id, channel=req.channel), local_request, actor)
    analysis = analysis_response.get("analysis", {})
    session_tbr = analysis.get("tbr")
    evaluated = evaluate_formula(formula.id, FormulaEvaluateRequest(
        tbr=session_tbr,
        quality_status=analysis.get("quality_status", "INSUFFICIENT_DATA") if session_tbr is not None else "INSUFFICIENT_DATA",
        session_id=session.id,
    ), db, actor)
    evaluated["session_id"] = session.id
    evaluated["reprocessing"] = {
        "channel": analysis_response.get("channel"),
        "profile_id": analysis_response.get("profile_id"),
        "sensor_type": analysis_response.get("sensor_type"),
        "provenance": analysis_response.get("provenance"),
        "sample_count": analysis.get("sample_count"),
        "sample_rate_hz": analysis.get("sample_rate_hz"),
        "quality_status": analysis.get("quality_status"),
        "quality_flags": analysis.get("quality_flags", []),
        "tbr": analysis.get("tbr"),
    }
    evaluation_record = db.query(AlgorithmEvaluation).filter(AlgorithmEvaluation.id == evaluated["evaluation_id"]).first()
    if evaluation_record:
        evaluation_record.source_metadata = json.dumps(evaluated["reprocessing"])
        db.commit()
    return evaluated


@app.delete("/api/v1/algorithms/formulas/{formula_id}", tags=["Algorithm Lab"])
def retire_formula(formula_id: str, db: DBSession = Depends(get_db), actor: LocalUser = Depends(require_roles("admin", "operator", "researcher"))):
    formula = db.query(AlgorithmFormula).filter(AlgorithmFormula.id == formula_id).first()
    if not formula:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên bản công thức.")
    formula.status = "retired"; db.commit()
    crud.create_audit_event(db, action="algorithm_formula_retired", actor=actor.username, detail={"formula_id": formula.id, "version": formula.version})
    return {"id": formula.id, "status": formula.status, "message": "Đã ngừng dùng; bản ghi được giữ để truy nguyên."}


@app.post("/api/v1/algorithms/npi/compute", tags=["Algorithm Lab"])
def compute_npi(req: RunNPIRequest, _: LocalUser = Depends(require_roles("admin", "operator", "researcher"))):
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
        marker = ("Y" if req.reported_sex == "male" else "X" if req.reported_sex == "female" else req.chromosome_marker)
        if marker is None:
            raise ValueError("Choose male or female to assign the patient-code marker.")
        patient_code = generate_patient_code(db, marker, age_band, first_measurement_date)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    created_at = utcnow_naive()
    patient = Patient(
        id=str(uuid.uuid4()), patient_code=patient_code, full_name=req.full_name.strip(),
        date_of_birth=req.date_of_birth, chromosome_marker=marker, reported_sex=req.reported_sex,
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
    actor: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer")),
):
    sessions = crud.list_sessions(db, limit=limit, offset=offset, provenance=provenance, status=status)
    stats = crud.get_session_stats(db)
    serialized = [SessionResponse.model_validate(s).model_dump() for s in sessions]
    if actor.role == "reviewer":
        serialized = [_reviewer_session_view(row) for row in serialized]
    return {
        "sessions": serialized,
        "total": crud.get_session_count(db),
        "stats": stats,
    }

# ── Studies & Protocols ───────────────────────────────────────────────────────

@app.get("/api/v1/studies", tags=["Studies"])
def list_studies_endpoint(db: DBSession = Depends(get_db), actor: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer"))):
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
        studies = [default_study]
    serialized = [StudyResponse.model_validate(st).model_dump() for st in studies]
    if actor.role == "reviewer":
        # Preserve protocol context while excluding sensor identifiers and
        # algorithm cutoff constants reserved for research/staff modes.
        technical_fields = {"sensor_type", "tbr_min", "tbr_max"}
        return [{key: value for key, value in study.items() if key not in technical_fields}
                for study in serialized]
    return serialized


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
def session_stats(db: DBSession = Depends(get_db), _: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer"))):
    return crud.get_session_stats(db)


@app.get("/api/v1/analytics/cohorts", tags=["Analytics"])
def cohort_analytics(db: DBSession = Depends(get_db),
                     provenance: Optional[str] = None,
                     study_id: Optional[str] = None,
                     sensor_type: Optional[str] = None,
                     quality_status: Optional[str] = None,
                     date_from: Optional[datetime.date] = None,
                     date_to: Optional[datetime.date] = None,
                     actor: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer"))):
    """Descriptive summaries computed from locally stored patient/session records."""
    known_provenance = {"simulated", "device", "imported_benchmark", "reprocessed"}
    if provenance is not None and provenance not in known_provenance:
        raise HTTPException(status_code=400, detail="Unsupported provenance filter.")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="Start date must not be after end date.")
    if actor.role == "reviewer" and sensor_type:
        raise HTTPException(status_code=403, detail="Clinical Reviewer mode cannot filter by technical sensor type.")

    selected_filters = []
    if provenance:
        selected_filters.append(Session.provenance == provenance)
    if study_id:
        selected_filters.append(Session.study_id == (None if study_id == "unassigned" else study_id))
    if sensor_type:
        selected_filters.append(Session.sensor_type == sensor_type)
    if quality_status:
        selected_filters.append(Session.quality_status.is_(None) if quality_status == "unrated" else Session.quality_status == quality_status)
    session_date = func.coalesce(Session.start_time, Session.created_at)
    if date_from:
        selected_filters.append(session_date >= datetime.datetime.combine(date_from, datetime.time.min))
    if date_to:
        selected_filters.append(session_date < datetime.datetime.combine(date_to + datetime.timedelta(days=1), datetime.time.min))

    sessions_query = db.query(Session).filter(Session.is_deleted.is_(False), *selected_filters)
    total_sessions = sessions_query.count()
    completed_sessions = sessions_query.filter(Session.status == "completed").count()
    provenance_rows = db.query(Session.provenance, func.count(Session.id)).filter(
        Session.is_deleted.is_(False)).group_by(Session.provenance).all()

    link = (Session.participant_code == Patient.patient_code) & \
        Session.is_deleted.is_(False) & (Session.status == "completed")
    for criterion in selected_filters:
        link = link & criterion

    if selected_filters:
        participant_count = (db.query(func.count(func.distinct(Patient.id)))
                             .select_from(Patient)
                             .join(Session, (Session.participant_code == Patient.patient_code) &
                                   Session.is_deleted.is_(False) & (Session.status == "completed"))
                             .filter(*selected_filters)
                             .scalar() or 0)
    else:
        participant_count = db.query(func.count(Patient.id)).scalar() or 0

    def cohort_rows(field):
        participants_expr = (func.count(func.distinct(Patient.id)) if not selected_filters else
                             func.count(func.distinct(case((Session.id.is_not(None), Patient.id), else_=None))))
        rows = (db.query(field.label("group"), participants_expr.label("participants"),
                          func.count(Session.id).label("sessions"), func.avg(Session.npi_value).label("avg_npi"),
                          func.avg(Session.tbr).label("avg_tbr"))
                .select_from(Patient).outerjoin(Session, link).group_by(field).order_by(field).all())
        return [{"group": group or "Chưa ghi nhận", "participants": participants, "sessions": sessions,
                 "avg_npi": float(avg_npi) if avg_npi is not None else None,
                 "avg_tbr": float(avg_tbr) if avg_tbr is not None else None}
                for group, participants, sessions, avg_npi, avg_tbr in rows
                if not selected_filters or participants > 0]

    return {
        "source": "local_sqlite_records",
        "participant_count": participant_count,
        "session_count": total_sessions,
        "completed_session_count": completed_sessions,
        "provenance_counts": {key: count for key, count in provenance_rows if key is not None},
        "selected_provenance": provenance or "all",
        "selected_filters": {
            "study_id": study_id or "all",
            "sensor_type": sensor_type or "all",
            "quality_status": quality_status or "all",
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
        "filter_options": {
            "studies": [{"id": row.id, "name": row.name} for row in db.query(Study).order_by(Study.name).all()],
            "sensor_types": [] if actor.role == "reviewer" else [row[0] for row in db.query(Session.sensor_type).filter(Session.is_deleted.is_(False)).distinct().order_by(Session.sensor_type).all()],
            "quality_statuses": [row[0] for row in db.query(Session.quality_status).filter(Session.is_deleted.is_(False), Session.quality_status.isnot(None)).distinct().order_by(Session.quality_status).all()],
        },
        "by_age_band": cohort_rows(Patient.age_band),
        "by_reported_sex": cohort_rows(case(
            (Patient.reported_sex == "female", "Nữ"),
            (Patient.reported_sex == "male", "Nam"),
            (Patient.chromosome_marker == "X", "Nữ (hồ sơ cũ)"),
            (Patient.chromosome_marker == "Y", "Nam (hồ sơ cũ)"),
            else_="Chưa ghi nhận",
        )),
        "by_diet": cohort_rows(Patient.diet),
        "metric_note": "NPI/TBR averages are descriptive per stored completed session for the selected source; they are not clinical comparisons.",
    }

@app.get("/api/v1/sessions/{session_id}", tags=["Sessions"])
def get_session_endpoint(session_id: str, db: DBSession = Depends(get_db), actor: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer"))):
    s = crud.get_session(db, session_id)
    if not s:
        raise HTTPException(404, detail=f"Session {session_id} not found")
    result = SessionResponse.model_validate(s).model_dump()
    return _reviewer_session_view(result) if actor.role == "reviewer" else result


def _reviewer_session_view(session: Dict[str, Any]) -> Dict[str, Any]:
    """Remove device, acquisition, storage, and source-path details for reviewers."""
    technical_fields = {
        "sensor_type", "profile_id", "sample_rate_hz", "sample_count", "total_samples",
        "sha256_hash", "raw_data_path", "notes",
    }
    return {key: value for key, value in session.items() if key not in technical_fields}

@app.patch("/api/v1/sessions/{session_id}", tags=["Sessions"])
def update_session_endpoint(session_id: str, req: SessionUpdate, actor: LocalUser = Depends(require_roles("admin", "operator", "researcher")), db: DBSession = Depends(get_db)):
    updated = crud.update_session(db, session_id, **req.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(404, detail=f"Session {session_id} not found")
    crud.create_audit_event(db, action='session_updated', session_id=session_id, actor=actor.username, detail=str(req.model_dump(exclude_none=True)))
    return SessionResponse.model_validate(updated)

@app.delete("/api/v1/sessions/{session_id}", tags=["Sessions"])
def delete_session_endpoint(session_id: str, actor: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer")), db: DBSession = Depends(get_db)):
    ok = crud.soft_delete_session(db, session_id)
    if not ok:
        raise HTTPException(404, detail=f"Session {session_id} not found")
    crud.create_audit_event(db, action='session_deleted', session_id=session_id, actor=actor.username)
    return {"status": "deleted", "session_id": session_id}


@app.get("/api/v1/sessions/{session_id}/export", tags=["Sessions"])
def export_session_endpoint(session_id: str, format: str = "json", db: DBSession = Depends(get_db),
                            actor: LocalUser = Depends(require_roles("admin", "operator", "researcher", "reviewer"))):
    s = crud.get_session(db, session_id)
    if not s:
        raise HTTPException(404, detail=f"Session {session_id} not found")

    if actor.role == "reviewer":
        # Reviewers may export clinical/session summaries, but never raw channels
        # or device/processing identifiers from the staff research export.
        clinical = {
            "session_id": s.id,
            "study_id": s.study_id,
            "participant_code": s.participant_code,
            "provenance": s.provenance,
            "status": s.status,
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "duration_sec": s.duration_sec,
            "tbr": s.tbr,
            "npi_value": s.npi_value,
            "npi_category": s.npi_category,
            "screening_rule_version": "NPI_DEMO_BANDS_40_70_v1" if s.npi_category else None,
            "quality_status": s.quality_status,
            "dominant_freq_hz": s.dominant_freq_hz,
            "disclaimer": "RESEARCH / EXPERIMENTAL — NOT FOR DIAGNOSIS",
        }
        crud.create_audit_event(db, action="session_exported", session_id=s.id, actor=actor.username,
                                detail=f"format={format.lower()}; scope=reviewer_clinical_summary")
        if format.lower() == "csv":
            headers = list(clinical.keys())
            values = ["" if clinical[key] is None else str(clinical[key]).replace('"', '""') for key in headers]
            return PlainTextResponse(",".join(headers) + "\n" + ",".join(f'"{value}"' for value in values),
                                     media_type="text/csv", headers={
                                         "Content-Disposition": f"attachment; filename=neuropulse_{session_id}_review.csv"
                                     })
        if format.lower() != "json":
            raise HTTPException(status_code=400, detail="format must be json or csv")
        return {"metadata": clinical}

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


@app.get("/api/v1/patients/lookup/{patient_code}/export", tags=["Patients"])
def export_patient_record(patient_code: str, request: Request,
                          actor: LocalUser = Depends(require_roles("patient")),
                          db: DBSession = Depends(get_db)):
    """Export the selected local patient record and its own session measurements.

    The patient code is a prototype lookup key, not identity verification. This
    endpoint is intentionally restricted to loopback and the Patient workflow
    mode, and requires the selected code header to match the requested record.
    """
    ensure_local_client(request.client.host if request.client else None)
    code = patient_code.strip().upper()
    selected_code = (request.headers.get("x-neuropulse-patient-code") or "").strip().upper()
    if not selected_code or selected_code != code:
        raise HTTPException(status_code=403, detail="Mã hồ sơ cần xuất phải khớp với mã bệnh nhân đang chọn.")

    patient = db.query(Patient).filter(Patient.patient_code == code).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ theo mã bệnh nhân.")

    sessions = (db.query(Session)
                .filter(Session.participant_code == code, Session.is_deleted.is_(False))
                .order_by(Session.created_at.desc()).all())
    category_labels = {
        "experimental_reference_range": "Trong khoảng tham chiếu demo",
        "experimental_monitoring": "Theo dõi theo giả thuyết demo",
        "outside_experimental_reference_range": "Ngoài khoảng tham chiếu demo",
    }
    quality_labels = {
        "VALID_FOR_ANALYSIS": "Đủ dữ liệu cho phân tích thử nghiệm",
        "WARNING": "Tín hiệu cần được nhân viên kiểm tra",
        "INVALID": "Phép đo chưa đạt kiểm tra chất lượng",
        "INSUFFICIENT_DATA": "Phiên đo chưa đủ dài để phân tích",
        "ANALYSIS_PENDING": "Đang xử lý",
    }
    origin_labels = {
        "simulated": "Dữ liệu mô phỏng",
        "device": "Dữ liệu từ thiết bị",
        "imported_benchmark": "Dữ liệu benchmark nhập vào",
        "reprocessed": "Kết quả xử lý lại",
    }
    exported_sessions = [{
        "measured_at": (session.start_time or session.created_at).isoformat() if (session.start_time or session.created_at) else None,
        "duration_seconds": session.duration_sec,
        "result_status": "Hoàn tất" if session.status == "completed" else "Chưa hoàn tất",
        "experimental_npi": session.npi_value,
        "experimental_screening_band": category_labels.get(session.npi_category, "Chưa có kết quả phân loại"),
        "experimental_rule_version": "NPI_DEMO_BANDS_40_70_v1" if session.npi_category else None,
        "measurement_quality": quality_labels.get(session.quality_status, "Chưa đánh giá"),
        "data_origin": origin_labels.get(session.provenance, "Nguồn dữ liệu chưa xác định"),
    } for session in sessions]
    crud.create_audit_event(
        db, action="patient_personal_data_exported", actor=actor.username,
        detail={"patient_code": code, "session_count": len(exported_sessions)},
    )
    return {
        "export_version": "patient-personal-export-v1",
        "exported_at": utcnow_naive().isoformat() + "Z",
        "patient": {
            "patient_code": patient.patient_code,
            "full_name": patient.full_name,
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "reported_sex": patient.reported_sex,
            "age_band": patient.age_band,
            "medical_history": patient.medical_history,
            "family_history": patient.family_history,
            "diet": patient.diet,
        },
        "sessions": exported_sessions,
        "export_scope": "Personal profile and patient-friendly session summaries only; raw sensor samples and technical device/processing details are not included.",
        "provenance_note": "Nguồn dữ liệu được ghi rõ cho từng phiên. Dữ liệu mô phỏng hoặc benchmark nhập vào không phải phép đo người tham gia.",
        "experimental_notice": "NPI và các dải hiển thị là kết quả nghiên cứu thử nghiệm, chưa được xác nhận lâm sàng và không phải chẩn đoán.",
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
    if not user or user.role not in {"admin", "operator", "researcher"}:
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
