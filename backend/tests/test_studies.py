import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.database import init_db

def test_studies_api():
    init_db()
    with TestClient(app) as client:
        # 1. Get studies list (seeds default if empty)
        resp = client.get("/api/v1/studies")
        assert resp.status_code == 200
        studies = resp.json()
        assert len(studies) >= 1
        assert any(s["id"] == "STUDY-PILOT-01" for s in studies)

        # 2. Create custom study
        create_resp = client.post(
            "/api/v1/studies",
            json={
                "id": "STUDY-ADXL-COHORT",
                "name": "Nghiên cứu Gia tốc 3 Trục ADXL345",
                "protocol_version": "1.1.0",
                "description": "Nghiên cứu gia tốc vi rung với ODR 100 Hz",
                "sensor_type": "ADXL345",
                "target_duration_sec": 10.0,
                "tbr_min": 0.35,
                "tbr_max": 0.80,
            },
        )
        assert create_resp.status_code == 200
        study_data = create_resp.json()
        assert study_data["id"] == "STUDY-ADXL-COHORT"
        assert study_data["sensor_type"] == "ADXL345"
        assert study_data["target_duration_sec"] == 10.0
