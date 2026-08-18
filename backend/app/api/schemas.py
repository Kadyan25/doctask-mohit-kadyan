import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class PileCreate(BaseModel):
    name: str
    watch_folder_path: Optional[str] = None


class PileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    watch_folder_path: Optional[str]
    created_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pile_id: uuid.UUID
    filename: str
    mime_type: str
    doc_type: Optional[str]
    content_hash: str
    ingested_at: datetime


class RunCreate(BaseModel):
    """llm_provider overrides LLM_PROVIDER for this run only — omit (or send
    null) to use the env-configured default."""

    llm_provider: Optional[str] = None


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pile_id: uuid.UUID
    status: str
    thread_id: str
    started_at: datetime
    completed_at: Optional[datetime]


class PendingReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pile_id: uuid.UUID
    item_type: str
    payload: Any
    status: str
    reviewer: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime


class ReviewDecision(BaseModel):
    reviewer: Optional[str] = None


class RuleCreate(BaseModel):
    rule_text: str
    source: Optional[str] = None


class RuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pile_id: uuid.UUID
    rule_text: str
    source: Optional[str]
    created_at: datetime


class DeliverableSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    section_key: str
    content: str
    version: int
    citations: list[str]
    updated_at: datetime


class CostStageBreakdown(BaseModel):
    stage_name: str
    total_duration_ms: int
    call_count: int
    tokens_used: Optional[int] = None
    cost_estimate: Optional[float] = None


class CostReport(BaseModel):
    run_id: uuid.UUID
    total_duration_ms: int
    stages: list[CostStageBreakdown]


class ChangelogEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    section_key: str
    change_summary: str
    source_document_id: Optional[uuid.UUID]
    changed_at: datetime
