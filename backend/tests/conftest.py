import asyncio
import hashlib
import shutil
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete

from app.db.models import (
    ChangelogEntry,
    Conflict,
    DeliverableSection,
    Document,
    Fact,
    Finding,
    PendingReview,
    Pile,
    Rule,
    Run,
    RunStageMetric,
)
from app.db.session import SessionLocal

if sys.platform == "win32":
    # psycopg's async mode requires a selector-based loop; Windows defaults
    # to ProactorEventLoop, which it explicitly rejects. No-op on Linux/Docker,
    # which is what this ships on.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

CORPUS_DIR = Path(__file__).parent / "fixtures" / "corpus"

# The canonical 8 documents for the Atlas Migration test project. status_week1.pdf
# and change_request_001.docx in the same directory are format-proof variants
# (same content as their .md counterparts) used only by test_document_parser.py —
# including them here too would double-count facts and create phantom conflicts
# between a document and its own format duplicate.
CANONICAL_CORPUS_FILES = [
    "project_plan.md",
    "status_week1.md",
    "meeting_notes_week1.md",
    "status_week2.md",
    "meeting_notes_week2.md",
    "status_week3.md",
    "meeting_notes_week3.md",
    "change_request_001.md",
]

# A second, deliberately clean project — no blockers contradicting status, no
# undocumented scope decisions, no stale action items — proving the honest
# "no findings" path is real and not just an untested code path.
CLEAN_CORPUS_FILES = [
    "clean_project_plan.md",
    "clean_status_week1.md",
    "clean_meeting_notes_week1.md",
]

GOVERNANCE_RULES = [
    "No status report may say the project is on track while an open blocker exists for the same reporting period.",
    "Every scope or date change must trace to an approved change request; the plan must not go out of date silently.",
    "No action item may stay open past three consecutive meetings without an escalation note.",
]


def seed_pile(tmp_path: Path, filenames: list[str]) -> tuple[str, list[str]]:
    storage_dir = tmp_path / f"documents-{uuid.uuid4().hex[:8]}"
    storage_dir.mkdir()
    document_ids = []

    with SessionLocal() as db:
        pile = Pile(name=f"test-pile-{uuid.uuid4().hex[:8]}")
        db.add(pile)
        db.commit()
        db.refresh(pile)
        pile_id = str(pile.id)

        for filename in filenames:
            source = CORPUS_DIR / filename
            dest = storage_dir / filename
            shutil.copy(source, dest)
            doc = Document(
                pile_id=pile.id,
                filename=filename,
                mime_type="application/octet-stream",
                raw_storage_path=str(dest),
                content_hash=hashlib.sha256(dest.read_bytes()).hexdigest(),
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            document_ids.append(str(doc.id))

    return pile_id, document_ids


def seed_rules(pile_id: str, rule_texts: list[str]) -> list[str]:
    rule_ids = []
    with SessionLocal() as db:
        for text in rule_texts:
            rule = Rule(pile_id=pile_id, rule_text=text, source="test")
            db.add(rule)
            db.commit()
            db.refresh(rule)
            rule_ids.append(str(rule.id))
    return rule_ids


def cleanup_pile(pile_id: str) -> None:
    with SessionLocal() as db:
        db.execute(delete(PendingReview).where(PendingReview.pile_id == pile_id))
        db.execute(delete(ChangelogEntry).where(ChangelogEntry.pile_id == pile_id))
        db.execute(delete(DeliverableSection).where(DeliverableSection.pile_id == pile_id))
        db.execute(delete(Conflict).where(Conflict.pile_id == pile_id))
        db.execute(delete(Finding).where(Finding.pile_id == pile_id))
        db.execute(delete(Fact).where(Fact.pile_id == pile_id))
        db.execute(delete(Rule).where(Rule.pile_id == pile_id))
        run_ids = [r.id for r in db.query(Run).filter(Run.pile_id == pile_id).all()]
        if run_ids:
            db.execute(delete(RunStageMetric).where(RunStageMetric.run_id.in_(run_ids)))
        db.execute(delete(Run).where(Run.pile_id == pile_id))
        db.execute(delete(Document).where(Document.pile_id == pile_id))
        db.execute(delete(Pile).where(Pile.id == pile_id))
        db.commit()


@pytest.fixture
def seeded_pile(tmp_path):
    pile_id, document_ids = seed_pile(tmp_path, CANONICAL_CORPUS_FILES)
    yield pile_id, document_ids
    cleanup_pile(pile_id)


@pytest.fixture
def seeded_pile_no_change_request(tmp_path):
    """Only the plan and week-2 meeting notes — no change_request document —
    so the undocumented-scope-change detector has something to actually fire
    on (behavior #8's companion: the detector must be context-sensitive, not
    always-on; see test_pipeline_stages.py for the contrasting case)."""
    pile_id, document_ids = seed_pile(tmp_path, ["project_plan.md", "meeting_notes_week2.md"])
    yield pile_id, document_ids
    cleanup_pile(pile_id)


@pytest.fixture
def seeded_clean_pile(tmp_path):
    pile_id, document_ids = seed_pile(tmp_path, CLEAN_CORPUS_FILES)
    yield pile_id, document_ids
    cleanup_pile(pile_id)
