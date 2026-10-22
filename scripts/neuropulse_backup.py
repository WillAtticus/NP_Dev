"""Create and restore integrity-checked, local NeuroPulse data archives."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Dict


FORMAT_VERSION = 1
DATABASE_NAME = "neuropulse.db"
MANIFEST_NAME = "manifest.json"
PAYLOAD_PREFIX = "payload/"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(data_dir: Path, output: Path) -> Dict[str, object]:
    source = data_dir.resolve()
    destination = output.resolve()
    source_db = source / DATABASE_NAME
    if not source_db.is_file():
        raise FileNotFoundError(f"NeuroPulse database not found: {source_db}")
    if destination == source or source in destination.parents:
        raise ValueError("Backup archive must be stored outside the source data directory.")
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing backup: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="neuropulse-backup-") as temp_name:
        temp_root = Path(temp_name)
        snapshot_db = temp_root / DATABASE_NAME
        source_connection = sqlite3.connect(source_db)
        snapshot_connection = sqlite3.connect(snapshot_db)
        try:
            source_connection.backup(snapshot_connection)
        finally:
            snapshot_connection.close()
            source_connection.close()

        payload_files = {DATABASE_NAME: snapshot_db}
        sessions_dir = source / "sessions"
        if sessions_dir.exists():
            if sessions_dir.is_symlink():
                raise ValueError(f"Symlinks are not supported in session storage: {sessions_dir}")
            for item in sorted(sessions_dir.rglob("*")):
                if item.is_symlink():
                    raise ValueError(f"Symlinks are not supported in session storage: {item}")
                if item.is_file():
                    relative = item.relative_to(source).as_posix()
                    payload_files[relative] = item

        manifest = {
            "format": "neuropulse-local-backup",
            "format_version": FORMAT_VERSION,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "files": {name: _sha256(path) for name, path in sorted(payload_files.items())},
        }
        created_by_this_call = False
        try:
            with destination.open("xb") as archive_stream:
                created_by_this_call = True
                with zipfile.ZipFile(archive_stream, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr(MANIFEST_NAME, json.dumps(manifest, sort_keys=True, indent=2))
                    for name, path in sorted(payload_files.items()):
                        archive.write(path, PAYLOAD_PREFIX + name)
            with zipfile.ZipFile(destination, "r") as archive:
                for name, expected_hash in manifest["files"].items():
                    digest = hashlib.sha256()
                    with archive.open(PAYLOAD_PREFIX + name, "r") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                    if digest.hexdigest() != expected_hash:
                        raise ValueError(f"Source changed while the backup was being created: {name}")
        except Exception:
            if created_by_this_call:
                destination.unlink(missing_ok=True)
            raise
    return manifest


def _safe_archive_payload_name(name: str) -> str:
    if not name.startswith(PAYLOAD_PREFIX):
        raise ValueError(f"Unexpected archive entry: {name}")
    relative = PurePosixPath(name[len(PAYLOAD_PREFIX):])
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"Unsafe archive entry path: {name}")
    normalized = relative.as_posix()
    if normalized != DATABASE_NAME and not normalized.startswith("sessions/"):
        raise ValueError(f"Unexpected backup payload path: {name}")
    return normalized


def restore_backup(archive_path: Path, destination: Path) -> Dict[str, object]:
    archive_path = archive_path.resolve()
    destination = destination.resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(f"Backup archive not found: {archive_path}")
    if destination.exists():
        raise FileExistsError(f"Restore destination already exists; refusing to overwrite: {destination}")
    if not destination.parent.exists():
        raise FileNotFoundError(f"Restore parent directory does not exist: {destination.parent}")

    with zipfile.ZipFile(archive_path, "r") as archive:
        entries = archive.infolist()
        filenames = [entry.filename for entry in entries]
        if len(filenames) != len(set(filenames)):
            raise ValueError("Backup archive contains duplicate paths.")
        if any(name != MANIFEST_NAME and not name.startswith(PAYLOAD_PREFIX) for name in filenames):
            raise ValueError("Backup archive contains unrecognized entries.")
        if MANIFEST_NAME not in filenames:
            raise ValueError("Backup manifest is missing.")
        manifest = json.loads(archive.read(MANIFEST_NAME))
        if manifest.get("format") != "neuropulse-local-backup" or manifest.get("format_version") != FORMAT_VERSION:
            raise ValueError("Unsupported NeuroPulse backup format.")
        expected: Dict[str, str] = manifest.get("files", {})
        payload_entries = { _safe_archive_payload_name(name): name for name in filenames if name.startswith(PAYLOAD_PREFIX) }
        if set(payload_entries) != set(expected) or DATABASE_NAME not in expected:
            raise ValueError("Backup archive contents do not match the manifest.")

        temp_restore = Path(tempfile.mkdtemp(prefix=".neuropulse-restore-", dir=destination.parent))
        try:
            for relative, archive_name in payload_entries.items():
                output_file = temp_restore.joinpath(*PurePosixPath(relative).parts)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with archive.open(archive_name, "r") as source_stream, output_file.open("xb") as output_stream:
                    for chunk in iter(lambda: source_stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                        output_stream.write(chunk)
                if digest.hexdigest() != expected[relative]:
                    raise ValueError(f"Checksum mismatch for backup file: {relative}")

            # Never restore authentication sessions from an older snapshot.
            db_path = temp_restore / DATABASE_NAME
            connection = sqlite3.connect(db_path)
            try:
                has_auth_sessions = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='auth_sessions'"
                ).fetchone()
                if has_auth_sessions:
                    connection.execute("UPDATE auth_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE revoked_at IS NULL")
                    connection.commit()
            finally:
                connection.close()

            if destination.exists():
                raise FileExistsError(f"Restore destination appeared during restore: {destination}")
            os.rename(temp_restore, destination)
            return {
                "restored_to": str(destination),
                "verified_file_count": len(expected),
                "auth_sessions_revoked": bool(has_auth_sessions),
                "backup_created_at_utc": manifest.get("created_at_utc"),
            }
        except Exception:
            shutil.rmtree(temp_restore, ignore_errors=True)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up or restore NeuroPulse local data.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup_parser = subparsers.add_parser("backup", help="Create a new integrity-checked archive.")
    backup_parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("DATA_DIR", "data")))
    backup_parser.add_argument("--output", type=Path, required=True)
    restore_parser = subparsers.add_parser("restore", help="Restore into a new, non-existing data directory.")
    restore_parser.add_argument("--archive", type=Path, required=True)
    restore_parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "backup":
        result = create_backup(args.data_dir, args.output)
        print(json.dumps({"archive": str(args.output.resolve()), "file_count": len(result["files"]),
                          "created_at_utc": result["created_at_utc"]}, indent=2))
    else:
        print(json.dumps(restore_backup(args.archive, args.destination), indent=2))


if __name__ == "__main__":
    main()
