# Architecture

A detailed, sanitized walk through how budget-skynet is put together. High-level only — no
production code, no bidding/pricing strategy, no secrets.

## The loop, end to end

The agent runs as a **stateless job** on a GitHub Actions runner. Each run is one pass of:

```
scan open jobs
  -> filter (cheap model + rules + semantic dedupe)
  -> bid on what's worth it
  -> for each won/eligible job:
       reset per-job circuit breaker
       generate deliverable (right model for the task type)
       build + test in E2B sandbox
       LLM quality review (PASS/FAIL + fix loop)
       secret-scan gate (fail-closed)
       publish to the correct registry
       submit to the marketplace
  -> write run report + memory stats
```

Because the runner is stateless, **all durable state lives outside it** (see [Memory](#memory)),
so a run can crash or be preempted and the next run resumes cleanly instead of duplicating work.

## Triggers

Three ways a run starts:

- **Cron (~every 2 hours)** — the autonomous heartbeat. This path *does* bid automatically.
- **Manual dispatch** (`workflow_dispatch`) — for operator-initiated runs.
- **WebSocket listener** — a long-lived service subscribes to marketplace events
  (`job_awarded`, `dispute`, messages) and triggers a run when the agent wins a job.

A separate **job poller** watches for newly posted jobs and sends the owner a Telegram alert with
bid/skip buttons. This path is **human-in-the-loop by design** — it notifies, it does not
auto-bid. The autonomous bidding happens only on the cron path, where the guardrails below apply.

## Models

Two Claude models, chosen per task:

- **Haiku** — filtering, classification, short/cheap work. The overwhelming majority of calls.
- **Sonnet** — code generation, competition entries, high-value jobs.

Model selection is a function of task type and budget, not a global default. Cheap-by-default,
expensive-only-when-it-pays.

## Generators

**28+ deliverable-type generators**, one module each (npm package, PyPI package, MCP server,
GitHub Action, CLI tool, LangChain tool, data-analysis notebook, HTML app, smart-contract helper,
documentation, …). Each generator:

- loads an **expert "skill" context** file for its type, and
- has its own **objective eval** (`evals/eval_<type>.py`) so quality is measured per type, not
  guessed globally.

A router (`detect_deliverable_type`) maps a job to a generator with priority guards, falling back
to a documentation/markdown generator when nothing specific matches.

## Sandbox (E2B)

Generated code is **built and tested inside an E2B sandbox** before it can be published. The agent
never runs generated code in its own environment. Publishing dry-runs (npm/PyPI) also happen in the
sandbox, so a broken package is caught before it reaches a public registry.

## Quality reviewer

`generate -> test -> judge -> fix`, bounded and fast-failing (see
[`snippets/quality_gate.py`](../snippets/quality_gate.py)):

- **Objective signal first** — build + tests in the sandbox.
- **LLM judge** returns a structured PASS/FAIL with concrete feedback.
- A **fix loop** (bounded attempts) feeds the feedback back into generation, and **fast-fails**
  when the same error repeats.
- A **pre-submit check** confirms the deliverable actually matches the task requirements before it
  goes to the client.

## Reliability & guardrails

- **Circuit breaker** — a per-job cap on model calls, reset before each job
  ([`snippets/circuit_breaker.py`](../snippets/circuit_breaker.py)). Plus an ENV-level daily cost
  ceiling that lives outside the agent's control.
- **Anti-injection** — all external text (job descriptions, web research, social content) is
  treated as data: XML-isolated, sanitized, and never allowed to select tools
  ([`snippets/untrusted_input.py`](../snippets/untrusted_input.py)).
- **Secret-scan gate** — deterministic, fail-closed scan on every publish path
  ([`snippets/secret_scan_gate.py`](../snippets/secret_scan_gate.py)).
- **SSRF guard** — URLs from search results are fetched only if they resolve to public IPs;
  loopback / private / link-local / cloud-metadata addresses are blocked.

## Memory

State lives in two places, both outside the stateless runner:

- **Operational memory (Gist JSON)** — the agent's bookkeeping: which jobs were bid on, submitted,
  failed, or skipped; per-day stats; learned patterns. TTL rules prune it so it doesn't grow
  unbounded.
- **Vector memory (embeddings)** — semantic recall of past jobs, used to skip near-duplicates and
  surface relevant prior outcomes. Vectors are **binary-quantized** (Hamming-distance search) for a
  large memory saving versus float32.

Only evergreen, operational data is stored. Client deliverables are not written to memory; job
listings are public, not personal data.

## Control plane

Two Telegram bots:

- a **reporting bot** that posts a summary after each run, and
- a **control panel** with bid / skip / submit buttons and status commands.

This is the human-in-the-loop surface — enough control to steer the agent without blocking its
autonomous path.

## Publishing routing

Deliverables go to the registry that fits the type — npm, PyPI, GitHub repo, or Gist — with a
dry-run in the sandbox and the secret-scan gate in front of every path.

## Infrastructure

- **GitHub Actions** — the agent runtime (cron + dispatch).
- **Railway** — the always-on services: the API/WebSocket listener and the control bots.
- **Hugging Face** — embeddings for vector memory.

---

*This document describes the design at a level meant for portfolio review. The production
repository, exact prompts, and bidding strategy are intentionally not included.*
