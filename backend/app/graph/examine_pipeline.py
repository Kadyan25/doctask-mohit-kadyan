from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Send

from app.graph.examine_state import ExamineState
from app.graph.nodes.check_one_rule import check_one_rule
from app.graph.nodes.load_rules import load_rules
from app.graph.nodes.produce_findings import produce_findings


def _route_to_rule_checks(state: ExamineState):
    rules = state.get("rules", [])
    if not rules:
        return "produce_findings"
    return [Send("check_one_rule", {**state, "current_rule": rule}) for rule in rules]


def build_examine_graph(checkpointer: BaseCheckpointSaver):
    """Movement 2 (Examine): load_rules fans out to one check_one_rule branch
    per rule, running in parallel — LangGraph's Send/map-reduce pattern, a
    genuinely different orchestration shape from Movement 1's fixed sequential
    pipeline. produce_findings aggregates once every branch has completed.
    """
    graph = StateGraph(ExamineState)
    graph.add_node("load_rules", load_rules)
    graph.add_node("check_one_rule", check_one_rule)
    graph.add_node("produce_findings", produce_findings)

    graph.set_entry_point("load_rules")
    graph.add_conditional_edges("load_rules", _route_to_rule_checks, ["check_one_rule", "produce_findings"])
    graph.add_edge("check_one_rule", "produce_findings")
    graph.add_edge("produce_findings", END)

    return graph.compile(checkpointer=checkpointer)
