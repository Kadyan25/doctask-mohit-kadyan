from collections import defaultdict

from app.db.models import RunStageMetric


def build_cost_report(db, run_id) -> dict:
    """Shared by the REST endpoint and the MCP tool — one aggregation, not two
    that could drift."""
    metrics = db.query(RunStageMetric).filter(RunStageMetric.run_id == run_id).all()
    by_stage: dict[str, list[RunStageMetric]] = defaultdict(list)
    for m in metrics:
        by_stage[m.stage_name].append(m)

    stages = []
    total_duration_ms = 0
    for stage_name, rows in sorted(by_stage.items()):
        duration_sum = sum(r.duration_ms or 0 for r in rows)
        tokens_sum = sum(r.tokens_used or 0 for r in rows) or None
        cost_sum = sum(r.cost_estimate or 0 for r in rows) or None
        stages.append(
            {
                "stage_name": stage_name,
                "total_duration_ms": duration_sum,
                "call_count": len(rows),
                "tokens_used": tokens_sum,
                "cost_estimate": cost_sum,
            }
        )
        total_duration_ms += duration_sum

    return {"run_id": str(run_id), "total_duration_ms": total_duration_ms, "stages": stages}
