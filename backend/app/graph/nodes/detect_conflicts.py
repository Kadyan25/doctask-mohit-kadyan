import json
from collections import defaultdict

from app.db.models import Conflict, Document, PendingReview
from app.db.session import SessionLocal
from app.graph.state import PipelineState


def detect_conflicts(state: PipelineState) -> PipelineState:
    """Rule-based, deterministic conflict detection over the facts extracted
    so far — deliberately explainable rather than another opaque model call.
    Each conflict cites the exact facts/locations it came from.
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

        by_doc = defaultdict(list)
        for f in facts:
            by_doc[f["document_id"]].append(f)

        def period_of(doc_id: str) -> str | None:
            return next((f["value"] for f in by_doc[doc_id] if f["fact_type"] == "period"), None)

        status_docs = sorted(
            (d for d in by_doc if any(f["fact_type"] == "status" for f in by_doc[d])),
            key=lambda d: period_of(d) or "",
        )
        meeting_docs = sorted(
            (
                d
                for d in by_doc
                if any(f["fact_type"] in ("blocker", "decision", "action_item") for f in by_doc[d])
            ),
            key=lambda d: period_of(d) or "",
        )

        # 1. status-vs-blocker: same period, status says "on track" but a blocker exists
        for status_doc in status_docs:
            period = period_of(status_doc)
            status_fact = next((f for f in by_doc[status_doc] if f["fact_type"] == "status"), None)
            if not status_fact or "on track" not in status_fact["value"].lower():
                continue
            for meeting_doc in meeting_docs:
                if period_of(meeting_doc) != period:
                    continue
                blocker_fact = next((f for f in by_doc[meeting_doc] if f["fact_type"] == "blocker"), None)
                if blocker_fact:
                    conflicts.append(
                        {
                            "conflict_type": "status_vs_blocker",
                            "description": (
                                f'Status report for {period} says "{status_fact["value"]}" but '
                                f'meeting notes for the same period record an open blocker: '
                                f'"{blocker_fact["value"]}"'
                            ),
                            "citations": [status_fact["citation_location"], blocker_fact["citation_location"]],
                        }
                    )

        # 2. stalled progress: identical percent-complete across consecutive status reports
        percent_sequence = [
            (period_of(d), next(f for f in by_doc[d] if f["fact_type"] == "percent_complete"))
            for d in status_docs
            if any(f["fact_type"] == "percent_complete" for f in by_doc[d])
        ]
        for i in range(1, len(percent_sequence)):
            prev_period, prev_fact = percent_sequence[i - 1]
            cur_period, cur_fact = percent_sequence[i]
            if prev_fact["value"] == cur_fact["value"]:
                conflicts.append(
                    {
                        "conflict_type": "stalled_progress",
                        "description": (
                            f'Percent-complete stayed at {cur_fact["value"]}% from {prev_period} to '
                            f"{cur_period} with no explanation — possible stalled progress reported as steady."
                        ),
                        "citations": [prev_fact["citation_location"], cur_fact["citation_location"]],
                    }
                )

        # 3. undocumented scope change: a decision fact reads like a scope change,
        # and no change_request document has been processed in this pile yet
        change_request_docs = [d for d in by_doc if documents.get(d) and documents[d].doc_type == "change_request"]
        if not change_request_docs:
            for meeting_doc in meeting_docs:
                for f in by_doc[meeting_doc]:
                    if f["fact_type"] != "decision":
                        continue
                    if "scope" in f["value"].lower() or "sync" in f["value"].lower():
                        conflicts.append(
                            {
                                "conflict_type": "undocumented_scope_change",
                                "description": (
                                    f'Meeting notes record a scope decision — "{f["value"]}" — with no '
                                    f"matching change request on file yet. The project plan was never updated."
                                ),
                                "citations": [f["citation_location"]],
                            }
                        )

        # 4. stale action items: same action-item id still "open" across 3+ meetings
        action_item_occurrences = defaultdict(list)
        for d in meeting_docs:
            for f in by_doc[d]:
                if f["fact_type"] == "action_item":
                    value = json.loads(f["value"])
                    action_item_occurrences[f["key"]].append((period_of(d), value, f["citation_location"]))
        for item_id, occurrences in action_item_occurrences.items():
            still_open = [o for o in occurrences if o[1]["status"] == "open"]
            if len(still_open) >= 3:
                conflicts.append(
                    {
                        "conflict_type": "stale_action_item",
                        "description": (
                            f'Action item {item_id} ("{still_open[0][1]["description"]}") has stayed '
                            f"open across {len(still_open)} consecutive meetings with no escalation."
                        ),
                        "citations": [o[2] for o in still_open],
                    }
                )

        # 5. embedded instructions: always surfaced, never obeyed (behavior #8)
        for f in facts:
            if f["fact_type"] == "suspicious_instruction":
                conflicts.append(
                    {
                        "conflict_type": "embedded_instruction_attempt",
                        "description": (
                            f'Document contains text resembling an instruction aimed at an AI reviewer: '
                            f'"{f["value"][:200]}". Treated as data, not followed.'
                        ),
                        "citations": [f["citation_location"]],
                    }
                )

        for c in conflicts:
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
