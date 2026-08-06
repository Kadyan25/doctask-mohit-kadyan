from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from app.graph.nodes.classify import classify
from app.graph.nodes.detect_conflicts import detect_conflicts
from app.graph.nodes.draft_deliverable import draft_deliverable
from app.graph.nodes.extract_facts import extract_facts
from app.graph.nodes.ingest import ingest
from app.graph.state import PipelineState

MOVEMENT_1_NODES = ["ingest", "classify", "extract_facts", "detect_conflicts", "draft_deliverable"]


def build_graph(checkpointer: BaseCheckpointSaver, interrupt_after: list[str] | None = None):
    """Movement 1 (Understand): ingest -> classify -> extract_facts ->
    detect_conflicts -> draft_deliverable. `interrupt_after` lets tests pause
    the graph after a given node to prove kill-and-resume — LangGraph
    checkpoints after every node regardless of whether you ask it to pause,
    so deliberately pausing here and continuing later exercises exactly the
    code path a real crash-and-restart would.
    """
    graph = StateGraph(PipelineState)
    graph.add_node("ingest", ingest)
    graph.add_node("classify", classify)
    graph.add_node("extract_facts", extract_facts)
    graph.add_node("detect_conflicts", detect_conflicts)
    graph.add_node("draft_deliverable", draft_deliverable)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "classify")
    graph.add_edge("classify", "extract_facts")
    graph.add_edge("extract_facts", "detect_conflicts")
    graph.add_edge("detect_conflicts", "draft_deliverable")
    graph.add_edge("draft_deliverable", END)

    return graph.compile(checkpointer=checkpointer, interrupt_after=interrupt_after or [])
