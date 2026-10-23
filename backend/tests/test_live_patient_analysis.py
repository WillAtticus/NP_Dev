import asyncio
import time
from collections import deque

import numpy as np
from fastapi.testclient import TestClient

from backend.app.db.models import LocalUser
from backend.app import main as backend_main
from backend.app.main import app, current_local_user, acq


def test_patient_live_analysis_waits_for_eight_seconds_and_returns_minimal_result():
    client = TestClient(app)
    created = client.post("/api/v1/sessions", json={
        "sensor_type": "PIEZO_LDT0_028K",
        "profile_id": "piezo_butterworth_1_20_default",
        "provenance": "simulated",
        "participant_code": "LIVE_PATIENT_01",
    })
    assert created.status_code == 200
    session_id = created.json()["id"]

    prior = (acq.is_streaming, acq.is_simulated, acq.active_session_id, acq.selected_sensor,
             acq.effective_sample_rate, acq.start_stream_time, acq.analysis_channel,
             acq.live_channels["raw_counts"])
    try:
        acq.is_streaming = True
        acq.is_simulated = True
        acq.active_session_id = session_id
        acq.selected_sensor = "PIEZO_LDT0_028K"
        acq.effective_sample_rate = 1000.0
        acq.start_stream_time = time.perf_counter() - 9.0
        acq.analysis_channel = "raw_counts"
        acq.live_channels["raw_counts"] = deque([2048.0 + 100.0 * np.sin(2 * np.pi * 5 * i / 1000)
                                                   for i in range(8000)], maxlen=8000)

        app.dependency_overrides[current_local_user] = lambda: LocalUser(
            id="live-patient", username="live-patient", password_hash="", role="patient", is_active=True
        )
        response = client.get("/api/v1/acquisition/live-analysis",
                              headers={"X-NeuroPulse-Patient-Code": "LIVE_PATIENT_01"})
        assert response.status_code == 200
        body = response.json()
        assert body["quality_status"] == "VALID_FOR_ANALYSIS"
        assert body["npi"]["npi_value"] is not None
        assert set(body) == {"elapsed_sec", "quality_status", "npi", "disclaimer"}

        acq.live_channels["raw_counts"] = deque(list(acq.live_channels["raw_counts"])[-7999:], maxlen=8000)
        short = client.get("/api/v1/acquisition/live-analysis",
                           headers={"X-NeuroPulse-Patient-Code": "LIVE_PATIENT_01"})
        assert short.status_code == 200
        assert short.json()["quality_status"] == "INSUFFICIENT_DATA"
        assert short.json()["npi"]["npi_value"] is None

        wrong_code = client.get("/api/v1/acquisition/live-analysis",
                                headers={"X-NeuroPulse-Patient-Code": "LIVE_PATIENT_02"})
        assert wrong_code.status_code == 403
    finally:
        app.dependency_overrides.pop(current_local_user, None)
        (acq.is_streaming, acq.is_simulated, acq.active_session_id, acq.selected_sensor,
         acq.effective_sample_rate, acq.start_stream_time, acq.analysis_channel,
         acq.live_channels["raw_counts"]) = prior


def test_automatic_stop_finalizes_only_the_matching_active_session(monkeypatch):
    calls = []
    prior_streaming, prior_session = acq.is_streaming, acq.active_session_id

    async def fake_stop(request, actor):
        calls.append((request.client.host, actor.role))

    monkeypatch.setattr(backend_main, "AUTO_STOP_SECONDS", 0)
    monkeypatch.setattr(backend_main, "stop_acquisition", fake_stop)
    try:
        acq.is_streaming = True
        acq.active_session_id = "session-auto-stop"
        asyncio.run(backend_main._auto_stop_after("session-auto-stop"))
        assert calls == [("127.0.0.1", "admin")]

        calls.clear()
        acq.active_session_id = "another-session"
        asyncio.run(backend_main._auto_stop_after("session-auto-stop"))
        assert calls == []
    finally:
        acq.is_streaming, acq.active_session_id = prior_streaming, prior_session
