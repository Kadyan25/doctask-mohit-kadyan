"""Process-wide handles shared between the REST API and the MCP server —
both are mounted in the same FastAPI process, so a plain module is enough,
no IPC needed. Set once in main.py's lifespan, read by mcp_server.py's tools,
so both surfaces always operate on the identical compiled graphs and
checkpointer, never two independent copies that could drift.
"""

from typing import Any

graph: Any = None
examine_graph: Any = None
incremental_graph: Any = None
