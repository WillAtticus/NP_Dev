"""Alembic migration runner for the local SQLite metadata database."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

try:
    from . import models  # noqa: F401
    from .database import Base
except ImportError:
    try:
        from app.db import models  # noqa: F401
        from app.db.database import Base
    except ImportError:
        from backend.app.db import models  # noqa: F401
        from backend.app.db.database import Base


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _PROJECT_ROOT / "backend" / "alembic.ini"


def _validate_unversioned_schema(connection) -> None:
    """Reject unknown schema shapes before the first migration touches data.

    Older application versions created tables with ``create_all`` but did not
    record a schema version. Existing tables may be adopted only when their
    column names match the current baseline. Extra and partial columns require
    a deliberate migration rather than an automatic guess.
    """
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names()) - {"sqlite_sequence"}
    if not table_names or "alembic_version" in table_names:
        return

    expected_tables = Base.metadata.tables
    for table_name in sorted(table_names):
        expected = expected_tables.get(table_name)
        if expected is None:
            raise RuntimeError(
                f"Cannot migrate unversioned database: unexpected table '{table_name}'. "
                "Back up the database and create a reviewed migration before starting NeuroPulse."
            )
        actual_column_rows = {column["name"]: column for column in inspector.get_columns(table_name)}
        actual_columns = set(actual_column_rows)
        expected_columns = set(expected.columns.keys())
        if actual_columns != expected_columns:
            missing = sorted(expected_columns - actual_columns)
            extra = sorted(actual_columns - expected_columns)
            raise RuntimeError(
                f"Cannot migrate unversioned table '{table_name}': column mismatch "
                f"(missing={missing}, extra={extra}). Back up the database and create a "
                "reviewed migration before starting NeuroPulse."
            )
        for expected_column in expected.columns:
            actual_column = actual_column_rows[expected_column.name]
            expected_type = expected_column.type.compile(dialect=connection.dialect).upper()
            actual_type = str(actual_column["type"]).upper()
            if (
                expected_type != actual_type
                or bool(actual_column["nullable"]) != bool(expected_column.nullable)
                or bool(actual_column.get("primary_key")) != bool(expected_column.primary_key)
            ):
                raise RuntimeError(
                    f"Cannot migrate unversioned table '{table_name}': column "
                    f"'{expected_column.name}' does not match the baseline type/nullability/key. "
                    "Back up the database and create a reviewed migration before starting NeuroPulse."
                )


def upgrade_database(target_engine: Engine) -> None:
    """Upgrade or safely adopt an existing database to the latest revision."""
    if not _ALEMBIC_INI.is_file():
        raise RuntimeError(f"Alembic configuration is missing: {_ALEMBIC_INI}")

    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_PROJECT_ROOT / "backend" / "migrations"))

    with target_engine.begin() as connection:
        table_names = set(inspect(connection).get_table_names())
        if table_names and "alembic_version" not in table_names:
            _validate_unversioned_schema(connection)
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

