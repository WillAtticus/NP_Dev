import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.database import SessionLocal
from backend.app.db import crud

def test_export_and_benchmark_endpoints():
    client = TestClient(app)

    # 1. Test benchmark import
    synthetic_samples = list(2048.0 + 250.0 * np.sin(2 * np.pi * 5.0 * np.linspace(0, 4, 4000)))
    import_resp = client.post(
        "/api/v1/benchmark/import",
        json={
            "name": "TEST_COHORT_A",
            "sensor_type": "PIEZO_LDT0_028K",
            "profile_id": "piezo_butterworth_1_20_default",
            "sample_rate_hz": 1000.0,
            "channel_name": "raw_counts",
            "samples": synthetic_samples,
            "participant_code": "BENCH_SUBJ_01",
            "notes": "Validation test for benchmark import",
        },
    )
    assert import_resp.status_code == 200
    import_body = import_resp.json()
    assert import_body["status"] == "imported"
    assert import_body["provenance"] == "imported_benchmark"
    assert import_body["sample_count"] == 4000
    session_id = import_body["session_id"]

    # 2. Test JSON export of the imported session
    export_json_resp = client.get(f"/api/v1/sessions/{session_id}/export?format=json")
    assert export_json_resp.status_code == 200
    json_body = export_json_resp.json()
    assert json_body["metadata"]["session_id"] == session_id
    assert json_body["metadata"]["provenance"] == "imported_benchmark"
    assert "raw_counts" in json_body["channels"]
    assert len(json_body["channels"]["raw_counts"]) == 4000

    # 3. Test CSV export
    export_csv_resp = client.get(f"/api/v1/sessions/{session_id}/export?format=csv")
    assert export_csv_resp.status_code == 200
    assert "text/csv" in export_csv_resp.headers["content-type"]
    csv_text = export_csv_resp.text
    assert "# NeuroPulse Session Export (CSV)" in csv_text
    assert "sample_index,raw_counts" in csv_text
