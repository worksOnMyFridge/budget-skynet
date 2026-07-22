# Evaluation

How the agent knows a deliverable is good *before* it ships — the part that turns "an LLM generated
some code" into "a change that passed objective checks and an independent review."

High-level and sanitized: no production code, no prompts, no bidding/pricing strategy.

## Why a harness at all

The agent competes for paid jobs. Sending broken work to a client costs money and reputation, and
"the model was confident" is not evidence of correctness. So quality is measured, not assumed — and
measured *offline*, against a fixed set of tasks, not discovered in production.

## Two layers of grading

Every deliverable type is graded on two independent signals:

**1. Objective signal (primary).** The deliverable is built and tested inside an
[E2B](https://e2b.dev) sandbox:
- run its tests (e.g. `pytest`) and grade pass/fail,
- do a **publish dry-run** (npm / PyPI) so a package that can't actually publish is caught before it
  ever reaches a registry.

This layer is deterministic — it either builds and passes or it doesn't. It's the signal that
carries the most weight, precisely because it doesn't depend on a model's opinion.

**2. LLM judge (secondary).** A separate model reviews the deliverable against a **binary-question
rubric** derived from the task's acceptance criteria — each criterion is checked explicitly ("does
it satisfy X? yes/no") rather than collapsed into one fuzzy score. The judge returns a structured
PASS/FAIL with concrete feedback that feeds the fix loop.

## Per-type evals

Each of the 30+ generator types has its **own eval** built on a small dataset of **real marketplace
tasks** (a handful per type), deliberately mixed — NEAR-specific and general, including a task
shaped like a real production-accepted job. Quality is therefore measured *per deliverable type*,
not as one global average that hides weak spots.

Dataset hygiene is part of the work: mislabeled tasks (e.g. a package task filed under the wrong
type) get fixed, because an eval is only as honest as its dataset. Each eval writes its results to a
file so scores are trackable over time and a regression is visible rather than silent.

## Guarding against a biased judge

A single LLM judge tends to drift toward PASS, and a non-deterministic judge makes scores jump run
to run. Two mitigations:

- **Determinism** — the judge is run for reproducible scoring, so a change in score reflects a change
  in the deliverable, not sampling noise.
- **A second lens** — a requirements-focused review uses a **different model family** than the maker,
  to reduce correlated blind spots (the maker and the checker failing the same way).

The objective sandbox layer is the backstop: even a lenient judge can't wave through code that
doesn't build.

## What "good" means here

The harness measures **intent, not proxy**. "It compiles" or "it runs" is necessary but not
sufficient — the acceptance-criteria rubric checks that the deliverable does *what the task asked
for*. A green build on the wrong thing is still a fail.

## Where it fits

The eval harness runs offline during development. At run time, the same philosophy gates every live
job through the [quality reviewer](architecture.md#quality-reviewer): generate → sandbox build &
test → judge → bounded fix loop, with a pre-submit check that the deliverable matches the task
before anything is submitted.

---

*Design and methodology only. The production evals, datasets, prompts, and the bidding strategy are
intentionally not part of this repository.*
