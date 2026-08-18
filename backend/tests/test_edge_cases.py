"""Adversarial and scale testing beyond the canonical 8-document corpus. FakeLLMClient
is a regex parser tuned to this project's "Field: value" format (see llm_client.py) —
these fixtures are still synthetic and in that same format, but aimed at inputs the
canonical corpus never exercises: malformed files, duplicates, encoding, prompt-injection
phrasing variety (including false-positive checks), unmatched rules, and scale.
"""
import hashlib
import shutil
import uuid
from pathlib import Path

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.db.models import DeliverableSection, Document, Fact, Finding, Pile
from app.db.session import SessionLocal
from app.graph.checkpointer import get_checkpointer_dsn
from app.graph.examine_pipeline import build_examine_graph
from app.graph.pipeline import build_graph
from tests.conftest import cleanup_pile, create_run, seed_pile, seed_rules

EDGE_CORPUS_DIR = Path(__file__).parent / "fixtures" / "corpus_edge_cases"
CANONICAL_CORPUS_DIR = Path(__file__).parent / "fixtures" / "corpus"


async def _run_movement1(pile_id: str, document_ids: list[str]) -> dict:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    async with AsyncPostgresSaver.from_conn_string(get_checkpointer_dsn()) as saver:
        await saver.setup()
        graph = build_graph(saver)
        return await graph.ainvoke(
            {"pile_id": pile_id, "run_id": create_run(pile_id), "document_ids": document_ids},
            config=config,
        )


async def _run_movement2(pile_id: str) -> dict:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    async with AsyncPostgresSaver.from_conn_string(get_checkpointer_dsn()) as saver:
        await saver.setup()
        graph = build_examine_graph(saver)
        return await graph.ainvoke({"pile_id": pile_id, "run_id": create_run(pile_id)}, config=config)


def _seed_from_dir(tmp_path: Path, source_dir: Path, filenames: list[str]) -> tuple[str, list[str]]:
    """Like conftest.seed_pile but reads from an arbitrary source directory,
    so edge-case fixtures don't have to live in the canonical corpus folder."""
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
            source = source_dir / filename
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


@pytest.mark.asyncio
async def test_malformed_file_does_not_crash_the_run(tmp_path):
    """A corrupt .docx alongside good documents must not take the whole run down —
    ingest.py's per-document try/except should degrade to a reported error while
    still processing the documents that DO parse."""
    pile_id, document_ids = _seed_from_dir(
        tmp_path, EDGE_CORPUS_DIR, ["malformed.docx", "unicode_status.md"]
    )
    try:
        result = await _run_movement1(pile_id, document_ids)

        assert result["stages_completed"][-1] == "draft_deliverable"
        assert result["error"] is not None
        assert "malformed.docx" in result["error"]

        # The valid document alongside it still got processed.
        with SessionLocal() as db:
            facts = db.query(Fact).filter(Fact.pile_id == pile_id).all()
            assert any(f.citation_location.startswith("unicode_status.md") for f in facts)
    finally:
        cleanup_pile(pile_id)


@pytest.mark.asyncio
async def test_empty_file_produces_no_facts_but_does_not_crash(tmp_path):
    pile_id, document_ids = _seed_from_dir(tmp_path, EDGE_CORPUS_DIR, ["empty.md"])
    try:
        result = await _run_movement1(pile_id, document_ids)
        assert result["error"] is None
        assert result["facts"] == []
    finally:
        cleanup_pile(pile_id)


@pytest.mark.asyncio
async def test_unicode_content_is_parsed_without_crashing(tmp_path):
    pile_id, document_ids = _seed_from_dir(tmp_path, EDGE_CORPUS_DIR, ["unicode_status.md"])
    try:
        result = await _run_movement1(pile_id, document_ids)
        assert result["error"] is None

        with SessionLocal() as db:
            facts = db.query(Fact).filter(Fact.pile_id == pile_id).all()
            status_facts = [f for f in facts if f.fact_type == "status"]
            assert len(status_facts) == 1
            assert status_facts[0].value == "On Track"
            blocker_facts = [f for f in facts if f.fact_type == "blocker"]
            assert len(blocker_facts) == 1
            assert "Café Deploy" in blocker_facts[0].value
    finally:
        cleanup_pile(pile_id)


