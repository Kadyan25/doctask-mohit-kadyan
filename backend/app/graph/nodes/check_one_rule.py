from app.db.models import Document, Fact
from app.db.session import SessionLocal
from app.graph.examine_state import ExamineState
from app.services.llm_client import get_llm_client


def check_one_rule(state: ExamineState) -> dict:
    """One branch of the Send fan-out — runs once per rule, in parallel with
    every other rule's branch. Reads facts already extracted by Movement 1;
    Movement 2 never re-parses or re-extracts, it only re-examines."""
    client = get_llm_client()
    pile_id = state["pile_id"]
    rule = state["current_rule"]

    with SessionLocal() as db:
        fact_rows = db.query(Fact).filter(Fact.pile_id == pile_id).all()
        facts = [
            {
                "document_id": str(f.document_id),
                "fact_type": f.fact_type,
                "key": f.key,
                "value": f.value,
                "citation_location": f.citation_location,
            }
            for f in fact_rows
        ]
        change_request_doc_ids = {
            str(d.id)
            for d in db.query(Document)
            .filter(Document.pile_id == pile_id, Document.doc_type == "change_request")
            .all()
        }

    results = client.check_rule(rule["rule_text"], facts, change_request_doc_ids)
    findings = [{**r, "rule_id": rule["id"], "rule_text": rule["rule_text"]} for r in results]

    return {"findings": findings, "stages_completed": [f"check_rule:{rule['id']}"]}
