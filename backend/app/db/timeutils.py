"""UTC clock helpers for the SQLite metadata store.

SQLite drops timezone metadata from SQLAlchemy ``DateTime`` values. Keep the
existing naive-UTC storage contract explicit while sourcing time from an
aware UTC clock (``datetime.utcnow`` is deprecated in newer Python versions).
"""
from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """Return the current UTC instant as a naive datetime for SQLite storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
