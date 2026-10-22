"""Initial metadata schema for local NeuroPulse installations.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _create_table_if_missing(name, *columns, **kwargs):
    if not inspect(op.get_bind()).has_table(name):
        op.create_table(name, *columns, **kwargs)


def upgrade() -> None:
    # The migration runner validates unversioned tables before reaching here.
    _create_table_if_missing(
        "sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("study_id", sa.String()),
        sa.Column("participant_code", sa.String()),
        sa.Column("sensor_type", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("status", sa.String()),
        sa.Column("provenance", sa.String()),
        sa.Column("start_time", sa.DateTime()),
        sa.Column("end_time", sa.DateTime()),
        sa.Column("duration_sec", sa.Float()),
        sa.Column("sample_count", sa.Integer()),
        sa.Column("sample_rate_hz", sa.Float()),
        sa.Column("tbr", sa.Float()),
        sa.Column("npi_value", sa.Float()),
        sa.Column("npi_category", sa.String()),
        sa.Column("quality_status", sa.String()),
        sa.Column("quality_flags", sa.String()),
        sa.Column("dominant_freq_hz", sa.Float()),
        sa.Column("sha256_hash", sa.String()),
        sa.Column("notes", sa.Text()),
        sa.Column("raw_data_path", sa.String()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column("is_deleted", sa.Boolean()),
    )
    _create_table_if_missing(
        "devices",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("serial_port", sa.String()),
        sa.Column("baud_rate", sa.Integer()),
        sa.Column("sensor_type", sa.String(), nullable=False),
        sa.Column("firmware_version", sa.String()),
        sa.Column("protocol_version", sa.String()),
        sa.Column("is_simulator", sa.Boolean()),
        sa.Column("last_connected", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
    )
    _create_table_if_missing(
        "studies",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("protocol_version", sa.String()),
        sa.Column("description", sa.Text()),
        sa.Column("sensor_type", sa.String()),
        sa.Column("target_duration_sec", sa.Float()),
        sa.Column("tbr_min", sa.Float()),
        sa.Column("tbr_max", sa.Float()),
        sa.Column("created_at", sa.DateTime()),
    )
    _create_table_if_missing(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime()),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor", sa.String()),
        sa.Column("session_id", sa.String()),
        sa.Column("detail", sa.Text()),
    )
    _create_table_if_missing(
        "local_users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
    )
    if not inspect(op.get_bind()).has_index("local_users", "ix_local_users_username"):
        op.create_index("ix_local_users_username", "local_users", ["username"], unique=True)
    _create_table_if_missing(
        "auth_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
    )
    if not inspect(op.get_bind()).has_index("auth_sessions", "ix_auth_sessions_user_id"):
        op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)
    if not inspect(op.get_bind()).has_index("auth_sessions", "ix_auth_sessions_token_hash"):
        op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)


def downgrade() -> None:
    raise RuntimeError(
        "The initial schema downgrade is disabled to prevent deletion of local research metadata. "
        "Restore a verified backup to roll back an installation."
    )
