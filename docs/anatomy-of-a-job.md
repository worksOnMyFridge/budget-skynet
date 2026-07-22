# Anatomy of a completed job

The architecture describes the loop in the abstract. This is one job followed end to end, so the
moving parts connect to something concrete.

> **Representative and sanitized.** The job below is illustrative — shaped like the real work the
> agent handles (small, well-specified packaging tasks), but not a transcript of a specific client's
> job. No client identifiers, no real job text, no bidding/pricing numbers.

**The job (representative):** *"PyPI package: a small NEAR RPC helper — a `NearRpc` class with
`view_account`, `check_balance`, and `send_tokens`, using `requests`."*

---

### 1. Intake — `scan_and_bid()`
A cron run wakes the agent. It pulls open jobs from the marketplace and does a cheap first pass:
tag-based rules and a **Haiku** classification decide the deliverable type — here, `python_package`.
No expensive model has been spent yet.

*Component: [Triggers](architecture.md#triggers) → the filter layer.*

### 2. Filter — skip rules + vector dedupe
The job clears the skip rules (it isn't a disallowed category like trading/financial execution).
The agent embeds it and checks **vector memory** for near-duplicates of past jobs — nothing close
enough to skip, so it's worth pursuing. If a very similar job had failed before, that history would
weigh against bidding.

*Component: [Filter layer](architecture.md#component-breakdown) + [Memory](architecture.md#memory).*

### 3. Bid
The agent places a bid. *How* it prices is the private edge and isn't shown here — what matters for
the walkthrough is that the bid is a first-class step with its own gate, and the job is awarded.

### 4. Generate — two-phase, right model for the task
Before writing code, the agent does a **Phase 0** structured read of the requirements (what class,
what methods, what library) and a **Phase 1** technical spec. Then the `python_package` generator
produces the deliverable with **Sonnet** (code-quality work). Untrusted text from the job
description is XML-isolated and treated as data throughout — it can't redirect the generator.

*Component: [Generators](architecture.md#generators) + the [anti-injection guardrail](security.md#untrusted-input--defense-in-depth).*

### 5. Sandbox — build & test
The package is built and tested inside an **E2B sandbox**: `pytest` runs against the generated code,
and a **PyPI publish dry-run** confirms the package can actually publish. The agent never runs the
generated code in its own environment.

*Component: [E2B sandbox](architecture.md#sandbox-e2b).*

### 6. Quality review — with one fix-loop iteration
The **LLM judge** checks the deliverable against a binary rubric built from the task's acceptance
criteria. On the first pass it flags that `send_tokens` lacks input validation. That feedback goes
back into generation; attempt two adds it and passes both the tests and the judge. The fix loop is
bounded and fast-fails on a repeating error, so it can't thrash forever.

*Component: [Quality reviewer](architecture.md#quality-reviewer) — see [`snippets/quality_gate.py`](../snippets/quality_gate.py).*

### 7. Publish + submit
The deliverable passes the **fail-closed secret-scan gate**, then publishes to **PyPI**. The agent
submits the deliverable to the marketplace (package URL + a content hash + timestamp), and logs the
submit response.

*Component: [Publishing routing](architecture.md#publishing-routing) + [secret-scan gate](security.md#output--fail-closed-egress).*

### 8. Outcome — accepted, and the agent learns
The client accepts; **NEAR** is paid out. The agent updates its **operational memory**: the job is
marked completed, daily stats tick up, and a learned pattern from this job is stored so a similar
future task starts from a better place. The run ends with a report to Telegram.

*Component: [Memory](architecture.md#memory) + [Control plane](architecture.md#control-plane).*

---

Every stage left an artifact — a classification, a bid, a sandbox result, a judge verdict, a publish
URL, a memory entry — which is the point: the agent isn't "magically doing work," it's running a
loop where each step is observable and gated.
