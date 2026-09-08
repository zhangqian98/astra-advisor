# Safe worker context reuse (reuse-v1)

This extension prefers continuing a suitable existing worker over spawning another
worker for the same bounded task. It preserves the routing-memory risk/model floors,
independent review and snapshot-bound acceptance checks. This reference takes
precedence over older blanket spawn/parent-repair language in `operations.md` and
`routing-memory.md`; it does not weaken their model, evidence or review requirements.

## What this does and does not do

[agent_reuse.py](../../../scripts/agent_reuse.py) is a local Python 3.10+ policy and
receipt tool using the existing routing-memory SQLite store. It does not invoke,
intercept or install native subagent tools. Astra must run the commands AND perform
the corresponding native actions. A receipt alone is not an actual resumed agent.
No API keys, external inference CLI, daemon, background worker or network calls are
added. Native capabilities and runtime evidence remain authoritative.

Continuing a worker can avoid repeating code exploration and reconstructing the
same task context. **It does not make historical input free, guarantee a prompt
cache hit, or prove a net cost reduction.** Cached tokens are a subset of input,
not additional tokens and not zero-priced. Context growth can make continuation
more expensive. Actual usage is kept separate from hypothetical fresh-worker or
all-Astra comparisons. Never claim subscription-credit savings from API estimates.
See [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
and [Codex subagents](https://developers.openai.com/codex/subagents/); the currently
exposed native schema, not these links or a hardcoded tool name, decides capability.

## Mandatory lifecycle

Resolve `agent_reuse.py` and `routing_memory.py` relative to this installed reference.
Use `--repo` for the user's WORKING repository, not the installed plugin checkout.
Keep inputs, observations and receipts in the private evidence directory returned
by `routing_memory.py init`. Never commit them or embed personal identifiers in examples.

1. Inspect the task and live native schemas. Run `routing_memory.py plan` to choose
   the model/effort FIRST. Address every required process correction. Retrying the
   same task keeps its task ID but needs a NEW model route ID on every attempt.
2. Run `agent_reuse.py plan --route ROUTE_ID --context CONTEXT.json`. Announce
   `ASTRA CONTEXT`, decision ID, `fresh/reuse/wait/blocked`, requested model/effort,
   candidate ID when relevant and the reason. A candidate is only a suggestion.
   `wait` means wait/reconcile the existing worker; do not spawn duplicate work.
3. Immediately before native dispatch, run `agent_reuse.py claim --decision ID`.
   Only exit 0 permits dispatch. Claims reserve the worker and exact writable files
   transactionally across cooperating local sessions. Any new feedback since the
   model route, stale evidence, changed source snapshot, or conflicting reservation
   rejects the claim. Recompute the model route AND reuse decision instead of forcing it.
4. For `fresh`, use the observed native spawn interface with explicit selected
   model/effort and `fork_turns: none` when that is its actual schema. For `reuse`,
   continue the EXACT observed native agent/thread with a bounded delta using the
   actual live follow-up interface. Some hosts expose `send_input`, `resume_agent`
   or `followup_task`; these are examples, not aliases or fabricated tool contracts.
   If a closed agent first needs reopening, confirm preserved identity/model/effort
   before sending the task. Do not put spawn-only arguments on a follow-up call.
   Unknown or incompatible controls require a fresh, separately claimed route or
   safe parent work; never silently downgrade a selected model to preserve context.
5. On return (including failures, cancellation and blocked dispatch), record
   `routing_memory.py feedback` FIRST. Then run `agent_reuse.py finish --input
   RESULT.json`, binding the real feedback ID and claim ID. Confirm the worker is
   idle/closed, or that dispatch never started. A timeout is NOT proof it stopped.
   An unresolved claim intentionally remains reserved after crashes: inspect or stop
   the actual worker, record evidence-backed blocked/cancelled feedback and finish
   that claim before retrying. There is no blind force-unlock or automatic expiry.
6. If a confirmed reused-context error is found now or later, record the failure
   against its ORIGINAL model route and agent, then `agent_reuse.py lesson --feedback
   EVENT_ID --cause stale_context|anchoring|context_overflow --evidence FILE`.
   Use old feedback cause `context_gap`, `verification_gap` or a investigated
   `unknown`, not `capability`/`environment`/`spec_gap` merely to force this mechanism.
   Successes and failures both remain in history. Do not let workers grade themselves.
7. For substantial changes, parent diff inspection/checks and `routing_memory.py
   verify` precede a separately routed, CLAIMED, genuinely fresh read-only reviewer.
   Record review feedback and finish its dispatch. Use `agent_reuse.py gate --review
   REVIEW_ROUTE_ID` for final acceptance: it validates observed dispatch receipts
   then invokes the original snapshot-bound gate. Calling only the old gate does
   not establish reuse-enabled acceptance. Changed source/evidence requires a new
   verification and NEW independent review, even after a tiny correction.

A `fix-first` finding may go back to the original implementer through a newly routed
and claimed continuation; it no longer forces Astra to perform every repair itself.
Astra may still make a small safe correction directly. If the correction changes the
model/risk floor, choose a fresh suitably capable worker instead. The reviewer never
implements its own finding and is never reused as the final independent reviewer.

## Decision inputs

An illustrative first-dispatch context (NOT runtime evidence):

```json
{
  "session_id": "opaque-parent-session",
  "ownership": ["src/example.py"],
  "continuation": "same_task",
  "candidate_agent_id": null,
  "agent_state": "unobservable",
  "context_state": "unknown",
  "delta_ready": false,
  "observed_model": null,
  "observed_effort": null,
  "continuation_tool": null,
  "evidence": ["current-native-observation.json"],
  "context_tokens": null,
  "context_limit": null
}
```

Supply real evidence; the example file is not bundled as a fake observation. On a
continuation, candidate ID must match an earlier FINISHED dispatch in this parent
session and worktree. Record current idle/closed state, exact observed model/effort,
`context_state: usable`, `delta_ready: true` and the actual exposed continuation tool
name in `continuation_tool`. Its evidence must document the current tool contract
and state, not simply repeat the requested settings. If native context size is
unobservable, leave both counters null; `usable` then represents the parent's
explicit evidence-backed qualitative assessment, not invented telemetry.

Ownership uses exact portable relative writable file paths, not directories/globs;
read-only work uses `[]`. Only one concurrent writer may own a file. Current owner
and context evidence must account for other workers' or parent edits. Session IDs
are opaque runtime labels, not usernames or absolute paths. A reopened parent gets
a new session ID unless continuity is actually confirmed. Worktrees share learned
history but never automatically share live workers or their working directories.

Default reuse eligibility:

- Same parent session, worktree and runtime epoch; same observed model AND effort;
  same task kind/domain/pattern/scope and writable ownership; same task ID by default.
- `related_task` is an explicit opt-in for a small follow-up within those same
  boundaries, after Astra confirms relevance. Unrelated work gets a fresh worker.
- Usable context, bounded delta prepared, current native continuation capability,
  confirmed earlier execution, and no learned context-failure caution.
- At most four continuations per worker chain; no more than six hours since last
  completion; known context usage below 75% of its observed limit. Decisions expire
  after five minutes. These are conservative versioned policy heuristics, NOT cache
  retention guarantees or benchmark-calibrated optimal values.
- Two failed attempts on the same worker chain require a fresh context. Existing
  three-failed-attempt task limits and model upgrades still take precedence.

A model/effort upgrade, stale/suspect/unknown context, boundary drift or missing
capability produces `fresh` rather than silently continuing. `wait`/`blocked` exit 3;
invalid inputs and failed claims exit 2. No nonzero result authorizes a native call.

## Small delta, not a replay of the entire conversation

A continuation handoff contains only the current bounded goal, exact findings,
changed interfaces/files since the last turn, relevant test failures and explicit
acceptance checks. Link to the current local artifacts instead of pasting the full
parent transcript or entire source tree again. The worker must reread changed owned
files and relevant dependencies; remembered code is not authoritative after edits.

When refreshing is necessary, send a compact, parent-reviewed factual checkpoint:
current goal, owned paths, interfaces, verified findings, failed hypotheses, remaining
checks and evidence references. Do not copy speculative old reasoning as instruction.
Do not reuse solely because many files were read: stale context and anchoring can
cost more than starting again. Never reuse an implementer as its own reviewer.

## Finish, feedback, audit and learning

```json
{
  "claim_id": "actual-claim-id",
  "feedback_id": "actual-routing-feedback-id",
  "actual_mode": "reuse",
  "agent_state": "idle",
  "evidence": ["native-completion.json"],
  "usage": {
    "call_id": "unique-observed-call-id",
    "input_tokens": null,
    "cached_input_tokens": null,
    "output_tokens": null,
    "latency_ms": null
  }
}
```

`usage` may be omitted. When present it describes ONE observed atomic call, never a
cumulative session total. Unknown values are null; cache input must be a known
subset of input. Full evidence, including usage provenance, belongs in the private
completion file. A reused agent ID is constant, but each call, model route, decision
and claim is new. Never add a parent-inclusive aggregate to its child totals. The
existing cost calculator remains authoritative for API-equivalent receipts.

`actual_mode: unobservable` preserves honesty when continuity or dispatch cannot be
confirmed; it cannot establish reuse-enabled acceptance or seed reusable context.
A mismatched native agent is not successful reuse. Unfinished native workers keep
reservations until evidenced as stopped. Claims coordinate only callers following
this protocol, not arbitrary OS processes or unrelated tools.

`report` separates fresh/reused/unobservable attempts, failures, observed token/cache
counts and missing metrics. It does not label a raw group difference as causal
savings. One confirmed context failure triggers seven days of caution for the exact
repository/runtime/task-family/model/effort bucket. After that, at least three
independent failed tasks, decayed sample mass >=2 and failure fraction >=0.35 retain
caution; observations decay with a 30-day half-life and expire after 90 days. This
adapts context strategy, not model weights. Repeated retries in one task do not
become independent samples. Later discovered errors count even after initial success.

Use `routing_memory.py void` with evidence to retract wrong feedback. Its dependent
context lesson then stops affecting decisions while audit records remain. Stale
lesson evidence is not used to teach a rule. Lessons are fixed codes and hashes,
not executable prose or automatic edits to skills. All session receipts and history
stay inside Git metadata. No personal information, private task context or history
is automatically uploaded to GitHub. The local database is not tamper-proof against
the same OS user, and recorded judgments do not establish perfect causal attribution.

Run the tests with:

```sh
python3 -B -m unittest discover -s plugins/astra-advisor/tests -p 'test_*.py'
```

Tests exercise policy, concurrency and evidence invariants with synthetic fixtures;
they are not a live Astra/worker benchmark or proof of lower task costs.
