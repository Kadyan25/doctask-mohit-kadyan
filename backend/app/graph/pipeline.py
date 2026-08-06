from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from app.graph.state import PipelineState


def _stage_a(state: PipelineState) -> PipelineState:
    completed = list(state.get("stages_completed", []))
    completed.append("stage_a")
    return {**state, "stage": "stage_a_complete", "stages_completed": completed}


def _stage_b(state: PipelineState) -> PipelineState:
    completed = list(state.get("stages_completed", []))
    completed.append("stage_b")
    return {**state, "stage": "stage_b_complete", "stages_completed": completed}


def build_graph(checkpointer: BaseCheckpointSaver, interrupt_after_stage_a: bool = False):
    """Placeholder two-node graph for Phase 0. Its only job is to prove the
    checkpoint/resume mechanism that every real Movement 1/2/3 node (Phase 1+)
    will reuse — real ingest/extract/reconcile/etc. nodes replace stage_a/stage_b,
    the graph-building and checkpointing pattern does not change.
    """
    graph = StateGraph(PipelineState)
    graph.add_node("stage_a", _stage_a)
    graph.add_node("stage_b", _stage_b)
    graph.set_entry_point("stage_a")
    graph.add_edge("stage_a", "stage_b")
    graph.add_edge("stage_b", END)

    interrupt_after = ["stage_a"] if interrupt_after_stage_a else []
    return graph.compile(checkpointer=checkpointer, interrupt_after=interrupt_after)
