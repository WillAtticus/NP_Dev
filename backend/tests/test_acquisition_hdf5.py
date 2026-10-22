import os
import shutil
import tempfile
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
import h5py
import numpy as np

from backend.app.services.acquisition.manager import AcquisitionManager
from backend.app.main import app
from fastapi.testclient import TestClient

def test_hdf5_storage_and_analysis():
    temp_dir = tempfile.mkdtemp()
    try:
        manager = AcquisitionManager(data_root=temp_dir)
        manager.is_simulated = True
        manager.selected_sensor = "PIEZO_LDT0_028K"

        # Start and inject fake samples
        session_id = "test-session-hdf5-001"
        manager.active_session_id = session_id
        manager.session_start_monotonic_us = 1000000
        manager.session_raw_samples = {
            "raw_counts": list(2048.0 + 300.0 * np.sin(2 * np.pi * 5.0 * np.linspace(0, 8, 8000)))
        }
        manager.total_samples_received = 8000
        manager.effective_sample_rate = 1000.0

        # Stop acquisition which persists session data
        res = manager.stop_acquisition()
        assert res["status"] == "streaming_stopped"
        assert res["saved_recording"] is not None

        session_dir = os.path.join(temp_dir, "sessions", session_id)
        raw_h5 = os.path.join(session_dir, "raw.h5")
        raw_json = os.path.join(session_dir, "raw.json")

        assert os.path.exists(raw_h5), "raw.h5 should exist"
        assert os.path.exists(raw_json), "raw.json should exist"

        # Verify HDF5 content
        with h5py.File(raw_h5, "r") as h5f:
            assert h5f.attrs["session_id"] == session_id
            assert h5f.attrs["sensor_type"] == "PIEZO_LDT0_028K"
            assert "channels" in h5f
            assert "raw_counts" in h5f["channels"]
            data = h5f["channels"]["raw_counts"][:]
            assert len(data) == 8000

        # Now test the API analysis endpoint loading from HDF5
        from backend.app import main as backend_main
        orig_data_root = backend_main.DATA_ROOT
        backend_main.DATA_ROOT = temp_dir
        try:
            client = TestClient(app)
            # Remove raw.json to prove it loads from raw.h5
            os.remove(raw_json)
            assert not os.path.exists(raw_json)

            response = client.post(
                "/api/v1/processing/analyse",
                json={
                    "session_id": session_id,
                    "profile_id": "piezo_butterworth_1_20_default",
                    "channel": "raw_counts",
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["session_id"] == session_id
            assert body["analysis"]["tbr"] > 0.4
            assert body["analysis"]["npi"]["npi_value"] is not None
        finally:
            backend_main.DATA_ROOT = orig_data_root
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_simulated_acquisition_creates_and_finalizes_session(monkeypatch):
    from backend.app import main as backend_main
    from backend.app.db.database import Base

    temp_dir = tempfile.mkdtemp()
    engine = create_engine(f"sqlite:///{os.path.join(temp_dir, 'test.db')}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    def test_get_db():
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    manager = AcquisitionManager(data_root=temp_dir)
    monkeypatch.setattr(backend_main, "DATA_ROOT", temp_dir)
    monkeypatch.setattr(backend_main, "SessionLocal", test_session_local)
    monkeypatch.setattr(backend_main, "get_db", test_get_db)
    monkeypatch.setattr(backend_main, "acq", manager)

    try:
        client = TestClient(app)
        connected = client.post("/api/v1/devices/connect", json={"port": "SIMULATOR", "sensor_type": "PIEZO_LDT0_028K"})
        assert connected.status_code == 200
        session_id = "integration-session-001"
        started = client.post("/api/v1/acquisition/start", json={
            "session_id": session_id,
            "sensor_type": "PIEZO_LDT0_028K",
            "profile_id": "piezo_butterworth_1_20_default",
            "participant_code": "TEST_PSEUDONYM",
            "study_id": "STUDY-PILOT-01",
        })
        assert started.status_code == 200, started.text
        time.sleep(0.05)

        stopped = client.post("/api/v1/acquisition/stop")
        assert stopped.status_code == 200, stopped.text
        payload = stopped.json()
        assert payload["saved_recording"]["session_id"] == session_id
        assert payload["session"]["status"] == "completed"
        assert payload["session"]["provenance"] == "simulated"
        assert payload["session"]["raw_data_path"]
        assert payload["session"]["sha256_hash"]
        assert os.path.exists(os.path.join(temp_dir, "sessions", session_id, "raw.h5"))
        assert client.get(f"/api/v1/sessions/{session_id}").json()["sample_count"] > 0
    finally:
        engine.dispose()
        shutil.rmtree(temp_dir, ignore_errors=True)
