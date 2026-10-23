"""Persist formula evaluation results separately from audit events."""
from alembic import op
import sqlalchemy as sa

revision = "0005_algorithm_evaluations"
down_revision = "0004_algorithm_formulas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "algorithm_evaluations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("formula_id", sa.String(), nullable=False),
        sa.Column("formula_version", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("tbr", sa.Float(), nullable=True),
        sa.Column("quality_status", sa.String(), nullable=False),
        sa.Column("npi_value", sa.Float(), nullable=True),
        sa.Column("parameters_snapshot", sa.Text(), nullable=False),
        sa.Column("source_metadata", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_algorithm_evaluations_formula_id", "algorithm_evaluations", ["formula_id"])
    op.create_index("ix_algorithm_evaluations_session_id", "algorithm_evaluations", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_algorithm_evaluations_session_id", table_name="algorithm_evaluations")
    op.drop_index("ix_algorithm_evaluations_formula_id", table_name="algorithm_evaluations")
    op.drop_table("algorithm_evaluations")
