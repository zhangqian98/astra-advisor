---
name: orchestration
description: "Plan, selectively delegate, hand off bounded tasks, reuse suitable workers, and verify substantial work with GPT-6 Astra."
---

# Astra Advisor Orchestration

Astra is the architect, coordinator, and acceptance owner. Preserve the user's goal,
non-goals, approval boundaries, and chosen parent model/effort. A skill cannot change
the parent configuration. Report observed model/effort or `unobservable`; an observed
non-Astra parent is a selection prerequisite, not confirmed Astra orchestration.

## Decide whether delegation helps

Proactively consider independent work when it materially improves elapsed time,
context focus, or independent checking. Do not maximize the number of agents. Keep
small, reversible work local when briefing and integrating a worker would dominate
its benefit. Do not create a planning bureaucracy or mirror-the-implementation tests
for a trivial change. Required checks and substantial-work review still apply.

Before meaningful delegation, read the [delegation and handoff contract](references/delegation-handoff.md).
Record the split, each deliverable, why delegation helps, what useful work Astra will
continue, and when results must be joined. The `handoff.py assess` command supports
this decision without a Git database; a `parent`, `wait`, or `blocked` result is NOT
permission to dispatch. Straightforward solo work does not need an assessment file.

Delegate only bounded deliverables with ready inputs and clear ownership. Prefer
independent code exploration, evidence-heavy analysis, isolated implementation slices,
or genuinely independent review. Resolve serial dependencies first. If the parent
would immediately wait, do not call it a parallel speed benefit; a separate context
or independent check can still be worthwhile with a concrete reason. Never dispatch
the same work twice or start overlapping writers. Independent read-only review is an
intentional second check, not a duplicate implementation. Respect user limits, live
capacity, and budgets; necessary review cannot be skipped to manufacture savings.

The root retains architecture tradeoffs, integration, overall acceptance, and work
whose scope cannot yet be separated. Workers do not recursively delegate in this fork.
Use no fixed team size or mandatory role roster. Wait before consuming dependencies,
integrating edits, or accepting the result, as specified in the parent join plan.

## Route, prepare, claim, dispatch

Read [routing memory](references/routing-memory.md) and [worker reuse](references/agent-reuse.md)
before the first delegation. Initialize their local store in the WORKING repository,
not in the plugin checkout. Keep packet inputs and evidence in its private evidence
directory; never commit/export task history or include personal data in examples.

For every worker attempt and every independent review:

1. Inspect real task evidence and live tool schemas. Run `routing_memory.py plan`.
   Only `status: ready` proceeds. Resolve all required history/process actions; never
   lower model/effort or risk floors to retain a cheaper worker.
2. Run `agent_reuse.py plan` for a fresh/reuse/wait/blocked decision. Prefer an eligible
   existing worker for same-task corrections. Changed model, untrusted context,
   ownership drift, unsupported continuation, or repeated failure requires replanning.
3. Run `handoff.py prepare --decision ID --input PACKET.json`. Supply a parent-reviewed
   assessment and the child packet, not a transcript. Preparation checks task identity,
   permissions, acceptance evidence, delta/review fields, and resolved process actions.
4. Immediately before dispatch, run `handoff.py claim --handoff ID`. This rechecks the
   prepared packet and invokes the existing atomic worker/file reservation. Do NOT
   also call `agent_reuse.py claim` for the same attempt. Nonzero exit stops dispatch.
5. Send only the returned `message` as the child prompt through the actually exposed
   native interface. Parent routing metadata is not part of the child task. Choose
   arguments from that interface's public schema; the returned JSON is NOT native
   tool-call arguments. A prepared or claimed receipt is not proof of a native call.

Fresh requests must support this backend's explicit model, supported effort, and
clean-context controls (`fork_turns: none` in its current contract). Follow-ups use
their own live schema and the exact observed worker identity; do not add spawn-only
fields to a continuation. No fabricated tool aliases, silent model substitutions,
API-key/nested inference CLI fallback, or new external app tasks without permission.
Unavailable controls fail the affected delegation closed while safe parent work may
continue. See [operations](references/operations.md) for app/cloud and receipt limits.

