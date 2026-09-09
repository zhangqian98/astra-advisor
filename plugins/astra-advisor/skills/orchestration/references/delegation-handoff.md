# Selective delegation and bounded handoffs (handoff-v2)

This reference governs whether Astra delegates and how a child task is packaged. It
preserves the model/risk floors in `routing-memory.md`, the continuation policy in
`agent-reuse.md`, and the evidence and acceptance requirements in `operations.md`.
[`token-efficient-profiles.md`](token-efficient-profiles.md) defines the compact
renderer. These are local workflow rules based on official prompting principles, not
an OpenAI-endorsed routing benchmark.

## Official basis

Reviewed 2026-09-08:

- [Codex Subagents](https://developers.openai.com/codex/subagents/): delegate
  independent work; prefer read-heavy parallelism; account for token and coordination
  overhead; state division, wait/join behavior, and returned output.
- [Codex best practices](https://developers.openai.com/codex/learn/best-practices/):
  include Goal, Context, Constraints, and Done when.
- [GPT-6 Astra model guidance](https://developers.openai.com/api/docs/guides/latest-model/):
  tell Astra when and how much to delegate and calibrate verification to the change.
- [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching/):
  keep stable shared instructions first, append changing content, and measure cache
  behavior instead of assuming it.

## Delegation decision

A candidate must be concrete, bounded, independent, input-ready, and free of duplicate
work or overlapping ownership. Astra then identifies one material benefit:

- `parallel_progress`: parent and child can perform useful non-overlapping work before
  the declared join point;
- `context_isolation`: noisy exploration, logs, tests, or document processing stays
  outside the main thread and returns a distilled result;
- `independent_check`: a fresh perspective materially improves quality.

Keep the task in the parent when coordination overhead dominates or no material
benefit exists. Return `wait` when dependencies, ownership, or duplicate work must be
resolved. Respect user delegation restrictions and available capacity. A required
fresh final review may become `blocked`; it is never silently skipped.

`profile_handoff.py assess` records this parent-supplied judgment. It does not measure
latency, token savings, task difficulty, or dispatch success. Simple solo work need not
create an assessment file.

## Handoff contract

Astra supplies only information the child needs to act:

1. one local goal;
2. exact read/write scope and task-specific invariants;
3. accessible canonical inputs;
4. sourced observations and explicitly labeled hypotheses;
5. checks paired with expected evidence;
6. stop/escalation conditions;
7. a compact return contract.

A fresh worker gets self-contained inputs because it may receive no parent conversation.
A continuation gets a bounded delta plus still-valid constraints and completion
criteria. A reviewer gets actual change and verification references and remains fresh
and read-only. Do not send routing scores, pricing, private deliberation, complete chat
history, or large raw logs. Reference accessible artifacts instead.

## Required lifecycle

```text
profile_handoff.py assess                    # nontrivial candidate
routing_memory.py plan                       # model/effort and history floors
agent_reuse.py plan                          # fresh/reuse/wait/blocked
profile_handoff.py prepare --decision ...    # validate and render handoff-v2
profile_handoff.py claim --handoff ...       # reserve agent/files and recheck evidence
native spawn or continuation                 # actual live schema
routing_memory.py feedback
agent_reuse.py finish
parent diff/check verification
fresh independent review
profile_handoff.py gate --review ...
```

Only successful `plan`, `prepare`, and `claim` results authorize a native dispatch.
`claim` binds the packet hash, route, reuse decision, model/effort, source snapshot,
evidence, and exact writable ownership. A changed packet, source tree, runtime schema,
feedback record, or conflicting reservation requires replanning. Preparation alone is
not dispatch.

Use only the returned `message` as the child prompt. Map model, effort, agent identity,
and spawn/continuation controls to the current native tool schema. Never send the
whole JSON object as guessed tool arguments. Never invent a follow-up alias, claim a
submitted model as runtime-confirmed, or preserve stale context by downgrading the
selected route.

## Join and return

For parallel work, Astra states what it will do concurrently and joins before
integration. For context isolation, it may wait immediately but must name that benefit.
For independent review, join before acceptance. Child returns are distilled and include
status, exact references, checks actually run and results, unrun checks, blockers, and
remaining risk. Raw logs remain in accessible artifacts.

The parent owns integration and acceptance. Children do not recursively delegate,
change user success criteria, expand scope, commit, push, deploy, purchase, or perform
unrelated external actions unless separately and explicitly authorized by the user and
supported by the live environment.

## Review and compatibility

A final reviewer is a new independent read-only agent, never a reused implementer or
prior reviewer. It inspects actual changes and parent verification evidence. `ship` is
necessary but not sufficient without the snapshot-bound v2 gate.

`profile_handoff.py` lazily reuses `handoff.py` validation and storage while setting
policy `handoff-v2` and replacing its renderer. Legacy `handoff.py` remains for
compatibility. Do not claim the v2 contract for legacy handoff records; re-plan and
prepare unfinished work after upgrading.

The 6,000-byte compact-message guard and micro-profile mapping are repository policies,
not official context limits. The tools cannot prove that task facts are true, that an
agent followed its prompt, or that shorter prompts reduced total cost. Use real outcome
and usage evidence.
