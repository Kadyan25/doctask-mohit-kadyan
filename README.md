# Document Health Register

An agentic system that owns a pile of software-project-delivery documents end to end: understands them, checks them against your rules, and stays live as new documents arrive — with a human gate on everything it commits.

Built for the SuperDocs Round 2 engineering task. Standalone — does not call SuperDocs' API (that's the separate Slack build in the sibling repo).

## What it does

- **Understands the pile**: ingests mixed-format documents (project plans, weekly status reports, meeting notes, change requests), extracts facts, detects where documents disagree, and produces a cited **Project Health Register**.
- **Examines against your rules**: checks the pile and the register against a user-supplied governance checklist, producing findings — or an honest "no findings" when the corpus is clean.
- **Stays alive**: new documents dropped into a watched folder produce a scoped update to the register, not a rewrite; untouched sections stay byte-identical; contradictions with the existing register are surfaced, never silently resolved.
- **Human gates everything**: every conflict, finding, and update lands in one review queue, approved or rejected item by item.

See [architecture.md](architecture.md) for the full technical contract and [build-plan.md](build-plan.md) for phase-by-phase status.

## Formats and domain accepted

Documents: PDF, DOCX, Markdown, plain text. Domain: software project delivery (project plans/SOWs, status reports, meeting notes, change requests). A second run means different documents inside this same declared set.

## Quick start

Requires Docker and Docker Compose.

```bash
./start.sh
```

This builds and starts Postgres+pgvector, the backend, and the frontend; the backend applies its own database migrations on startup. Then:

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs

No live LLM key is required to run this — `LLM_PROVIDER=fake` (the default in `.env.example`) uses a deterministic stub so the stack, and the test suite, run for free.

## Running tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

Tests run against a real Postgres-backed LangGraph checkpointer, not mocks — see `tests/test_checkpointer.py` for the kill-and-resume and concurrent-runs proofs.

## Logged assumptions

- Domain chosen (software project delivery docs) over the brief's other suggested domains (contracts, loans, insurance, clinical) because it needs no outside domain expertise to build a credible, deliberately-contradicting synthetic corpus — see the project's `CLAUDE.md` for the reasoning.
- MCP server exposes the same operations as the REST API (create_pile, upload_document, submit_rules, start_run, list_pending_review, approve_item, reject_item, get_deliverable, get_changelog, get_cost_report) — mirrored 1:1, per the brief's "strongest version of behavior four."

---
Built for the SuperDocs Round 2 engineering task.
