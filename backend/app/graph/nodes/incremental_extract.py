from app.db.models import Fact
from app.db.session import SessionLocal
from app.graph.state import PipelineState
from app.services.document_parser import parsed_document_from_dict
from app.services.llm_client import get_llm_client


def incremental_extract(state: PipelineState) -> PipelineState:
    """Extracts facts from the newly-arrived document only — the expensive,
    LLM-driven work stays scoped to what's actually new. It then reloads the
    full current fact set (existing + new) from the database, a cheap local
    query, so downstream conflict detection and drafting see the complete
    picture without re-running extraction on anything already processed.
    """
    client = get_llm_client(state.get("llm_provider"))
    parsed_documents = state.get("parsed_documents", {})
    doc_types = state.get("doc_types", {})
    pile_id = state["pile_id"]

    with SessionLocal() as db:
        for doc_id, parsed_dict in parsed_documents.items():
            parsed = parsed_document_from_dict(parsed_dict)
            doc_type = doc_types.get(doc_id, "unknown")
            extracted = client.extract_facts(parsed, doc_type)
            for fact in extracted:
                db.add(
                    Fact(
                        document_id=doc_id,
                        pile_id=pile_id,
                        fact_type=fact["fact_type"],
                        key=fact["key"],
                        value=fact["value"],
                        citation_location=fact["citation_location"],
                    )
                )
        db.commit()

        all_facts = db.query(Fact).filter(Fact.pile_id == pile_id).all()
        facts = [
            {
                "document_id": str(f.document_id),
                "fact_type": f.fact_type,
                "key": f.key,
                "value": f.value,
                "citation_location": f.citation_location,
            }
            for f in all_facts
        ]

    stages_completed = list(state.get("stages_completed", []))
    stages_completed.append("incremental_extract")
    return {**state, "facts": facts, "stage": "incremental_extract_complete", "stages_completed": stages_completed}
