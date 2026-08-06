from app.db.models import Finding, PendingReview
from app.db.session import SessionLocal
from app.graph.examine_state import ExamineState
from app.services.deliverable import upsert_section


def produce_findings(state: ExamineState) -> dict:
    """Aggregates every check_one_rule branch's output. An honest "no
    findings" (behavior #5 — never bluffs) is a normal, valid outcome and is
    reported explicitly, distinct from "no rules configured yet."""
    pile_id = state["pile_id"]
    findings = state.get("findings", [])
    rules = state.get("rules", [])

    with SessionLocal() as db:
        for f in findings:
            finding_row = Finding(
                pile_id=pile_id,
                rule_id=f["rule_id"],
                citation=", ".join(f["citations"]),
                description=f["description"],
                status="pending",
            )
            db.add(finding_row)
            db.flush()
            db.add(
                PendingReview(
                    pile_id=pile_id,
                    item_type="finding",
                    payload={
                        "description": f["description"],
                        "citations": f["citations"],
                        "rule_text": f["rule_text"],
                        "finding_id": str(finding_row.id),
                    },
                    status="pending",
                )
            )

        if findings:
            lines = [f"- [{f['rule_text'][:60]}] {f['description']}" for f in findings]
            content = "# Compliance Findings\n\n" + "\n".join(lines)
            citations = [c for f in findings for c in f["citations"]]
        elif rules:
            content = f"# Compliance Findings\n\nNo findings — checked against {len(rules)} rule(s), clean corpus."
            citations = []
        else:
            content = "# Compliance Findings\n\nNo rules configured yet."
            citations = []

        upsert_section(db, pile_id, "compliance_findings", content, citations)
        db.commit()

    return {"stage": "produce_findings_complete", "stages_completed": ["produce_findings"]}
