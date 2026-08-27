"""Add audio metadata to detection_cases and engine_type to detection_results

Revision ID: 002_metadata
Revises: 001_initial
Create Date: 2026-08-25 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "002_metadata"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add audio metadata columns to detection_cases
    with op.batch_alter_table("detection_cases") as batch_op:
        batch_op.add_column(sa.Column("file_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("sample_rate", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("channels", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_detection_cases_file_hash"), ["file_hash"], unique=False)

    # 2. Add engine_type column to detection_results with temporary server_default to populate pre-existing rows
    with op.batch_alter_table("detection_results") as batch_op:
        batch_op.add_column(
            sa.Column("engine_type", sa.String(length=50), nullable=False, server_default="mock")
        )
        batch_op.create_index(batch_op.f("ix_detection_results_engine_type"), ["engine_type"], unique=False)
        # Drop server_default so future application writes must supply engine_type explicitly
        batch_op.alter_column("engine_type", server_default=None)


def downgrade() -> None:
    # Revert engine_type on detection_results
    with op.batch_alter_table("detection_results") as batch_op:
        batch_op.drop_index(batch_op.f("ix_detection_results_engine_type"))
        batch_op.drop_column("engine_type")

    # Revert audio metadata on detection_cases
    with op.batch_alter_table("detection_cases") as batch_op:
        batch_op.drop_index(batch_op.f("ix_detection_cases_file_hash"))
        batch_op.drop_column("channels")
        batch_op.drop_column("sample_rate")
        batch_op.drop_column("file_hash")
