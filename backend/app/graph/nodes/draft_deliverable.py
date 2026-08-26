from app.db.session import SessionLocal
from app.graph.state import PipelineState
from app.services.deliverable import upsert_section as _upsert_section
from app.services.fact_analysis import parse_fact_json


def draft_deliverable(state: PipelineState) -> PipelineState:
    facts = state.get("facts", [])
    conflicts = state.get("conflicts", [])
    pile_id = state["pile_id"]

    # Sorted by citation_location — draft_deliverable is the single source of
    # truth for render order, deliberately independent of whatever order
    # `facts` arrives in (Movement 1's in-memory extraction order and
    # Movement 3's reloaded-from-DB order are not guaranteed to match one
    # another otherwise, which would make "byte-identical untouched
    # sections" false whenever an unrelated section got rebuilt).
    status_facts = sorted((f for f in facts if f["fact_type"] == "status"), key=lambda f: f["citation_location"])
    percent_facts = sorted(
        (f for f in facts if f["fact_type"] == "percent_complete"), key=lambda f: f["citation_location"]
    )
    milestone_facts = sorted(
        (f for f in facts if f["fact_type"] == "milestone"), key=lambda f: f["citation_location"]
    )
    action_facts = sorted(
        (f for f in facts if f["fact_type"] == "action_item"), key=lambda f: f["citation_location"]
    )

    status_lines = [f"- {f['value']} ({f['citation_location']})" for f in status_facts]
    percent_lines = [f"- {f['value']}% ({f['citation_location']})" for f in percent_facts]
    status_summary = (
        "# Status Summary\n\n" + "\n".join(status_lines + percent_lines)
        if (status_lines or percent_lines)
        else "# Status Summary\n\nNo status facts extracted."
    )

    milestone_lines = []
    for f in milestone_facts:
        data = parse_fact_json(f["value"])
        if data is None:
            # A real provider returned a non-JSON milestone value — render it raw
            # rather than crashing the whole draft on one malformed fact.
            milestone_lines.append(f"- {f['key']}: {f['value']} ({f['citation_location']})")
        else:
            milestone_lines.append(
                f"- {f['key']}: owner {data.get('owner', '?')}, due {data.get('due', '?')} ({f['citation_location']})"
            )
    milestones_section = (
        "# Milestones\n\n" + "\n".join(milestone_lines) if milestone_lines else "# Milestones\n\nNo milestones extracted."
    )

    action_lines = []
    for f in action_facts:
        data = parse_fact_json(f["value"])
        if data is None:
            action_lines.append(f"- {f['key']}: {f['value']} ({f['citation_location']})")
        else:
            action_lines.append(
                f"- {f['key']}: {data.get('description', '')} — due {data.get('due', '?')}, "
                f"status {data.get('status', '?')} ({f['citation_location']})"
            )
    action_section = (
        "# Action Items\n\n" + "\n".join(action_lines) if action_lines else "# Action Items\n\nNo action items extracted."
    )

    if conflicts:
        sorted_conflicts = sorted(conflicts, key=lambda c: (c["conflict_type"], c["description"]))
        conflict_lines = [f"- [{c['conflict_type']}] {c['description']}" for c in sorted_conflicts]
        conflicts_section = "# Conflicts Awaiting Review\n\n" + "\n".join(conflict_lines)
    else:
        conflicts_section = "# Conflicts Awaiting Review\n\nNo conflicts detected — clean corpus."

    sections = {
        "status_summary": (status_summary, [f["citation_location"] for f in status_facts + percent_facts]),
        "milestones": (milestones_section, [f["citation_location"] for f in milestone_facts]),
        "action_items": (action_section, [f["citation_location"] for f in action_facts]),
        "conflicts": (conflicts_section, [loc for c in conflicts for loc in c["citations"]]),
    }

    deliverable = {}
    with SessionLocal() as db:
        for key, (content, citations) in sections.items():
            _section, changed = _upsert_section(db, pile_id, key, content, citations)
            deliverable[key] = {"content": content, "changed": changed}
        db.commit()

    stages_completed = list(state.get("stages_completed", []))
    stages_completed.append("draft_deliverable")
    return {**state, "deliverable": deliverable, "stage": "draft_deliverable_complete", "stages_completed": stages_completed}
