from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_simulate_and_analyse_endpoint():
    res = client.post("/api/v1/simulate-and-analyse", json={
        "sensor_type": "PIEZO_LDT0_028K",
        "profile_id": "piezo_butterworth_1_20_default",
        "tremor_freq_hz": 5.0,
        "duration_sec": 8.0
    })
    assert res.status_code == 200
    data = res.json()
    assert "analysis" in data
    assert data["analysis"]["tbr"] is not None
    assert data["analysis"]["npi"]["npi_value"] is not None

def test_algorithms_list():
    res = client.get("/api/v1/algorithms")
    assert res.status_code == 200
    assert len(res.json()) >= 1

def test_session_api_crud():
    # 1. Create session
    create_res = client.post("/api/v1/sessions", json={
        "sensor_type": "PIEZO_LDT0_028K",
        "profile_id": "piezo_butterworth_1_20_default",
        "provenance": "simulated",
        "participant_code": "TEST_P01"
    })
    assert create_res.status_code == 200
    created = create_res.json()
    session_id = created["id"]
    assert created["sensor_type"] == "PIEZO_LDT0_028K"
    assert created["status"] == "created"

    # 2. List sessions
    list_res = client.get("/api/v1/sessions")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert "sessions" in list_data
    assert "stats" in list_data
    assert any(s["id"] == session_id for s in list_data["sessions"])

    # 3. Get session
    get_res = client.get(f"/api/v1/sessions/{session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == session_id

    # 4. Update session
    patch_res = client.patch(f"/api/v1/sessions/{session_id}", json={
        "status": "completed",
        "tbr": 0.55,
        "npi_value": 72.5,
        "npi_category": "in_reference_range",
        "quality_status": "VALID_FOR_ANALYSIS",
        "duration_sec": 8.0,
    })
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["status"] == "completed"
    assert patched["tbr"] == 0.55
    assert patched["npi_value"] == 72.5

    # 5. Stats summary
    stats_res = client.get("/api/v1/sessions/stats/summary")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "total_count" in stats or "total" in stats

    # 6. Delete session
    del_res = client.delete(f"/api/v1/sessions/{session_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # 7. Check 404
    get_del = client.get(f"/api/v1/sessions/{session_id}")
    assert get_del.status_code == 404


if __name__ == "__main__":
    test_health()
    test_simulate_and_analyse_endpoint()
    test_algorithms_list()
    test_session_api_crud()
    print("[+] All API endpoints tested successfully!")
