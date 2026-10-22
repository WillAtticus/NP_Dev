import sqlite3
import zipfile
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine

from backend.app.db.database import Base
from backend.app.db.models import AuthSession, LocalUser
from scripts.neuropulse_backup import create_backup, restore_backup


def test_backup_restore_verifies_files_and_revokes_saved_auth_sessions(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    engine = create_engine(f"sqlite:///{data_dir / 'neuropulse.db'}")
    Base.metadata.create_all(bind=engine)
    from sqlalchemy.orm import Session as ORMSession
    with ORMSession(engine) as db:
        user = LocalUser(id="local-admin", username="admin", password_hash="scrypt-placeholder", role="admin")
        db.add(user)
        db.add(AuthSession(id="auth-active", user_id=user.id, token_hash="a" * 64,
                           expires_at=datetime.now(timezone.utc).replace(tzinfo=None)))
        db.commit()
    engine.dispose()

    raw_path = data_dir / "sessions" / "session-001" / "raw.json"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text('{"provenance":"simulated","samples":[1,2,3]}', encoding="utf-8")
    backup_path = tmp_path / "exports" / "snapshot.zip"
    manifest = create_backup(data_dir, backup_path)
    assert set(manifest["files"]) == {"neuropulse.db", "sessions/session-001/raw.json"}

    restored = tmp_path / "restored-data"
    result = restore_backup(backup_path, restored)
    assert result["verified_file_count"] == 2
    assert result["auth_sessions_revoked"] is True
    assert (restored / "sessions/session-001/raw.json").read_bytes() == raw_path.read_bytes()
    with sqlite3.connect(restored / "neuropulse.db") as db:
        assert db.execute("SELECT revoked_at IS NOT NULL FROM auth_sessions WHERE id='auth-active'").fetchone()[0] == 1

    with pytest.raises(FileExistsError):
        restore_backup(backup_path, restored)
    with pytest.raises(ValueError, match="outside"):
        create_backup(data_dir, data_dir / "backup.zip")


def test_restore_rejects_checksum_mismatch_without_creating_destination(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    with sqlite3.connect(data_dir / "neuropulse.db") as db:
        db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        db.commit()
    backup_path = tmp_path / "backup.zip"
    create_backup(data_dir, backup_path)

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(backup_path, "r") as source, zipfile.ZipFile(tampered, "w") as target:
        for entry in source.infolist():
            content = source.read(entry.filename)
            if entry.filename == "payload/neuropulse.db":
                content = content + b"tamper"
            target.writestr(entry.filename, content)

    destination = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="Checksum mismatch"):
        restore_backup(tampered, destination)
    assert not destination.exists()
