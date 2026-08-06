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


class DeliverableSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    section_key: str
    content: str
    version: int
    citations: list[str]
    updated_at: datetime


class ChangelogEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    section_key: str
    change_summary: str
    source_document_id: Optional[uuid.UUID]
    changed_at: datetime
