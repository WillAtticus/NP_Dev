import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from backend.app.db.migrations import upgrade_database
from backend.app.db.database import Base
from backend.app.db.models import Session


@pytest.fixture
def migration_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    try:
        yield engine
    finally:
        engine.dispose()


def test_empty_database_migrates_and_upgrade_is_repeatable(migration_engine):
    upgrade_database(migration_engine)
    upgrade_database(migration_engine)

    tables = set(inspect(migration_engine).get_table_names())
    assert {
        "sessions", "devices", "studies", "audit_events", "local_users",
        "auth_sessions", "patients", "alembic_version",
    } <= tables
    with migration_engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0002_patients"
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert differences == []


def test_unversioned_current_schema_is_adopted_without_losing_rows(migration_engine):
    Session.__table__.create(migration_engine)
    with migration_engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO sessions (id, sensor_type, profile_id, provenance) "
            "VALUES ('existing-session', 'PIEZO_LDT0_028K', 'piezo-profile', 'simulated')"
        ))

    upgrade_database(migration_engine)

    with migration_engine.connect() as connection:
        row = connection.execute(text("SELECT id FROM sessions")).one()
        assert row.id == "existing-session"
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0002_patients"
    assert "local_users" in inspect(migration_engine).get_table_names()


def test_unknown_unversioned_schema_is_refused_without_mutation(migration_engine):
    with migration_engine.begin() as connection:
        connection.execute(text("CREATE TABLE sessions (id TEXT PRIMARY KEY, obsolete TEXT)"))

    with pytest.raises(RuntimeError, match="column mismatch"):
        upgrade_database(migration_engine)

    assert inspect(migration_engine).get_table_names() == ["sessions"]
    with migration_engine.connect() as connection:
        columns = {row["name"] for row in inspect(connection).get_columns("sessions")}
    assert columns == {"id", "obsolete"}
