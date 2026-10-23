"""Store reported sex separately from the patient-code marker.

Revision ID: 0003_patient_reported_sex
Revises: 0002_patients
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_patient_reported_sex"
down_revision = "0002_patients"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("reported_sex", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "reported_sex")
