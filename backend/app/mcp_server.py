from mcp.server.mcpserver import MCPServer

mcp = MCPServer("doctask-mohit-kadyan")


@mcp.tool()
def ping() -> str:
    """Health check tool, proves the MCP server is reachable. Real tools
    (create_pile, upload_document, submit_rules, start_run, list_pending_review,
    approve_item, reject_item, get_deliverable, get_changelog, get_cost_report)
    are added as their REST counterparts land, Phase 1 onward — same operations,
    exposed both ways, per architecture.md."""
    return "pong"


if __name__ == "__main__":
    mcp.run()
