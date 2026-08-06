import hashlib

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import DeliverableSection


def upsert_section(db, pile_id: str, section_key: str, content: str, citations: list[str]):
    """Sectioned, not a blob: only this section's row changes, and only if its
    content actually changed (proven by hash comparison) — other sections stay
    byte-identical, which is what Movement 3's incremental updates depend on.

    Atomic at the database level via INSERT ... ON CONFLICT DO UPDATE, keyed
    on the (pile_id, section_key) unique constraint — not a read-then-write.
    Two concurrent runs on the same pile racing to update the same section
    serialize through Postgres's own conflict handling instead of one
    silently clobbering the other's version bump.
    """
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    stmt = pg_insert(DeliverableSection).values(
        pile_id=pile_id,
        section_key=section_key,
        content=content,
        content_hash=content_hash,
        version=1,
        citations=citations,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["pile_id", "section_key"],
        set_={
            "content": stmt.excluded.content,
            "content_hash": stmt.excluded.content_hash,
            "version": DeliverableSection.version + 1,
            "citations": stmt.excluded.citations,
            "updated_at": func.now(),
        },
        where=(DeliverableSection.content_hash != stmt.excluded.content_hash),
    ).returning(DeliverableSection)

    row = db.execute(stmt).first()
    if row is not None:
        return row[0], True

    # Conflict happened but the WHERE excluded the update — content is
    # unchanged. Nothing to return but the current row; fetch it plainly.
    existing = (
        db.query(DeliverableSection)
        .filter(DeliverableSection.pile_id == pile_id, DeliverableSection.section_key == section_key)
        .first()
    )
    return existing, False