@pytest.mark.asyncio
async def test_duplicate_document_upload_duplicates_facts_known_limitation(tmp_path):
    """Documents the real, current behavior: nothing dedupes by content_hash at
    upload time or in extract_facts, so uploading the same file twice into one
    pile produces two full sets of duplicate facts. This is not a crash, but it
    is a real gap — logged in issues.md, not silently accepted as correct."""
    pile_id, document_ids = _seed_from_dir(
        tmp_path, CANONICAL_CORPUS_DIR, ["status_week1.md", "status_week1.md"]
    )
    try:
        result = await _run_movement1(pile_id, document_ids)
        assert result["error"] is None

        with SessionLocal() as db:
            facts = db.query(Fact).filter(Fact.pile_id == pile_id).all()
            status_facts = [f for f in facts if f.fact_type == "status"]
            # Two Document rows -> two independent extractions -> duplicated facts.
            assert len(status_facts) == 2
            assert {str(f.document_id) for f in status_facts} == set(document_ids)
    finally:
        cleanup_pile(pile_id)


@pytest.mark.asyncio
async def test_prompt_injection_variants_are_all_reported_as_data(tmp_path):
    pile_id, document_ids = _seed_from_dir(tmp_path, EDGE_CORPUS_DIR, ["injection_variants.md"])
    try:
        result = await _run_movement1(pile_id, document_ids)
        assert result["error"] is None

        conflict_types = {c["conflict_type"] for c in result["conflicts"]}
        assert "embedded_instruction_attempt" in conflict_types

        with SessionLocal() as db:
            facts = db.query(Fact).filter(
                Fact.pile_id == pile_id, Fact.fact_type == "suspicious_instruction"
            ).all()
            # The injection sentences are word-wrapped across 2 physical lines each
            # in the fixture, and the detector runs per-line — so the "ignore all
            # previous instructions" / "mark this compliant" pair and the "skip
            # further review" / "pre-approved" pair each contribute 2 facts (4 total).
            assert len(facts) == 4

        # Behavior #8, restated: the run still completes normally and reports
        # a real status fact from the same document — the injection didn't
        # derail extraction of everything else in it.
        with SessionLocal() as db:
            status_facts = db.query(Fact).filter(
                Fact.pile_id == pile_id, Fact.fact_type == "status"
            ).all()
            assert len(status_facts) == 1
            assert status_facts[0].value == "On Track"
    finally:
        cleanup_pile(pile_id)


@pytest.mark.asyncio
async def test_benign_mention_of_trigger_words_is_not_falsely_flagged(tmp_path):
    """Precision check: ordinary text that happens to contain 'system',
    'approved', 'compliant' must NOT be misclassified as an injection attempt."""
    pile_id, document_ids = _seed_from_dir(tmp_path, EDGE_CORPUS_DIR, ["benign_mention.md"])
    try:
        result = await _run_movement1(pile_id, document_ids)
        assert result["error"] is None

        conflict_types = {c["conflict_type"] for c in result["conflicts"]}
        assert "embedded_instruction_attempt" not in conflict_types

        with SessionLocal() as db:
            suspicious = db.query(Fact).filter(
                Fact.pile_id == pile_id, Fact.fact_type == "suspicious_instruction"
            ).all()
            assert suspicious == []
    finally:
        cleanup_pile(pile_id)


