"""Shared fact-analysis helpers used by both Movement 1's automatic conflict
detection (detect_conflicts) and Movement 2's rule-checking (check_rule on the
fake LLM client) — same underlying signal, different framing: an analyst's own
observation while understanding the pile, versus an explicit check against a
policy the user handed the system. Keeping the logic in one place means the
two movements can never quietly disagree about what a "stale action item" is.
"""

import json
from collections import defaultdict


def group_facts_by_document(facts: list[dict]) -> dict[str, list[dict]]:
    by_doc = defaultdict(list)
    for f in facts:
        by_doc[f["document_id"]].append(f)
    return by_doc


def period_of(by_doc: dict, doc_id: str) -> str | None:
    return next((f["value"] for f in by_doc[doc_id] if f["fact_type"] == "period"), None)


def find_status_vs_blocker(facts: list[dict]) -> list[dict]:
    by_doc = group_facts_by_document(facts)
    status_docs = sorted(
        (d for d in by_doc if any(f["fact_type"] == "status" for f in by_doc[d])),
        key=lambda d: period_of(by_doc, d) or "",
    )
    meeting_docs = [d for d in by_doc if any(f["fact_type"] == "blocker" for f in by_doc[d])]

    results = []
    for status_doc in status_docs:
        period = period_of(by_doc, status_doc)
        status_fact = next((f for f in by_doc[status_doc] if f["fact_type"] == "status"), None)
        if not status_fact or "on track" not in status_fact["value"].lower():
            continue
        for meeting_doc in meeting_docs:
            if period_of(by_doc, meeting_doc) != period:
                continue
            blocker_fact = next((f for f in by_doc[meeting_doc] if f["fact_type"] == "blocker"), None)
            if blocker_fact:
                results.append(
                    {
                        "description": (
                            f'Status report for {period} says "{status_fact["value"]}" but '
                            f"meeting notes for the same period record an open blocker: "
                            f'"{blocker_fact["value"]}"'
                        ),
                        "citations": [status_fact["citation_location"], blocker_fact["citation_location"]],
                    }
                )
    return results


def find_stalled_progress(facts: list[dict]) -> list[dict]:
    by_doc = group_facts_by_document(facts)
    status_docs = sorted(
        (d for d in by_doc if any(f["fact_type"] == "percent_complete" for f in by_doc[d])),
        key=lambda d: period_of(by_doc, d) or "",
    )
    percent_sequence = [
        (period_of(by_doc, d), next(f for f in by_doc[d] if f["fact_type"] == "percent_complete"))
        for d in status_docs
    ]

    results = []
    for i in range(1, len(percent_sequence)):
        prev_period, prev_fact = percent_sequence[i - 1]
        cur_period, cur_fact = percent_sequence[i]
        if prev_fact["value"] == cur_fact["value"]:
            results.append(
                {
                    "description": (
                        f'Percent-complete stayed at {cur_fact["value"]}% from {prev_period} to '
                        f"{cur_period} with no explanation — possible stalled progress reported as steady."
                    ),
                    "citations": [prev_fact["citation_location"], cur_fact["citation_location"]],
                }
            )
    return results


def find_undocumented_scope_changes(facts: list[dict], change_request_doc_ids: set[str]) -> list[dict]:
    by_doc = group_facts_by_document(facts)
    meeting_docs = [d for d in by_doc if any(f["fact_type"] == "decision" for f in by_doc[d])]

    results = []
    if not change_request_doc_ids:
        for meeting_doc in meeting_docs:
            for f in by_doc[meeting_doc]:
                if f["fact_type"] != "decision":
                    continue
                if "scope" in f["value"].lower() or "sync" in f["value"].lower():
                    results.append(
                        {
                            "description": (
                                f'Meeting notes record a scope decision — "{f["value"]}" — with no '
                                f"matching change request on file yet. The project plan was never updated."
                            ),
                            "citations": [f["citation_location"]],
                        }
                    )
    return results


def find_stale_action_items(facts: list[dict], min_occurrences: int = 3) -> list[dict]:
    by_doc = group_facts_by_document(facts)
    meeting_docs = [d for d in by_doc if any(f["fact_type"] == "action_item" for f in by_doc[d])]

    occurrences = defaultdict(list)
    for d in meeting_docs:
        for f in by_doc[d]:
            if f["fact_type"] == "action_item":
                value = json.loads(f["value"])
                occurrences[f["key"]].append((period_of(by_doc, d), value, f["citation_location"]))

    results = []
    for item_id, occs in occurrences.items():
        still_open = [o for o in occs if o[1]["status"] == "open"]
        if len(still_open) >= min_occurrences:
            results.append(
                {
                    "description": (
                        f'Action item {item_id} ("{still_open[0][1]["description"]}") has stayed '
                        f"open across {len(still_open)} consecutive meetings with no escalation."
                    ),
                    "citations": [o[2] for o in still_open],
                }
            )
    return results


def find_embedded_instructions(facts: list[dict]) -> list[dict]:
    return [
        {
            "description": (
                f'Document contains text resembling an instruction aimed at an AI reviewer: '
                f'"{f["value"][:200]}". Treated as data, not followed.'
            ),
            "citations": [f["citation_location"]],
        }
        for f in facts
        if f["fact_type"] == "suspicious_instruction"
    ]
