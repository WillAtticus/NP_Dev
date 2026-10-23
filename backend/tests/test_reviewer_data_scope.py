from fastapi.testclient import TestClient

from backend.app.db.models import LocalUser
from backend.app.main import app, current_local_user


def test_reviewer_can_export_and_delete_without_receiving_technical_data():
    client = TestClient(app)
    def use_mode(mode: str):
        app.dependency_overrides[current_local_user] = lambda: LocalUser(
            id=f"test-{mode}", username=f"test-{mode}", password_hash="", role=mode, is_active=True
        )

    use_mode("admin")
    created = client.post("/api/v1/sessions", json={
        "sensor_type": "PIEZO_LDT0_028K",
        "profile_id": "piezo_butterworth_1_20_default",
        "provenance": "simulated",
        "participant_code": "REVIEW_SCOPE_01",
    })
    assert created.status_code == 200
    session_id = created.json()["id"]

    updated = client.patch(f"/api/v1/sessions/{session_id}", json={
        "status": "completed",
        "npi_value": 72.0,
        "npi_category": "in_reference_range",
        "tbr": 0.5,
        "quality_status": "VALID_FOR_ANALYSIS",
        "sample_rate_hz": 1000.0,
        "sample_count": 8000,
        "sha256_hash": "test-hash",
        "raw_data_path": "private/raw.h5",
        "notes": "technical note",
    })
    assert updated.status_code == 200

    use_mode("reviewer")
    listed = client.get("/api/v1/sessions")
    assert listed.status_code == 200
    row = next(item for item in listed.json()["sessions"] if item["id"] == session_id)
    for field in ("sensor_type", "profile_id", "sample_rate_hz", "sample_count", "total_samples",
                  "sha256_hash", "raw_data_path", "notes"):
        assert field not in row
    assert row["npi_value"] == 72.0

    detail = client.get(f"/api/v1/sessions/{session_id}")
    assert detail.status_code == 200
    assert "sensor_type" not in detail.json()
    assert detail.json()["quality_status"] == "VALID_FOR_ANALYSIS"

    for path in ("/api/v1/devices/ports", "/api/v1/devices/status", "/api/v1/acquisition/status",
                 "/api/v1/acquisition/live-buffer", "/api/v1/processing/profiles"):
        response = client.get(path)
        assert response.status_code == 403, path

    studies = client.get("/api/v1/studies")
    assert studies.status_code == 200
    assert studies.json()
    for field in ("sensor_type", "tbr_min", "tbr_max"):
        assert field not in studies.json()[0]
    assert client.get("/api/v1/sessions/stats/summary").status_code == 200

    exported = client.get(f"/api/v1/sessions/{session_id}/export?format=json")
    assert exported.status_code == 200
    body = exported.json()
    assert body["metadata"]["npi_value"] == 72.0
    assert "channels" not in body
    assert not {"sensor_type", "profile_id", "sha256_hash", "raw_data_path"}.intersection(body["metadata"])

    csv = client.get(f"/api/v1/sessions/{session_id}/export?format=csv")
    assert csv.status_code == 200
    assert "npi_value" in csv.text
    assert "raw_counts" not in csv.text
    assert "sensor_type" not in csv.text

    try:
        deleted = client.delete(f"/api/v1/sessions/{session_id}")
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "deleted"
    finally:
        app.dependency_overrides.pop(current_local_user, None)
