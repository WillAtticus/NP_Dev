"""Persist experimental formula versions for reproducible research."""
from alembic import op
import sqlalchemy as sa

revision = "0004_algorithm_formulas"
down_revision = "0003_patient_reported_sex"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "algorithm_formulas",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("tbr_min", sa.Float(), nullable=False),
        sa.Column("tbr_max", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_algorithm_formulas_name_version", "algorithm_formulas", ["name", "version"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_algorithm_formulas_name_version", table_name="algorithm_formulas")
    op.drop_table("algorithm_formulas")
