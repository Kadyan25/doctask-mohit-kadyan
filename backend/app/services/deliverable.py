import hashlib

from app.db.models import DeliverableSection


def upsert_section(db, pile_id: str, section_key: str, content: str, citations: list[str]):
    """Sectioned, not a blob: only this section's row changes, and only if its
    content actually changed (proven by hash comparison) — other sections stay
    byte-identical, which is what Movement 3's incremental updates depend on.
    Shared by Movement 1's draft_deliverable and Movement 2's produce_findings.
    """
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    existing = (
        db.query(DeliverableSection)
        .filter(DeliverableSection.pile_id == pile_id, DeliverableSection.section_key == section_key)
        .first()
    )
    if existing and existing.content_hash == content_hash:
        return existing, False
    if existing:
        existing.content = content
        existing.content_hash = content_hash
        existing.version += 1
        existing.citations = citations
        return existing, True
    section = DeliverableSection(
        pile_id=pile_id,
        section_key=section_key,
        content=content,
        content_hash=content_hash,
        version=1,
        citations=citations,
    )
    db.add(section)
    return section, True
