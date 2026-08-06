from typing import Optional, TypedDict


class PipelineState(TypedDict, total=False):
    """Shared LangGraph state. Fields beyond Phase 0's placeholder nodes
    (facts/conflicts/deliverable/findings/pending_review_ids) are defined
    now so Phase 1+ nodes can build directly on this schema."""

    pile_id: str
    run_id: str
    document_ids: list[str]
    facts: list[dict]
    conflicts: list[dict]
    deliverable: dict
    findings: list[dict]
    pending_review_ids: list[str]
    stage: str
    stages_completed: list[str]
    error: Optional[str]
