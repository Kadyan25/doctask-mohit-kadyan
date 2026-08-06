from app.db.models import Rule
from app.db.session import SessionLocal
from app.graph.examine_state import ExamineState


def load_rules(state: ExamineState) -> dict:
    pile_id = state["pile_id"]
    with SessionLocal() as db:
        rules = db.query(Rule).filter(Rule.pile_id == pile_id).all()
        rules_data = [{"id": str(r.id), "rule_text": r.rule_text} for r in rules]

    return {"rules": rules_data, "stage": "load_rules_complete", "stages_completed": ["load_rules"]}
