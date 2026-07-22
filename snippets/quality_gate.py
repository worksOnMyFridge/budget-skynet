"""
Quality gate — the Maker–Checker loop that guards every submission.

Illustrative, simplified extract from budget-skynet (production code is private).

The point: a deliverable never ships on the generating model's confidence. It goes
through generate -> build & test in a sandbox -> an independent LLM judge that returns
a structured PASS/FAIL with feedback -> a bounded fix loop. Two properties matter:

  1. The success signal is external (a passing test + a separate reviewer), not the
     maker model saying "looks good".
  2. The loop is bounded (max_attempts) and *fast-fails* when the same error repeats,
     so it doesn't burn attempts thrashing on an unfixable deliverable.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReviewResult:
    """Structured verdict from the checker — never just a free-text blob."""
    passed: bool
    feedback: str
    score: int = 0
    issues: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


def quality_loop(
    generate,          # (feedback: str | None) -> dict[str, str]   maker
    test_in_sandbox,   # (files: dict) -> tuple[bool, str]          objective signal
    review,            # (files: dict) -> ReviewResult              checker (LLM judge)
    *,
    max_attempts: int = 7,
) -> dict:
    """Generate -> test -> review -> fix, until it passes or the budget runs out.

    Returns the best deliverable produced. Bounded by max_attempts; fast-fails on a
    repeating error so a stuck job can't monopolize the run.
    """
    best: dict[str, str] = {}
    feedback: str | None = None
    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        files = generate(feedback)
        best = files

        ok, error = test_in_sandbox(files)
        if not ok:
            # Fast-fail: same error two attempts running -> stop wasting calls.
            if error == last_error:
                print(f"   fast-fail: error repeats ({error[:80]})")
                break
            last_error = error
            feedback = f"Build/tests failed: {error}"
            print(f"   attempt {attempt}/{max_attempts}: {error[:120]}")
            continue

        verdict = review(files)         # independent checker
        if verdict:
            return files                # passed test AND review -> ship it
        feedback = verdict.feedback     # reviewer's concrete fixes -> next attempt
        print(f"   attempt {attempt}/{max_attempts}: review FAIL — {verdict.feedback[:120]}")

    print(f"   returning best effort after {max_attempts} attempts")
    return best