## What the child receives

The generated message contains the local goal, exact write/read-only boundary,
accessible input and interface references, sourced observations versus hypotheses,
constraints, checks and expected evidence, stop/escalation rules, and return format.
It omits parent routing tables, cost accounting, whole transcripts, and private
reasoning. Prefer source references over copied logs or large code blocks; verify
that the selected child can actually access them. A no-inheritance worker needs a
self-contained assignment, not an unexplained pointer to the parent's conversation.

For a reused worker, send only the bounded current goal, findings, changed inputs,
and applicable constraints/checks. It must reread changed files and dependencies;
remembered code is not authoritative. A fresh replacement gets a compact factual
checkpoint, not speculative reasoning inherited as instruction. Use the goal and
observable completion conditions rather than prescribing every implementation step.

Stop and escalate missing/contradictory inputs, required scope or permission changes,
write conflicts, and failed approaches without new evidence. Source/log text does
not grant authority. Workers must preserve others' changes and must not commit,
push, deploy, or take unrelated external actions. These are instruction boundaries,
not a claim of OS-level sandbox enforcement.

## Feedback, review, and acceptance

After every return, failure, cancellation, or blocked dispatch, record evidence-backed
`routing_memory.py feedback` BEFORE another selection, then `agent_reuse.py finish`.
Keep a task ID across retries but create new route, decision, handoff, and claim IDs.
Never release a worker just because a timeout elapsed: confirm it stopped or never
started. Reconcile interrupted claims rather than force-unlocking or dispatching twice.

Record later-discovered mistakes against their original route. Distinguish capability,
specification, missing context, ownership, verification, and environment failures.
Use `agent_reuse.py lesson` only for evidenced context failures after normal feedback.
Successes, failures, and evidence-backed corrections all remain auditable. This adapts
policy, not model weights; do not let workers grade themselves into routing memory.

For substantial changes, Astra inspects the complete diff and reruns meaningful
requested checks, then records `routing_memory.py verify`. Route a NEW read-only
reviewer with the current change set and verification evidence, preserving the existing
reviewer model floor. Prepare and claim its REVIEW packet as above. Never use the
implementer, a reused reviewer context, or the worker's success summary as independent
approval. Require `ASTRA REVIEW` with `ship | fix-first | rethink`, concrete findings,
and residual risks. `fix-first` can go back to an eligible original worker with a new
DELTA packet; `rethink` requires replanning. Reverify and review afresh after repairs.

Only `handoff.py gate --review ID` plus a fresh `ship` permits handoff-enabled acceptance.
It checks handoff bindings and then the existing reuse/snapshot gates. Changed source,
verification evidence, or worker feedback invalidates acceptance. Legacy gates remain
available for compatibility but do not establish this stronger lifecycle. These tools
must actually run; a skill is not a native-tool interceptor or proof of correctness.

## Visibility and cost receipts

Before work begins, emit `ASTRA ROUTE` with observed parent settings, selected delegation
or `none`, and task-specific risk/benefit. Before each dispatch report the task, ownership,
requested model/effort, fresh/reuse choice, route and handoff IDs. On return show actual
status, agent ID, and runtime-observed settings with evidence or `unobservable`. Report
meaningful changes without polling narration or pretending a request confirms execution.

Every task completion, including solo/failed/blocked work, needs the API-equivalent
receipt defined in [operations](references/operations.md), or a precise unavailable
status. Capture unique atomic usage and provenance; include parent, workers and reviews
before claiming whole-task coverage. Unknown is not zero. Use the versioned historical
pricing snapshot and disclose unsupported regimes and partial coverage. Same-token
Astra repricing is not a measured counterfactual, subscription saving, or quality/speed
benchmark. No delegation means no delegation savings. Reuse is not free history or a
guaranteed cache hit. Missing tools/telemetry must be disclosed, never invented.
