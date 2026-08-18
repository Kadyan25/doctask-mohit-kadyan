from app.db.models import Document
from app.db.session import SessionLocal
from app.graph.state import PipelineState
from app.services.document_parser import parsed_document_from_dict
from app.services.llm_client import get_llm_client


def classify(state: PipelineState) -> PipelineState:
    client = get_llm_client(state.get("llm_provider"))
    parsed_documents = state.get("parsed_documents", {})
    doc_types: dict[str, str] = {}

    with SessionLocal() as db:
        for doc_id, parsed_dict in parsed_documents.items():
            parsed = parsed_document_from_dict(parsed_dict)
            doc_type = client.classify_document(parsed)
            doc_types[doc_id] = doc_type

            document = db.get(Document, doc_id)
            if document is not None:
                document.doc_type = doc_type
        db.commit()

    stages_completed = list(state.get("stages_completed", []))
    stages_completed.append("classify")
    return {**state, "doc_types": doc_types, "stage": "classify_complete", "stages_completed": stages_completed}
