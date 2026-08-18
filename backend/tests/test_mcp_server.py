"""Exercises the real MCP JSON-RPC wire protocol against the running app —
every other test either hits the REST API or invokes a graph directly in
Python. This is the one place that proves a program driving this system
through MCP (per behavior #4: fully machine-drivable) actually works end to
end through the protocol layer itself: session negotiation, tools/list,
tools/call, and the human-approval gate as a callable tool.

mcp.streamable_http_app() is mounted with its default json_response=False
(see app/main.py), so successful responses are SSE-framed — a single
`data: <json-rpc payload>` line. Error responses (missing session, bad
Accept header, etc.) are returned as plain JSON instead. _sse_json() below
handles the success path; error-path assertions read response.json() directly.

Two real constraints of the mcp package drove the fixture shape below:
- `mcp.session_manager.run()` (invoked by app/main.py's lifespan) raises if
  called twice on the same MCPServer instance, so every test in this module
  shares one TestClient/app lifespan (module-scoped fixture) instead of each
  test opening its own.
- The streamable-HTTP app auto-enables DNS-rebinding protection for
  host="127.0.0.1" (the default), allowing only Host headers matching
  "localhost:*"/"127.0.0.1:*"/"[::1]:*" — Starlette's TestClient default Host
  header ("testserver") doesn't match, so base_url must carry a real
  localhost origin with a port.
"""

import base64
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import cleanup_pile

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

_ALL_TOOL_NAMES = {
    "ping",
    "create_pile",
    "upload_document",
    "submit_rule",
    "start_run",
    "start_examine",
    "list_pending_review",
    "approve_item",
    "reject_item",
    "get_deliverable",
    "get_changelog",
    "get_cost_report",
}


def _sse_json(response) -> dict:
    for line in response.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:"):].strip())
    raise AssertionError(f"no SSE data line in response body: {response.text!r}")


def _rpc(client, session_id, method, params=None, request_id=1):
    headers = dict(_HEADERS)
    if session_id:
        headers["mcp-session-id"] = session_id
    body = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        body["params"] = params
    return client.post("/mcp/", json=body, headers=headers)


def _call_tool_blocks(client, session_id, request_id, name, arguments) -> list[dict]:
    response = _rpc(client, session_id, "tools/call", {"name": name, "arguments": arguments}, request_id=request_id)
    payload = _sse_json(response)
    assert "error" not in payload, payload
    return payload["result"]["content"]


def _call_tool(client, session_id, request_id, name, arguments):
    """For tools returning a single value (str/dict) — one content block."""
    return _call_tool_blocks(client, session_id, request_id, name, arguments)[0]["text"]


def _call_list_tool(client, session_id, request_id, name, arguments) -> list[dict]:
    """For tools returning list[dict] (get_deliverable, list_pending_review,
    get_changelog): the mcp SDK flattens a list return into one content block
    PER ITEM rather than one block holding the whole array — see the module
    docstring's constraints, or func_metadata.py's _convert_to_content."""
    blocks = _call_tool_blocks(client, session_id, request_id, name, arguments)
    return [json.loads(b["text"]) for b in blocks]


@pytest.fixture(scope="module")
def app_client():
    """One lifespan (and one MCPServer session-manager start) for the whole
    module — the underlying mcp.session_manager can only be run() once."""
    with TestClient(app, base_url="http://localhost:8000") as client:
        yield client


@pytest.fixture
def mcp_session(app_client):
    """A real initialize handshake against the shared client, yielding the
    session id every subsequent call in this test must carry."""
    init_response = _rpc(
        app_client,
        None,
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1.0"},
        },
    )
    assert init_response.status_code == 200, init_response.text
    session_id = init_response.headers["mcp-session-id"]
    yield app_client, session_id


def test_call_without_session_id_is_rejected(app_client):
    """Matches the manual live test: a bare tools/list with no prior
    initialize handshake must fail closed, not silently proceed."""
    response = _rpc(app_client, None, "tools/list")
    assert response.status_code == 400
    assert "Missing session ID" in response.json()["error"]["message"]


