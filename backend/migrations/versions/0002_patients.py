"""Add local patient profiles and code lookup.

Revision ID: 0002_patients
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_patients"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("patient_code", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("chromosome_marker", sa.String(), nullable=False),
        sa.Column("age_band", sa.String(), nullable=False),
        sa.Column("medical_history", sa.Text(), nullable=True),
        sa.Column("family_history", sa.Text(), nullable=True),
        sa.Column("diet", sa.String(), nullable=True),
        sa.Column("retain_indefinitely", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("retention_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_patients_patient_code", "patients", ["patient_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_patients_patient_code", table_name="patients")
    op.drop_table("patients")