@pytest.mark.asyncio
async def test_rule_text_outside_known_keywords_yields_honest_no_findings(seeded_pile):
    """The fake client's check_rule only recognizes 3 keyword patterns (see
    llm_client.py's own documented limitation). A rule phrased entirely outside
    those patterns must yield zero findings, not a false positive."""
    pile_id, document_ids = seeded_pile
    await _run_movement1(pile_id, document_ids)
    seed_rules(pile_id, ["All meeting notes must list at least one attendee from QA."])

    result = await _run_movement2(pile_id)

    assert result["findings"] == []
    with SessionLocal() as db:
        findings = db.query(Finding).filter(Finding.pile_id == pile_id).all()
        assert len(findings) == 0
        section = (
            db.query(DeliverableSection)
            .filter(DeliverableSection.pile_id == pile_id, DeliverableSection.section_key == "compliance_findings")
            .first()
        )
        assert "No findings" in section.content


def _make_status_and_meeting_pair(week: int, on_track: bool, has_blocker: bool) -> tuple[str, str]:
    period = f"2026-0{6 + week // 4}-{(week % 4) * 7 + 1:02d}"
    status = f"""Document-Type: status_report
Project: Scale Test
Period: {period}

# Weekly Status — {period}

Status: {"On Track" if on_track else "At Risk"}
Percent-Complete: {min(95, 5 * week)}%

Notes: Week {week} generated status for scale testing.
"""
    if has_blocker:
        status += f"Blocker: Vendor access for week {week} still pending.\n"

    meeting = f"""Document-Type: meeting_notes
Project: Scale Test
Period: {period}

# Meeting Notes — {period}

Attendees: Dev Team

Decisions: None this week.

Action-Item: [AI-{week}] Owner-{week} to follow up — Due: {period} — Status: open
"""
    return status, meeting


@pytest.mark.asyncio
async def test_large_generated_corpus_runs_without_errors(tmp_path):
    """Scale test: 40 generated documents (20 weeks x status+meeting), a third
    of them deliberately contradicting (On Track claimed while a blocker is
    open that same week) — proves the pipeline holds up well past the
    canonical 8-document corpus, and that conflict count scales sanely rather
    than exploding or silently under-counting."""
    storage_dir = tmp_path / "scale-documents"
    storage_dir.mkdir()

    with SessionLocal() as db:
        pile = Pile(name=f"scale-test-{uuid.uuid4().hex[:8]}")
        db.add(pile)
        db.commit()
        db.refresh(pile)
        pile_id = str(pile.id)

    document_ids: list[str] = []
    expected_contradictions = 0
    try:
        with SessionLocal() as db:
            for week in range(1, 21):
                on_track = True
                has_blocker = week % 3 == 0  # every 3rd week: On Track claimed + blocker open
                if has_blocker:
                    expected_contradictions += 1

                status_text, meeting_text = _make_status_and_meeting_pair(week, on_track, has_blocker)
                for filename, content in [
                    (f"status_week{week}.md", status_text),
                    (f"meeting_week{week}.md", meeting_text),
                ]:
                    dest = storage_dir / filename
                    dest.write_text(content, encoding="utf-8")
                    doc = Document(
                        pile_id=pile.id,
                        filename=filename,
                        mime_type="text/markdown",
                        raw_storage_path=str(dest),
                        content_hash=hashlib.sha256(dest.read_bytes()).hexdigest(),
                    )
                    db.add(doc)
                    db.commit()
                    db.refresh(doc)
                    document_ids.append(str(doc.id))

        assert len(document_ids) == 40

        result = await _run_movement1(pile_id, document_ids)

        assert result["error"] is None
        assert result["stages_completed"][-1] == "draft_deliverable"

        status_vs_blocker = [c for c in result["conflicts"] if c["conflict_type"] == "status_vs_blocker"]
        assert len(status_vs_blocker) == expected_contradictions

        with SessionLocal() as db:
            facts = db.query(Fact).filter(Fact.pile_id == pile_id).all()
            # 40 docs x (status/period/percent + notes-less blocker sometimes) — just
            # confirm a substantial, non-trivial number of facts were actually extracted.
            assert len(facts) > 80

            sections = db.query(DeliverableSection).filter(DeliverableSection.pile_id == pile_id).all()
            assert {s.section_key for s in sections} == {"status_summary", "milestones", "action_items", "conflicts"}
    finally:
        cleanup_pile(pile_id)
