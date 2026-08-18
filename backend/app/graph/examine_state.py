import operator
from typing import Annotated, Optional, TypedDict


class ExamineState(TypedDict, total=False):
    """Movement 2's state uses reducer-annotated fields (Annotated[..., operator.add])
    for anything written by parallel check_one_rule branches — nodes return only
    their own increment, LangGraph concatenates it into the accumulated value.
    This is different from PipelineState's plain fields, which are fine for
    Movement 1's strictly sequential nodes but would conflict if written from
    multiple branches in the same step.
    """

    pile_id: str
    run_id: str
    llm_provider: Optional[str]  # per-run override of LLM_PROVIDER; None means use the env default
    rules: list[dict]  # [{id, rule_text}, ...], loaded once
    current_rule: dict  # set only on the per-branch Send copy of state
    findings: Annotated[list[dict], operator.add]
    stage: str
    stages_completed: Annotated[list[str], operator.add]
    error: Optional[str]
