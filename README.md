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

Tests run against a real Postgres-backed LangGraph checkpointer, not mocks — see `tests/test_resume.py` (kill-and-resume), `tests/test_concurrency.py` (including the same-pile-hit-twice case), and `tests/test_watcher.py` (a real filesystem Observer, not just the graph it calls) for the load-bearing proofs.

## MCP

The same operations as the REST API, exposed as MCP tools at `/mcp` (streamable HTTP), sharing the identical compiled graphs: `create_pile`, `upload_document`, `submit_rule`, `start_run`, `start_examine`, `list_pending_review`, `approve_item`, `reject_item`, `get_deliverable`, `get_changelog`, `get_cost_report`. Approval — the human gate — is a callable tool, so a program can drive the whole flow end to end, including the gate itself.

## Logged assumptions

- Domain chosen (software project delivery docs) over the brief's other suggested domains (contracts, loans, insurance, clinical) because it needs no outside domain expertise to build a credible, deliberately-contradicting synthetic corpus — see the project's `CLAUDE.md` for the reasoning.
- Cost/time tracking (`GET /runs/{id}/cost`) reports real wall-clock duration per stage. Token counts and a dollar cost estimate stay null under `LLM_PROVIDER=fake` (the default) rather than fabricated — the fake client makes no real calls, so a made-up number would be worse than an honest gap. `AnthropicLLMClient`'s real calls carry actual usage data that could be threaded through if the real provider becomes the default.
- Same-pile-hit-twice concurrency (two runs racing on identical work) is handled via database-level unique constraints and `INSERT ... ON CONFLICT`, not application-level locking — verified in `tests/test_concurrency.py`.
- Uploading the same document twice into one pile is not deduped (no `content_hash` check at upload time) — it produces two independent extractions and visibly duplicated lines in the register. Known, not fixed; see `issues.md`. Beyond the canonical corpus, `tests/test_edge_cases.py` also covers malformed files, empty files, unicode content, prompt-injection phrasing variants (plus false-positive checks), unmatched rule text, and a 40-document scale test.

---
Built for the SuperDocs Round 2 engineering task.
