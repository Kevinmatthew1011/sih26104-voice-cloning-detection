"""Initial schema for detection_cases and detection_results

Revision ID: 001_initial
Revises: 
Create Date: 2026-08-24 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create detection_cases table
    op.create_table(
        "detection_cases",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mime_type", sa.String(length=100), nullable=False, server_default="audio/wav"),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_detection_cases_id"), "detection_cases", ["id"], unique=False)
    op.create_index(op.f("ix_detection_cases_status"), "detection_cases", ["status"], unique=False)
    op.create_index(op.f("ix_detection_cases_created_at"), "detection_cases", ["created_at"], unique=False)

    # Create detection_results table
    op.create_table(
        "detection_results",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("detection_case_id", sa.String(length=36), nullable=False),
        sa.Column("prediction", sa.String(length=30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("processing_time_ms", sa.Integer(), nullable=False),
        sa.Column("attack_type", sa.String(length=100), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("spectral_artifacts", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["detection_case_id"],
            ["detection_cases.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("detection_case_id"),
    )
    op.create_index(op.f("ix_detection_results_id"), "detection_results", ["id"], unique=False)
    op.create_index(op.f("ix_detection_results_prediction"), "detection_results", ["prediction"], unique=False)
    op.create_index(op.f("ix_detection_results_risk_level"), "detection_results", ["risk_level"], unique=False)
    op.create_index(op.f("ix_detection_results_created_at"), "detection_results", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_detection_results_created_at"), table_name="detection_results")
    op.drop_index(op.f("ix_detection_results_risk_level"), table_name="detection_results")
    op.drop_index(op.f("ix_detection_results_prediction"), table_name="detection_results")
    op.drop_index(op.f("ix_detection_results_id"), table_name="detection_results")
    op.drop_table("detection_results")
    
    op.drop_index(op.f("ix_detection_cases_created_at"), table_name="detection_cases")
    op.drop_index(op.f("ix_detection_cases_status"), table_name="detection_cases")
    op.drop_index(op.f("ix_detection_cases_id"), table_name="detection_cases")
    op.drop_table("detection_cases")
