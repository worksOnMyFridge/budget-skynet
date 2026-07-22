# Cost engineering

An autonomous agent that competes for small payouts only makes sense if a run is cheap. Keeping the
cost per job low is a design constraint, not an afterthought — here's how it's kept down.

High-level and sanitized: the mechanisms, not the bidding/pricing strategy.

## Model routing — cheap by default

Two models, picked per task rather than globally:

- **Haiku** handles the overwhelming majority of calls — job classification, filtering, short work.
- **Sonnet** is reserved for what actually benefits from it: code generation, competition entries,
  higher-value jobs.

The router chooses by deliverable type and budget: code paths get Sonnet, documentation-style work
gets Haiku, and the rest is decided against a budget threshold. Expensive tokens are spent only
where they change the outcome.

## Hard cost bounds

Cost isn't left to good behavior — it's bounded by mechanisms outside the agent's reasoning:

- **Per-job circuit breaker** — every model call on a job is counted, and past a limit further calls
  are refused (see [`snippets/circuit_breaker.py`](../snippets/circuit_breaker.py)). A runaway loop
  can't silently rack up a bill.
- **Environment cost ceiling** — a per-run / per-day cost limit lives in environment config, which
  the agent can't edit. Once the ceiling is hit, the run stops. This is the un-bypassable backstop
  behind the circuit breaker.

## Not paying twice — rebid optimization

When the agent re-bids on a job it has already analyzed, it skips the work it already did — the
requirements analysis and the proposal generation — instead of re-running them. On a busy run that
avoids roughly a hundred redundant cheap calls that would otherwise add up for no new information.

## Cheap memory

Semantic recall would be expensive if every past job were stored as full-precision vectors. Instead
the vectors are **binary-quantized** and searched by Hamming distance — a large storage and compute
saving versus float32, for recall that's more than good enough to catch near-duplicate jobs.

## The through-line

Every one of these is the same idea as the guardrails: don't trust the agent to be frugal, make
frugality structural. Cheap-by-default routing, hard limits it can't override, no repeated work, and
a memory layer that's cheap to keep. That's what makes leaving it running on a cron viable.

---

*Cost-engineering decisions only — no pricing strategy and no absolute figures that would expose the
economic edge.*
