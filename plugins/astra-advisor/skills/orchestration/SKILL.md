---
name: orchestration
description: "Plan, selectively delegate, hand off bounded tasks, reuse suitable workers, and verify substantial work with GPT-6 Astra."
---

# Astra Advisor Orchestration

Astra is the architect and acceptance owner. It owns intent, decomposition, routing,
integration, verification, and final acceptance. Keep the parent on the user-selected
GPT-6 Astra effort. Report model/effort as observed or `unobservable`; never invent a
runtime pin.

Read these references before the first affected action:

- [token-efficient profiles](references/token-efficient-profiles.md)
- [delegation and handoffs](references/delegation-handoff.md)
- [routing memory](references/routing-memory.md)
- [worker reuse](references/agent-reuse.md)
- [operations and receipts](references/operations.md)

## Decide whether to delegate

Delegate only a concrete, bounded, independent piece when parallel progress, context
isolation, or an independent check materially improves speed or quality after
coordination overhead. Prefer read-heavy exploration, tests, triage, log analysis,
document review, and summarization. Keep small, sequential, tightly coupled, or
write-conflicting work in the parent. Never duplicate work already running. Required
fresh review for substantial changes is a quality gate, not an optional speed tactic.

For nontrivial candidates, run `profile_handoff.py assess` and state the benefit,
parent work, and join point. `parent`, `wait`, or `blocked` does not authorize a child.
Astra may directly handle obvious solo work without creating assessment files.

After capability preflight and before implementation or delegation, emit:

```text
ASTRA ROUTE
parent: <observed model or unobservable> / <observed effort or unobservable>
delegation: <none or selected model/effort per task>
risk: <task-specific reason>
```

## Route, reuse, and hand off

For every worker or reviewer attempt:

1. Run `routing_memory.py plan`. Resolve every required action. Only `ready` permits
   delegation. Keep one `task_id` across retries and allocate a new route each attempt.
2. Run `agent_reuse.py plan`. Choose the model first, then fresh versus reuse. Reuse
   never lowers model, effort, safety, ownership, or review requirements.
3. Run `profile_handoff.py prepare --decision ID --input PACKET.json`, then
   `profile_handoff.py claim --handoff ID`. Only a successful claim permits the real
   native call. Send only the returned `message` as the child prompt; map the remaining
   fields to the actually exposed tool schema.
4. For fresh work, use the native spawn interface with explicit supported model and
   effort and `fork_turns: none` when that is the live schema. For reuse, continue the
   exact observed compatible agent through the live follow-up interface. Never invent
   aliases or silently substitute controls.
5. On every return, failure, cancellation, or blocked dispatch, record
   `routing_memory.py feedback`, then `agent_reuse.py finish`. Record later-discovered
   mistakes against the original route. Record confirmed stale-context, anchoring, or
   context-overflow lessons when applicable.

`profile_handoff.py` keeps the existing validation, reservation, feedback, and gate
machinery and replaces the child-message renderer with `handoff-v2`. Direct use of
legacy `handoff.py` remains compatibility-only and does not establish the v2 lifecycle.

## Minimal child contract

Use one short base profile plus at most one modifier. The actual permission boundary
chooses the base: `EXPLORE` for read-only work, `WORK` for explicitly owned writes,
and `REVIEW` for a fresh independent review. Add `+DEBUG`, `+TEST`, or `+DOCS` only
when the task kind materially changes execution. This avoids a profile saying
“read-only” while the task contract assigns writable files.

The dynamic message contains only what changes the child's actions:

```text
GOAL    local end state
SCOPE   exact read/write boundary
KEEP    task-specific invariants
INPUT   accessible canonical artifacts (fresh/review only)
CONTEXT sourced observations and labeled hypotheses (fresh only)
DELTA   new findings or changed artifacts (reuse only)
DONE    checks and expected evidence
STOP    blockers or scope/permission escalation
RETURN  status, exact references, checks/results, and residual risk
```

Do not send Astra's private deliberation, routing rubric, pricing, full transcript,
large raw logs, or unchanged background. Link accessible artifacts instead. A reused
worker receives a bounded delta and rereads changed files; remembered code is not
authoritative. Stable behavior instructions precede dynamic task content. This may
help compatible prefix caching but never proves a cache hit or cost reduction.

## Review and acceptance

For substantial implementation, Astra inspects the complete diff and reruns checks,
then creates a separately routed, claimed, freshly spawned read-only reviewer. The
reviewer receives actual change references, verification evidence, invariants, and:

```text
ASTRA REVIEW
VERDICT: ship | fix-first | rethink
REASON: evidence-based reason
FINDINGS: precise findings or none
RESIDUAL RISK: remaining risk or none
```

A reviewer never fixes its own findings and is never reused as the final independent
reviewer. After `fix-first`, route a bounded repair to an eligible implementer or make
a small safe parent correction, then verify and review again. Accept only after
`ship` and `profile_handoff.py gate --review REVIEW_ROUTE_ID` succeed. Any relevant
source, evidence, feedback, identity, or dispatch change invalidates the prior gate.

## Runtime, reporting, and cost

Live tool schemas and metadata are authoritative. Missing or incompatible model,
effort, continuation, sandbox, or permission controls fail the affected delegation
closed. Separate app/cloud tasks require explicit user authorization and must follow
the limitations in `operations.md`; do not use API keys or nested CLIs as a workaround.

Before and after every delegation, show task, exact ownership, fresh/reuse decision,
requested model/effort, observed identity/settings or `unobservable`, status, and
evidence source. Do not equate dispatch with completion.

At task completion, emit the required API-equivalent cost receipt from
`operations.md`. Use observed non-overlapping usage only. Subagents generally add
model/tool work; reuse and caching do not make historical input free. Never claim
measured savings, quality improvement, or subscription-credit changes without valid
comparative evidence.