def test_tools_list_matches_every_registered_tool(mcp_session):
    client, session_id = mcp_session
    response = _rpc(client, session_id, "tools/list", request_id=2)
    assert response.status_code == 200
    payload = _sse_json(response)
    tool_names = {t["name"] for t in payload["result"]["tools"]}
    assert tool_names == _ALL_TOOL_NAMES


def test_full_flow_through_the_real_json_rpc_protocol(mcp_session):
    """create_pile -> upload_document -> start_run -> get_deliverable ->
    list_pending_review -> submit_rule -> start_examine -> approve_item, all
    issued as real tools/call requests over the wire protocol, not as direct
    Python calls. Proves the human-approval gate itself is machine-drivable."""
    client, session_id = mcp_session
    request_id = 2

    def call(name, arguments):
        nonlocal request_id
        request_id += 1
        return _call_tool(client, session_id, request_id, name, arguments)

    def call_list(name, arguments):
        nonlocal request_id
        request_id += 1
        return _call_list_tool(client, session_id, request_id, name, arguments)

    assert call("ping", {}) == "pong"

    pile = json.loads(call("create_pile", {"name": f"mcp-protocol-test-{uuid.uuid4().hex[:8]}"}))
    pile_id = pile["id"]

    try:
        doc_text = "Document-Type: status_report\nStatus: on track\nPercent-Complete: 40%\n"
        call(
            "upload_document",
            {
                "pile_id": pile_id,
                "filename": "status.md",
                "content_base64": base64.b64encode(doc_text.encode()).decode(),
            },
        )

        run = json.loads(call("start_run", {"pile_id": pile_id}))
        assert run["status"] == "completed"

        sections = call_list("get_deliverable", {"pile_id": pile_id})
        assert any(s["section_key"] == "status_summary" for s in sections)

        pending = call_list("list_pending_review", {"pile_id": pile_id})
        assert pending == []

        call("submit_rule", {"pile_id": pile_id, "rule_text": "No status report may say on track while a blocker exists."})
        examine = json.loads(call("start_examine", {"pile_id": pile_id}))
        assert examine["status"] == "completed"

        pending_after_examine = call_list("list_pending_review", {"pile_id": pile_id})
        assert pending_after_examine == []
    finally:
        cleanup_pile(pile_id)


def test_approve_item_through_the_protocol_resolves_the_human_gate(mcp_session):
    """A conflict actually needs to exist for approve_item to have something
    to act on, so this seeds a contradiction (on track + open blocker) rather
    than reusing the clean fixture above."""
    client, session_id = mcp_session
    request_id = 2

    def call(name, arguments):
        nonlocal request_id
        request_id += 1
        return _call_tool(client, session_id, request_id, name, arguments)

    def call_list(name, arguments):
        nonlocal request_id
        request_id += 1
        return _call_list_tool(client, session_id, request_id, name, arguments)

    pile = json.loads(call("create_pile", {"name": f"mcp-approve-test-{uuid.uuid4().hex[:8]}"}))
    pile_id = pile["id"]

    try:
        doc_text = (
            "Document-Type: status_report\n"
            "Status: on track\n"
            "Percent-Complete: 40%\n"
            "Blocker: vendor credentials still not provisioned\n"
        )
        call(
            "upload_document",
            {
                "pile_id": pile_id,
                "filename": "status.md",
                "content_base64": base64.b64encode(doc_text.encode()).decode(),
            },
        )
        call("submit_rule", {"pile_id": pile_id, "rule_text": "No status report may say on track while an open blocker exists."})
        call("start_run", {"pile_id": pile_id})
        call("start_examine", {"pile_id": pile_id})

        pending = call_list("list_pending_review", {"pile_id": pile_id})
        assert len(pending) >= 1, "expected the status-vs-blocker contradiction to surface for review"
        item_id = pending[0]["id"]

        decision = json.loads(call("approve_item", {"item_id": item_id, "reviewer": "pytest"}))
        assert decision["status"] == "approved"
        assert decision["reviewer"] == "pytest"
    finally:
        cleanup_pile(pile_id)
