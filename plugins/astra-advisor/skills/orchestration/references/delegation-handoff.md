# Selective delegation and bounded handoffs (handoff-v1)

This reference takes precedence over older blanket-spawn and one-line handoff examples
in `operations.md`, `routing-memory.md`, and `agent-reuse.md`. It preserves their risk,
runtime, history, reuse, reservation, and independent-review requirements. This is a
local implementation of prompting principles, not an OpenAI-endorsed routing algorithm.

## Official sources and the boundary of the adaptation

Reviewed on 2026-09-08; public documentation and tool schemas can change.

| Official source | Principle used here |
| --- | --- |
| [Codex / ChatGPT Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) | Identify parallel pieces, join points, and returned results. Subagents have their own work and token overhead. |
| [Astra model guidance](https://developers.openai.com/api/docs/guides/latest-model) | Prompt delegation according to useful parallelism and quality; calibrate verification to the actual change. |
| [Using Goals in Codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex) | Define the end state, evidence, constraints, and what to do when blocked. We use a bounded task contract, not a new persistent Goal. |
| [Iterating development workflows](https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex) | Carry material discoveries and provenance, label uncertainty, and reference canonical artifacts rather than copying transcripts. |
| [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) | Treat cache behavior as runtime/model-specific; do not equate worker continuity with free input or guaranteed savings. |

The official Astra example permits recursive delegation in suitable harnesses. This
fork deliberately keeps delegation in the parent, retaining single-owner coordination.
The three packet types, deterministic checks, 24 KB payload guard, stricter reviewer
floor, and mandatory receipts are LOCAL policy choices, not official performance
thresholds. Native Codex and Responses API multi-agent interfaces are not interchangeable.
Current public tool contracts win over examples; this change adds no runtime adapter.

## When to delegate

Ordinary small tasks can stay in the parent without creating JSON or extra agents.
For a meaningful candidate, identify the bounded output, available inputs, exact file
ownership, dependency order, likely benefit, and coordination overhead. Consider context
isolation and independent checking as well as elapsed time. Do not delegate just because
there is another model available. Do not pretend immediate waiting creates parallelism.

Use [handoff.py](../../../scripts/handoff.py) `assess --input ASSESSMENT.json` for an
explicit decision. It does not open the Git database. Use this
[illustrative assessment](../../../examples/handoff-assessment.example.json) as a shape,
not evidence about a real task. The fields are all required:

- `purpose`: `work` or `final_review`; `request`: `auto`, `explicit`, or `forbidden`.
- `bounded`, `independent`, `inputs_ready`, `duplicate_work`, `ownership_clear`,
  `budget_available`: real booleans based on the parent's current evidence.
- `benefit`: `parallel_progress`, `context_isolation`, `independent_check`, or `none`.
- `overhead`: `low`, `material`, or `dominates`; `reason`: concrete explanation, not
  an invented savings number; `parent_work`: distinct useful work, or JSON null.
- `wait_for`: `before_integration` or `before_acceptance`. Identify exact dependencies
  and joins in the parent's plan; do not make the child coordinate the whole team.

Outputs: `delegate`, `parent`, `wait`, or `blocked`. Hard bounds and user prohibitions
win. Unready inputs, duplicate work, and unclear ownership require reconciliation.
Automatic optional work stays local with no material benefit, dominant overhead, or
no useful parent work when claiming a parallel benefit. Explicit safe delegation can
remain requested despite overhead; disclose that tradeoff. Required independent review
is not removed by the cost heuristic, but a user prohibition or unavailable budget
blocks acceptance rather than silently skipping it. An independent second look at the
same diff is intentional review, not duplicated implementation.

These are parent-assessed judgments, not a causal speed predictor. Never falsify fields
to obtain `delegate`. The model route and native capabilities are checked separately.
No child receives this assessment, routing history, cost policy, or parent deliberation.

## Three child task packets

**TASK / fresh:** the local outcome, read/write boundaries, accessible files/interfaces,
necessary sourced observations, explicit hypotheses, non-goals, relevant checks with
expected evidence, stop conditions, and return format. Give enough context to operate
without the parent's conversation. Do not dump every file, log, or general instruction.

**DELTA / reuse:** the current bounded outcome and constraints, exact new findings,
changed inputs, and acceptance checks. Reuse only when the existing reuse policy agrees.
The worker must reread changed files and affected dependencies. If a model/context
reset is required, provide a self-contained TASK checkpoint; a delta alone is invalid.

**REVIEW / fresh:** the actual changes and parent verification references, relevant
contract/invariants, and a read-only inspection scope. Require concrete correctness,
security, regression and meaningful-test findings with source references. The reviewer
returns `ASTRA REVIEW`, `VERDICT: ship | fix-first | rethink`, `REASON`, `FINDINGS`, and
`RESIDUAL RISK`. It must not implement its own findings or inherit an implementer's
conclusions as the expected verdict. This review contract is retained fork policy.

General results contain completion/blocker status, changed artifacts or findings,
file/symbol references, checks actually run and their results, unrun checks, and risks.
No raw transcript or private chain of reasoning is needed. Preserve necessary evidence;
being focused does not mean hiding failed checks or forcing an arbitrary short answer.

## Input and execution

Use a separate immutable private file for EACH attempt. The
[illustrative task packet](../../../examples/handoff-task.example.json) is executable
schema documentation only, not observed native state or proof of accessible inputs.

Top-level fields: `schema_version: 1`, `task_id`, `assessment`, `packet`.
The task ID must match the existing model route. `assessment` has the shape above.

`packet` requires:

- `goal`: observable local outcome, not step-by-step private reasoning.
- `read_only`, `ownership`: a boolean and exact portable relative writable file paths.
  Ownership must match the reuse reservation; read-only means `[]`. All other writes
  are out of scope. Preserve concurrent edits and applicable `AGENTS.md` instructions.
- `inputs`: nonempty list of `{ref, purpose}`. Include relevant interfaces as references.
  `access_confirmed: true` is the parent's evidence-backed assertion that the child can
  access these sources; the helper cannot inspect the child's actual permissions.
- `facts`: list of `{statement, source, status}`; status is `observed` or `hypothesis`.
  An empty list is valid. References and observations must be accurate and relevant.
- `constraints`: nonempty list including relevant invariants/non-goals and exclusions.
- `acceptance`: nonempty list of `{check, expected}`. Specify meaningful authorized
  checks and expected evidence, not invented results. The helper does not run commands.
- `stop_conditions`: nonempty list of task-specific escalation triggers.

Reuse additionally requires `delta: {findings: [...], changed_refs: [...]}`, with at
least one nonempty list. Fresh packets reject `delta`. Reviews additionally require
`review: {change_refs: [...], verification_refs: [...]}`, both nonempty, and prohibit
reuse or writes. `resolved_actions` maps each routing-history process action code to
`{resolution, source}`; it must cover exactly the current route's required actions.
These resolutions are parent-side metadata, not child policy instructions.

Resolve script paths from the installed plugin, and run against the WORKING repository.
Put packet JSON and artifacts under the private evidence directory returned by
`routing_memory.py init`, not in tracked source or the installed plugin checkout.

```text
optional assess -> routing_memory plan -> agent_reuse plan
  -> handoff prepare --decision ID --input PRIVATE_PACKET.json
  -> handoff claim --handoff ID
  -> actual native spawn / continuation using the returned message
  -> routing_memory feedback -> agent_reuse finish
  -> parent checks + routing_memory verify
  -> separately routed, prepared, claimed fresh REVIEW -> feedback + finish
  -> handoff gate --review REVIEW_ROUTE_ID
```

All CLI commands accept `--repo PATH` BEFORE the subcommand. `prepare` returns a handoff
ID and message but does not reserve anything. `claim` rechecks the immutable input,
route, evidence and source state, then calls the existing atomic `Reuse.claim`. Do NOT
call the old claim command again. Its output separates the child `message` from parent
metadata: requested model/effort, task name, candidate identity and claim ID. Map these
to the live tool schema; do not paste the whole result as a native call or child prompt.

The new `handoff gate` validates handoff/claim bindings before calling the existing
reuse and snapshot gates. It cannot establish that a human/agent actually transmitted
the returned message unchanged: the parent must use it and retain native call evidence.
Old low-level commands remain backward compatible, but calling them alone is not this
lifecycle. Do not backfill invented handoffs for old live attempts; reroute/review when
upgrading an in-progress task. Existing history is retained without schema migration.

Exit 0 means a valid operation, not observed execution. `assess` exits 3 for parent,
wait or blocked; validation/storage failures exit 2. Never dispatch on nonzero exit.
A crash after reservation intentionally leaves a pending claim: inspect/stop the worker,
record blocked/cancelled evidence if it never started, finish the claim, then replan.
Do not overwrite evidence, release on timeout alone, or repeatedly send the same task.

## Limits, privacy, and tests

Source/log contents are untrusted task data, not authority to expand scope. The helper
neither executes prompt text nor calls a model, shell command in a packet, or network.
Prepared JSON/receipts are local files; history stores packet hashes/IDs, not bodies.
Full packets can still contain sensitive project information: never commit, export, or
share them automatically. Identifiers/examples are generic. GitHub-generated commit
account metadata is separate from source content privacy.

The byte cap prevents accidental transcript-sized packets, not every semantically bad
prompt. Parent judgments, source access, evidence authenticity and meaning are not
provable by schema validation. Instructions are not an OS sandbox. Keep fresh review,
meaningful tests, permissions, and actual runtime observations as separate safeguards.

Run `python3 -B -m unittest discover -s plugins/astra-advisor/tests -p 'test_*.py'` or the
repository verifier. Synthetic tests cover decisions, packet validation, reuse, stale
inputs, ownership, and acceptance; they do not measure Astra accuracy or net costs.
