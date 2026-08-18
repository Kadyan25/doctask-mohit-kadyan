from typing import Optional, TypedDict


class PipelineState(TypedDict, total=False):
    """Shared LangGraph state. Fields beyond Phase 0's placeholder nodes
    (facts/conflicts/deliverable/findings/pending_review_ids) are defined
    now so Phase 1+ nodes can build directly on this schema."""

    pile_id: str
    run_id: str
    llm_provider: Optional[str]  # per-run override of LLM_PROVIDER; None means use the env default
    document_ids: list[str]
    parsed_documents: dict  # document_id -> {filename, mime_type, lines: [{location, text}]}
    doc_types: dict  # document_id -> classified type string
    facts: list[dict]
    conflicts: list[dict]
    deliverable: dict
    findings: list[dict]
    pending_review_ids: list[str]
    stage: str
    stages_completed: list[str]
    error: Optional[str]
