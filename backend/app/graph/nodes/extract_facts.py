from app.db.models import Fact
from app.db.session import SessionLocal
from app.graph.state import PipelineState
from app.services.document_parser import parsed_document_from_dict
from app.services.llm_client import (
    detect_embedded_instructions,
    get_llm_client,
    merge_injection_facts,
)


def extract_facts(state: PipelineState) -> PipelineState:
    client = get_llm_client(state.get("llm_provider"))
    parsed_documents = state.get("parsed_documents", {})
    doc_types = state.get("doc_types", {})
    pile_id = state["pile_id"]
    all_facts: list[dict] = []

    with SessionLocal() as db:
        for doc_id, parsed_dict in parsed_documents.items():
            parsed = parsed_document_from_dict(parsed_dict)
            doc_type = doc_types.get(doc_id, "unknown")
            extracted = client.extract_facts(parsed, doc_type)
            # Deterministic injection backstop for every provider (Behavior #8):
            # a real model that misses an embedded instruction must not leave it
            # unflagged. Deduped against any suspicious_instruction facts the
            # provider already emitted, so the fake client isn't double-counted.
            extracted = merge_injection_facts(extracted, detect_embedded_instructions(parsed))
            for fact in extracted:
                row = Fact(
                    document_id=doc_id,
                    pile_id=pile_id,
                    fact_type=fact["fact_type"],
                    key=fact["key"],
                    value=fact["value"],
                    citation_location=fact["citation_location"],
                )
                db.add(row)
                all_facts.append({**fact, "document_id": doc_id})
        db.commit()

    stages_completed = list(state.get("stages_completed", []))
    stages_completed.append("extract_facts")
    return {**state, "facts": all_facts, "stage": "extract_facts_complete", "stages_completed": stages_completed}
