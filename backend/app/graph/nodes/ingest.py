from pathlib import Path

from app.db.models import Document
from app.db.session import SessionLocal
from app.graph.state import PipelineState
from app.services.document_parser import parse_document, parsed_document_to_dict


def ingest(state: PipelineState) -> PipelineState:
    """Parses each document from disk. Document rows themselves are created at
    upload time (before a run exists) — this node's job is to prove the files
    are actually readable before any LLM work is spent on them, and to make
    the parsed content available to the rest of the run."""
    document_ids = state.get("document_ids", [])
    parsed_documents: dict[str, dict] = {}
    errors: list[str] = []

    with SessionLocal() as db:
        for doc_id in document_ids:
            document = db.get(Document, doc_id)
            if document is None:
                errors.append(f"document {doc_id} not found")
                continue
            try:
                parsed = parse_document(Path(document.raw_storage_path))
            except Exception as exc:
                errors.append(f"{document.filename}: failed to parse ({exc})")
                continue
            parsed_documents[doc_id] = parsed_document_to_dict(parsed)

    stages_completed = list(state.get("stages_completed", []))
    stages_completed.append("ingest")
    return {
        **state,
        "parsed_documents": parsed_documents,
        "stage": "ingest_complete",
        "stages_completed": stages_completed,
        "error": "; ".join(errors) if errors else None,
    }
