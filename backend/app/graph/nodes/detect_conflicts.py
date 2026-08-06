from app.db.models import Conflict, Document, PendingReview
from app.db.session import SessionLocal
from app.graph.state import PipelineState
from app.services.fact_analysis import (
    find_embedded_instructions,
    find_stale_action_items,
    find_stalled_progress,
    find_status_vs_blocker,
    find_undocumented_scope_changes,
)


def detect_conflicts(state: PipelineState) -> PipelineState:
    """Rule-based, deterministic conflict detection over the facts extracted
    so far — deliberately explainable rather than another opaque model call.
    Each conflict cites the exact facts/locations it came from. The detection
    logic itself lives in app.services.fact_analysis, shared with Movement 2's
    rule-checking so the two movements can't quietly disagree.
    """
    facts = state.get("facts", [])
    pile_id = state["pile_id"]
    conflicts: list[dict] = []

    with SessionLocal() as db:
        doc_ids = {f["document_id"] for f in facts}
        documents = (
            {str(d.id): d for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()}
            if doc_ids
            else {}
        )
        change_request_doc_ids = {d for d in documents if documents[d].doc_type == "change_request"}

        for result in find_status_vs_blocker(facts):
            conflicts.append({**result, "conflict_type": "status_vs_blocker"})
        for result in find_stalled_progress(facts):
            conflicts.append({**result, "conflict_type": "stalled_progress"})
        for result in find_undocumented_scope_changes(facts, change_request_doc_ids):
            conflicts.append({**result, "conflict_type": "undocumented_scope_change"})
        for result in find_stale_action_items(facts):
            conflicts.append({**result, "conflict_type": "stale_action_item"})
        for result in find_embedded_instructions(facts):
            conflicts.append({**result, "conflict_type": "embedded_instruction_attempt"})

        # Dedup by description: detect_conflicts can run more than once against
        # a growing fact set (Movement 3 re-runs it on every new-document
        # arrival) — without this, every prior conflict would get re-inserted
        # and re-queued for review each time, not just genuinely new ones.
        existing_descriptions = {
            c.description for c in db.query(Conflict).filter(Conflict.pile_id == pile_id).all()
        }
        new_conflicts = [c for c in conflicts if c["description"] not in existing_descriptions]

        for c in new_conflicts:
            conflict_row = Conflict(pile_id=pile_id, fact_ids=[], description=c["description"], status="pending")
            db.add(conflict_row)
            db.flush()
            review_row = PendingReview(
                pile_id=pile_id,
                item_type="conflict",
                payload={
                    "description": c["description"],
                    "citations": c["citations"],
                    "conflict_type": c["conflict_type"],
                    "conflict_id": str(conflict_row.id),
                },
                status="pending",
            )
            db.add(review_row)
            c["conflict_id"] = str(conflict_row.id)
        db.commit()

    stages_completed = list(state.get("stages_completed", []))
    stages_completed.append("detect_conflicts")
    return {**state, "conflicts": conflicts, "stage": "detect_conflicts_complete", "stages_completed": stages_completed}
