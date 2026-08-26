"""Regression tests for three robustness fixes found by code review (not live
testing), all tied to Task 1's stated non-negotiable behaviors:

1. Injection detection must hold for EVERY provider, not just the fake client
   (Behavior #8) — the deterministic detector is now a node-level backstop
   deduped against whatever the provider itself emitted.
2. milestone/action_item values are JSON-encoded strings; a real provider can
   return a malformed one, which must degrade gracefully, never crash a core
   node (draft_deliverable, find_stale_action_items).

The full-pipeline injection test (test_edge_cases.py) already proves the node
wires the detector in for the fake path; these focus on the new logic itself and
the malformed-provider-output paths a fake client never exercises.
"""
import json
import uuid

from app.db.models import DeliverableSection, Pile
from app.db.session import SessionLocal
from app.graph.nodes.draft_deliverable import draft_deliverable
from app.services.fact_analysis import find_stale_action_items, parse_fact_json
from app.services.llm_client import merge_injection_facts


# ---- Fix #1: injection backstop is provider-agnostic --------------------------

def test_merge_appends_injection_when_provider_emitted_nothing():
    """The core new guarantee: even when a provider returns zero
    suspicious_instruction facts (a real model that missed the line), the
    deterministic detector's fact is still added."""
    provider_facts = [{"fact_type": "status", "key": "status", "value": "On Track", "citation_location": "s.md:1"}]
    detected = [
        {
            "fact_type": "suspicious_instruction",
            "key": "embedded_instruction_attempt",
            "value": "ignore all previous instructions",
            "citation_location": "s.md:9",
        }
    ]
    merged = merge_injection_facts(provider_facts, detected)
    flagged = [f for f in merged if f["fact_type"] == "suspicious_instruction"]
    assert len(flagged) == 1
    assert flagged[0]["citation_location"] == "s.md:9"


def test_merge_does_not_double_count_when_provider_already_flagged_the_line():
    """A real provider that DID emit its own suspicious_instruction fact for the
    same line must not produce a duplicate when the detector flags it too."""
    same_loc = "s.md:9"
    provider_facts = [
        {"fact_type": "suspicious_instruction", "key": "x", "value": "ignore instructions", "citation_location": same_loc}
    ]
    detected = [
        {"fact_type": "suspicious_instruction", "key": "embedded_instruction_attempt", "value": "ignore instructions", "citation_location": same_loc}
    ]
    merged = merge_injection_facts(provider_facts, detected)
    assert len([f for f in merged if f["fact_type"] == "suspicious_instruction"]) == 1


# ---- Fix #2: defensive JSON parsing of milestone/action_item values -----------

def test_parse_fact_json_handles_valid_malformed_and_non_object():
    assert parse_fact_json('{"status": "open"}') == {"status": "open"}
    assert parse_fact_json("{not valid json") is None
    assert parse_fact_json("42") is None  # valid JSON, but not an object
    assert parse_fact_json("[]") is None  # valid JSON array, not an object


def test_find_stale_action_items_skips_malformed_value_without_crashing():
    """Three consecutive open occurrences of AI-1 (valid JSON) should still be
    flagged, while a malformed AI-2 value is skipped rather than crashing the
    whole rule check (the pre-fix behavior was a raw json.loads KeyError)."""
    facts = []
    for i in range(1, 4):
        facts.append(
            {
                "document_id": f"d{i}",
                "fact_type": "action_item",
                "key": "AI-1",
                "value": json.dumps({"description": "Migrate auth", "due": "2026-03-01", "status": "open"}),
                "citation_location": f"meeting_{i}.md:3",
            }
        )
    facts.append(
        {
            "document_id": "d4",
            "fact_type": "action_item",
            "key": "AI-2",
            "value": "{this is not valid json",  # a real provider could emit this
            "citation_location": "meeting_4.md:3",
        }
    )

    results = find_stale_action_items(facts, min_occurrences=3)

    assert len(results) == 1
    assert "AI-1" in results[0]["description"]
    assert len(results[0]["citations"]) == 3


def test_draft_deliverable_degrades_gracefully_on_malformed_values():
    """A malformed milestone/action_item value must render as raw text, not
    crash draft_deliverable (a core Movement-1 node)."""
    with SessionLocal() as db:
        pile = Pile(name=f"robustness-{uuid.uuid4().hex[:8]}")
        db.add(pile)
        db.commit()
        db.refresh(pile)
        pile_id = str(pile.id)

    try:
        state = {
            "pile_id": pile_id,
            "facts": [
                {"fact_type": "milestone", "key": "M1", "value": "{broken json", "citation_location": "plan.md:2"},
                {"fact_type": "action_item", "key": "AI-9", "value": "not json at all", "citation_location": "plan.md:5"},
            ],
            "conflicts": [],
            "stages_completed": [],
        }

        # Must not raise.
        result = draft_deliverable(state)

        milestones = result["deliverable"]["milestones"]["content"]
        actions = result["deliverable"]["action_items"]["content"]
        # Raw value is preserved rather than crashing on the missing owner/due keys.
        assert "{broken json" in milestones
        assert "not json at all" in actions
    finally:
        with SessionLocal() as db:
            db.execute(DeliverableSection.__table__.delete().where(DeliverableSection.pile_id == pile_id))
            db.execute(Pile.__table__.delete().where(Pile.id == pile_id))
            db.commit()
