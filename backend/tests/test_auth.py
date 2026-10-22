import os
import tempfile

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import main as backend_main
from backend.app.db.database import Base
from backend.app.db.database import get_db as original_get_db
from backend.app.db.models import LocalUser


def test_local_auth_bootstrap_roles_deactivation_and_logout(monkeypatch):
    temp_dir = tempfile.mkdtemp()
    engine = create_engine(f"sqlite:///{os.path.join(temp_dir, 'auth.db')}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    test_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def test_get_db():
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(backend_main, "get_db", test_get_db)
    monkeypatch.setattr(backend_main, "SessionLocal", test_session_local)
    backend_main.app.dependency_overrides[original_get_db] = test_get_db
    try:
        with TestClient(backend_main.app) as client:
            assert client.get("/api/v1/auth/status").json()["bootstrap_required"] is True
            boot = client.post("/api/v1/auth/bootstrap", json={
                "username": "PrimaryAdmin", "password": "Strong Local Password 123!",
            })
            assert boot.status_code == 200, boot.text
            admin_token = boot.json()["access_token"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}
            assert boot.json()["user"]["role"] == "admin"
            unsupported_baud = client.post("/api/v1/devices/connect", headers=admin_headers, json={
                "port": "SIMULATOR", "sensor_type": "PIEZO_LDT0_028K", "baud_rate": 921600,
            })
            assert unsupported_baud.status_code == 422
            assert client.get("/api/v1/sessions").status_code == 401
            assert client.post("/api/v1/auth/bootstrap", json={
                "username": "second-admin", "password": "Strong Local Password 456!",
            }).status_code == 409

            stored_user = test_session_local().query(LocalUser).filter_by(username="primaryadmin").one()
            assert "Strong Local Password" not in stored_user.password_hash
            assert stored_user.password_hash.startswith("scrypt$")

            created = client.post("/api/v1/auth/users", headers=admin_headers, json={
                "username": "reviewer_1", "password": "Reviewer Local Password 123!", "role": "reviewer",
            })
            assert created.status_code == 200, created.text
            reviewer_login = client.post("/api/v1/auth/login", json={
                "username": "reviewer_1", "password": "Reviewer Local Password 123!",
            })
            assert reviewer_login.status_code == 200
            reviewer_token = reviewer_login.json()["access_token"]
            reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}
            assert client.get("/api/v1/sessions", headers=reviewer_headers).status_code == 200
            assert client.post("/api/v1/devices/connect", headers=reviewer_headers, json={
                "port": "SIMULATOR", "sensor_type": "PIEZO_LDT0_028K",
            }).status_code == 403

            disabled = client.patch(f"/api/v1/auth/users/{created.json()['id']}/active",
                                    headers=admin_headers, json={"is_active": False})
            assert disabled.status_code == 200
            assert client.get("/api/v1/sessions", headers=reviewer_headers).status_code == 401
            assert client.post("/api/v1/auth/logout", headers=admin_headers).status_code == 200
            assert client.get("/api/v1/sessions", headers=admin_headers).status_code == 401
    finally:
        backend_main.app.dependency_overrides.clear()
        engine.dispose()
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
