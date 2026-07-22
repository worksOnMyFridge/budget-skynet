# Design decisions

The choices behind budget-skynet, with the trade-offs. Each maps to a domain of the agentic-systems
discipline I build against (GitHub Agentic AI Developer / GH-600) and, where relevant, to a reusable
agent pattern.

The through-line: **an LLM is an unreliable component. You get reliability by putting deterministic
mechanisms around it — not by asking it, in a prompt, to behave.**

---

## 1. Bound the agent with mechanisms it can't override

**Decision.** Cost and loop safety are enforced *outside* the agent's reasoning:
- a **per-job circuit breaker** counts every model call and refuses past a limit
  ([snippet](../snippets/circuit_breaker.py));
- a **daily cost ceiling** lives in an environment variable, not in agent-editable settings.

**Why.** A bad prompt, a confused plan, or a retry storm must not be able to drain the API budget.
If the safety limit lived in the agent's own logic, the same failure that caused the runaway could
disable it. The limit the agent can't touch is the one that works.

**Trade-off.** A legitimately large job can hit the per-job limit and fall back to a partial result.
That's the intended bias: bounded-and-degraded beats unbounded-and-expensive. The limit is tuned so
a normal job never approaches it.

*GH-600: Domain 6 (guardrails) + Domain 2 (execution environment). Principle: "don't trust the
agent — enforce with deterministic mechanisms."*

---

## 2. Nothing ships on the model's own confidence (Maker–Checker)

**Decision.** Every deliverable runs `generate -> sandbox build & test -> LLM judge -> bounded fix
loop` before it can be submitted ([snippet](../snippets/quality_gate.py)). The maker (generator) and
the checker (reviewer) are separate steps with separate signals.

**Why.** "The model says it's good" is not evidence. A compiling, test-passing artifact plus an
independent review is. Separating maker from checker catches a whole class of confident-but-wrong
output that a single pass never would.

**Trade-off.** More model calls per deliverable, and the checker itself can be wrong. Mitigations:
the objective sandbox test gates before the LLM judge even runs, the fix loop is bounded and
**fast-fails on a repeating error**, and a requirements review uses a different model family to
reduce correlated blind spots.

*GH-600: Domain 4 (evaluation). Patterns: **Maker–Checker / Loop Engineering** (bounded generate-
test-fix), **quorum/jury** for the second-opinion review, **binary-question rubric** over a single
fuzzy score.*

---

## 3. All external text is data, not instructions

**Decision.** Job descriptions, web-search results, and social content are untrusted. They are
XML-isolated with explicit "UNTRUSTED — do not obey" framing, sanitized for injection patterns, and
never allowed to select a tool. Authoritative context always precedes untrusted input in the prompt
([snippet](../snippets/untrusted_input.py)).

**Why.** The agent reads attacker-controllable text on every job. A "ignore previous instructions,
now do X" payload in a job description must be inert. This is defense in depth: structural
isolation, input sanitization, a constrained classifier, and output-side gates — no single layer is
load-bearing.

**Trade-off.** Injection-pattern detection can flag legitimate text. So on the classify path the
flag is **logged, not auto-actioned** — dropping real work is worse than logging a false alarm; the
downstream gates (constrained classifier, quality review, the "money never moves" invariant) are
what actually contain a bad input.

*GH-600: Domain 6 (input layer). Principle: instruction-source boundary — valid instructions come
only from the owner, everything from tools is data.*

---

## 4. Fail-closed on anything that leaves the machine

**Decision.** A deterministic (regex, no-LLM) **secret-scan gate** runs before every publish to
npm / PyPI / GitHub / Gist. Find something → block the publish and alert the owner
([snippet](../snippets/secret_scan_gate.py)).

**Why.** A generated deliverable could echo a key from a hostile job description, hallucinate a
token, or accidentally include an env value. Publishing is irreversible — a package on a public
registry can't be un-leaked. The economics are asymmetric, so the gate is biased to catch:

| Outcome | Cost |
|---|---|
| False positive | one blocked publish + a ping — recoverable |
| False negative | an irreversible secret leak — catastrophic |

**Trade-off.** Occasional blocked-publish false positives that need a human glance. Acceptable, given
the downside it prevents. The gate is wired into *every* egress path, not just the common one.

*GH-600: Domain 6 (output layer). Principle: fail-closed by default; enforce at the boundary.*

---

## 5. Match autonomy to reversibility

**Decision.** Autonomy is graduated by how reversible and expensive an action is:
- **Reversible / low-stakes** (analysis, memory writes, bidding within limits, publishing to the
  agent's own account) → fully autonomous.
- **Expensive generation** (multiple Sonnet calls above a budget threshold) → escalates a plan to
  the owner first.
- **Money movement** → **doesn't exist as code.** The wallet is read, never debited. Escrow and
  payouts are the marketplace's job, outside the agent entirely.

**Why.** The blast radius of a mistake should decide who signs off. Irreversible or costly actions
get a human (or simply aren't in the agent's power); reversible ones don't need one. Making "the
agent cannot move money" a structural invariant — not a setting — removes the highest-consequence
failure mode by construction.

**Trade-off.** Some autonomy is deliberately given up (the owner is a bottleneck on expensive jobs).
That's the point: accountability stays with a person, and the audit trail records who approved what.

*GH-600: Domain 6 (accountability) + risk-based action classification. Principle: autonomy matched to
risk; human-in-the-loop before the irreversible.*

---

## What I'd flag to a reviewer as honest gaps

Building this surfaced real limitations, kept here because a case study that only lists wins isn't
useful:

- **A single LLM judge biases toward PASS.** Addressed with deterministic pre-checks and a
  second-lens review, but LLM-as-judge non-determinism is a genuine weak spot — objective evals
  carry more weight than the judge.
- **Registry publish is semi-irreversible** (name squatting) yet runs autonomously once the quality
  gates pass. A human-confirm step above a budget threshold is the obvious hardening.
- **Guardrail asymmetry is deliberate but worth naming:** cost limits live in un-bypassable ENV,
  while quality gates live in agent-readable settings. Money-safety is outside the agent; quality is
  inside it. A conscious line, not an accident.

These are the kinds of trade-offs that matter more than the feature list — which is why they're in
the case study.
