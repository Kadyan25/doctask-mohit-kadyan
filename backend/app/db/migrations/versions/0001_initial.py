"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "piles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("watch_folder_path", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pile_id", UUID(as_uuid=True), sa.ForeignKey("piles.id"), nullable=False),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("mime_type", sa.String, nullable=False),
        sa.Column("raw_storage_path", sa.String, nullable=False),
        sa.Column("content_hash", sa.String, nullable=False),
        sa.Column("doc_type", sa.String, nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
    )

    op.create_table(
        "facts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("pile_id", UUID(as_uuid=True), sa.ForeignKey("piles.id"), nullable=False),
        sa.Column("fact_type", sa.String, nullable=False),
        sa.Column("key", sa.String, nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("citation_location", sa.String, nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "conflicts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pile_id", UUID(as_uuid=True), sa.ForeignKey("piles.id"), nullable=False),
        sa.Column("fact_ids", ARRAY(sa.String), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pile_id", UUID(as_uuid=True), sa.ForeignKey("piles.id"), nullable=False),
        sa.Column("rule_text", sa.Text, nullable=False),
        sa.Column("source", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "findings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pile_id", UUID(as_uuid=True), sa.ForeignKey("piles.id"), nullable=False),
        sa.Column("rule_id", UUID(as_uuid=True), sa.ForeignKey("rules.id"), nullable=False),
        sa.Column("citation", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "deliverable_sections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pile_id", UUID(as_uuid=True), sa.ForeignKey("piles.id"), nullable=False),
        sa.Column("section_key", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("citations", ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "changelog",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pile_id", UUID(as_uuid=True), sa.ForeignKey("piles.id"), nullable=False),
        sa.Column("section_key", sa.String, nullable=False),
        sa.Column("change_summary", sa.Text, nullable=False),
        sa.Column("source_document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "pending_review",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pile_id", UUID(as_uuid=True), sa.ForeignKey("piles.id"), nullable=False),
        sa.Column("item_type", sa.String, nullable=False),
        sa.Column("payload", JSON, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("reviewer", sa.String, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pile_id", UUID(as_uuid=True), sa.ForeignKey("piles.id"), nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="running"),
        sa.Column("thread_id", sa.String, nullable=False, unique=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "run_stage_metrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("stage_name", sa.String, nullable=False),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("cost_estimate", sa.Float, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("run_stage_metrics")
    op.drop_table("runs")
    op.drop_table("pending_review")
    op.drop_table("changelog")
    op.drop_table("deliverable_sections")
    op.drop_table("findings")
    op.drop_table("rules")
    op.drop_table("conflicts")
    op.drop_table("facts")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("piles")
    op.execute("DROP EXTENSION IF EXISTS vector")
