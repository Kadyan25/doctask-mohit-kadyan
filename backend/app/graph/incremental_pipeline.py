from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from app.graph.nodes.changelog_entry import changelog_entry
from app.graph.nodes.classify import classify
from app.graph.nodes.detect_conflicts import detect_conflicts
from app.graph.nodes.draft_deliverable import draft_deliverable
from app.graph.nodes.incremental_extract import incremental_extract
from app.graph.nodes.ingest import ingest
from app.graph.state import PipelineState


def build_incremental_graph(checkpointer: BaseCheckpointSaver):
    """Movement 3 (Stay alive): triggered per new-document arrival, scoped to
    `document_ids` containing just that one document. Reuses Movement 1's
    `ingest`, `classify`, `detect_conflicts`, and `draft_deliverable` nodes
    unchanged — the only new nodes are `incremental_extract` (extracts the
    new document, then reloads the full current fact set so conflict
    detection and drafting see the complete picture) and `changelog_entry`
    (records which sections actually changed). Movement 1 and Movement 3 can
    never quietly disagree about what counts as a conflict or how the
    register renders, since they call the identical functions.
    """
    graph = StateGraph(PipelineState)
    graph.add_node("ingest", ingest)
    graph.add_node("classify", classify)
    graph.add_node("incremental_extract", incremental_extract)
    graph.add_node("detect_conflicts", detect_conflicts)
    graph.add_node("draft_deliverable", draft_deliverable)
    graph.add_node("changelog_entry", changelog_entry)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "classify")
    graph.add_edge("classify", "incremental_extract")
    graph.add_edge("incremental_extract", "detect_conflicts")
    graph.add_edge("detect_conflicts", "draft_deliverable")
    graph.add_edge("draft_deliverable", "changelog_entry")
    graph.add_edge("changelog_entry", END)

    return graph.compile(checkpointer=checkpointer)
