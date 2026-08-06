import time
from functools import wraps

from app.db.models import RunStageMetric
from app.db.session import SessionLocal


def timed_node(stage_name: str):
    """Wraps a graph node to record how long its stage took, per run — the
    concrete answer to "what did this cost and where did the time go." Token
    counts and a dollar estimate are left null under the fake provider: it
    makes no real calls, so a fabricated number would be worse than an honest
    gap. AnthropicLLMClient's real calls carry actual `usage` data that a
    future pass can thread through here instead of guessing.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(state):
            start = time.monotonic()
            result = fn(state)
            duration_ms = int((time.monotonic() - start) * 1000)

            run_id = state.get("run_id") if isinstance(state, dict) else None
            if run_id:
                with SessionLocal() as db:
                    db.add(RunStageMetric(run_id=run_id, stage_name=stage_name, duration_ms=duration_ms))
                    db.commit()

            return result

        return wrapper

    return decorator
