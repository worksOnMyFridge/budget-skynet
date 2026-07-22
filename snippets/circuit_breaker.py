"""
Per-job circuit breaker for LLM calls.

Illustrative, simplified extract from budget-skynet (production code is private).

The point: an autonomous loop that calls a paid API must not be able to run away.
Instead of trusting the agent's logic to "not loop too much", the cost bound is a
deterministic mechanism the agent cannot reason its way around — every call is
counted, and past a per-job limit the call simply returns None without hitting the
API. The counter is reset before each new job.

This is the cheap, boring control that turns "an LLM in a loop touching money" into
something you can leave running on a cron.
"""
from __future__ import annotations

# Wrapped in a list so nested closures can mutate it without `global`.
_job_call_counter: list[int] = [0]

CLAUDE_CALLS_PER_JOB_LIMIT = 60  # tuned empirically; a real job never needs this many


def reset_job_call_counter() -> None:
    """Reset the per-job call counter. Call this before processing each new job."""
    _job_call_counter[0] = 0


def ask_model(prompt: str, *, model: str = "haiku") -> str | None:
    """Send a prompt to the model, guarded by the per-job circuit breaker.

    Returns the model's text, or None if the circuit breaker has tripped for the
    current job (so the caller degrades gracefully instead of spending more budget).
    """
    _job_call_counter[0] += 1
    if _job_call_counter[0] >= CLAUDE_CALLS_PER_JOB_LIMIT:
        print(
            f"   circuit breaker: {_job_call_counter[0]} calls on one job "
            f"(limit {CLAUDE_CALLS_PER_JOB_LIMIT}) — refusing further calls"
        )
        return None

    # ... real implementation sends the request to the model API here and returns
    # the response text. Omitted: retries, timeouts, prompt caching, structured
    # prefill — none of which change the guarantee above.
    return _call_api(prompt, model=model)


def process_job(job: dict) -> None:
    """Example of the invariant: reset the counter at the start of every job."""
    reset_job_call_counter()  # <- without this, counts leak across jobs and later
    #                            jobs silently hit the limit and get fallback output
    ...


def _call_api(prompt: str, *, model: str) -> str:  # placeholder for the real client
    raise NotImplementedError("wired to the model client in production")
