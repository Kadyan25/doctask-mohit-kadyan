from app.db.models import ChangelogEntry
from app.db.session import SessionLocal
from app.graph.state import PipelineState


def changelog_entry(state: PipelineState) -> PipelineState:
    """Answers "what changed, when, because of which source": one entry per
    deliverable section that draft_deliverable actually changed this run —
    sections whose content_hash was unaffected by the new document produce no
    entry here, which is itself part of the proof they stayed untouched.
    """
    pile_id = state["pile_id"]
    deliverable = state.get("deliverable", {})
    new_document_ids = state.get("document_ids", [])
    source_document_id = new_document_ids[0] if new_document_ids else None

    with SessionLocal() as db:
        for section_key, info in deliverable.items():
            if info.get("changed"):
                db.add(
                    ChangelogEntry(
                        pile_id=pile_id,
                        section_key=section_key,
                        change_summary=f"Section '{section_key}' updated following a new document arrival.",
                        source_document_id=source_document_id,
                    )
                )
        db.commit()

    stages_completed = list(state.get("stages_completed", []))
    stages_completed.append("changelog_entry")
    return {**state, "stage": "changelog_entry_complete", "stages_completed": stages_completed}
