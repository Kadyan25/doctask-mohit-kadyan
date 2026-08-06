import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Pile(Base):
    __tablename__ = "piles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    watch_folder_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    pile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("piles.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    raw_storage_path: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    doc_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(1536), nullable=False)


class Fact(Base):
    __tablename__ = "facts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    pile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("piles.id"), nullable=False)
    fact_type: Mapped[str] = mapped_column(String, nullable=False)
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    citation_location: Mapped[str] = mapped_column(String, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conflict(Base):
    __tablename__ = "conflicts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    pile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("piles.id"), nullable=False)
    fact_ids: Mapped[list] = mapped_column(ARRAY(String), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = _uuid_pk()
    pile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("piles.id"), nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    pile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("piles.id"), nullable=False)
    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rules.id"), nullable=False)
    citation: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeliverableSection(Base):
    __tablename__ = "deliverable_sections"

    id: Mapped[uuid.UUID] = _uuid_pk()
    pile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("piles.id"), nullable=False)
    section_key: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    citations: Mapped[list] = mapped_column(ARRAY(String), nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChangelogEntry(Base):
    __tablename__ = "changelog"

    id: Mapped[uuid.UUID] = _uuid_pk()
    pile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("piles.id"), nullable=False)
    section_key: Mapped[str] = mapped_column(String, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PendingReview(Base):
    __tablename__ = "pending_review"

    id: Mapped[uuid.UUID] = _uuid_pk()
    pile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("piles.id"), nullable=False)
    item_type: Mapped[str] = mapped_column(String, nullable=False)  # conflict | finding | update
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")  # pending | approved | rejected
    reviewer: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    pile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("piles.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    thread_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class RunStageMetric(Base):
    __tablename__ = "run_stage_metrics"

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False)
    stage_name: Mapped[str] = mapped_column(String, nullable=False)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
