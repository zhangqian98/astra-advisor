# Evidence-backed routing memory (feedback-v1)

This fork adds local policy adaptation, not weight training. Use this reference in
addition to `operations.md`. Its stronger routing floors, evidence bindings, and
acceptance requirements take precedence over permissive model selection language.
It does not change the parent model/effort or authorize any new external actions.

## Activation and boundaries

Resolve [routing_memory.py](../../../scripts/routing_memory.py) relative to this
installed reference. Run it with Python 3.10+ and `--repo` pointing at the user's
working Git repository, NOT the installed plugin repository. A skill is not a
native-tool interceptor: these commands must actually be invoked by the parent on
every delegation lifecycle. Do not claim memory is active merely because this file
was loaded. No daemon, remote inference, credentials, API-key fallback, or native
hook is installed by this extension.

Run `init` first. It returns a private `state_dir` and `evidence_dir` beneath the
Git common directory. Git worktrees share this local history; different repositories
do not. Put task JSON, runtime observations, test receipts, and review evidence in
that private directory so they do not change the source-code snapshot. Do not store
secrets in labels; never commit/export this history automatically. The database
stores identifiers, typed metadata and file hashes, not prompts/code/log contents.
Only the parent records outcomes; workers may report evidence but must not grade
themselves into memory. This is a workflow rule, not a filesystem authorization
boundary against processes running as the same user.

If Python/Git/local storage is unavailable, report `feedback memory unavailable`
and retain conservative parent work. Do not claim persistence or silently pretend
feedback was recorded. A non-ready plan is not permission to spawn.

## Mandatory lifecycle

1. Inspect the real task, interfaces and current native tool schema. Write task and
   runtime JSON from observed evidence, not the bundled illustrative values. Each
   task needs explicit ownership, expected return, acceptance checks, excluded paths
   and integration boundaries in its handoff. One writable file has one concurrent
   owner. Do not delegate the same work twice or allow recursive delegation.
2. Run `plan --task TASK.json --runtime RUNTIME.json`. It writes an immutable route
   receipt. Publish its route ID, selected model/effort, risk, history event IDs,
   provisional/persistent caution, and required actions in `ASTRA ROUTE`. Resolve
   each process action before dispatch and state how it was satisfied. Parent work
   is appropriate when a task is unbounded/dependent or the specification is absent.
3. Dispatch through the actually exposed native interface with those exact controls.
   Never infer runtime identity from the submitted request. Save observable metadata
   and actual evidence. If realization is unknown, record null settings.
4. At every return, failure, cancellation or blocked dispatch, run `feedback --input
   OUTCOME.json` BEFORE the next model selection. Also record a new failure event
   against the original route when parent review or a later regression discovers a
   delegated mistake. Record successful attempts too; failures-only logging is biased.
5. Correct the specification, context, environment, ownership or verification gap as
   appropriate. For a real capability failure, explicitly exclude those other causes.
   Keep the same `task_id` across retries; new route IDs represent attempts, not new
   independent tasks. Three failed attempts in one task stop automatic retry and
   require parent replanning. Do not evade this by inventing a new task ID.
6. For substantial implementation, inspect the entire diff and rerun requested
   checks. Run `verify --routes ROUTE_ID ... --evidence CHECK_RECEIPT ...` on the
   current integrated working tree. This records hashes and binds the latest worker
   feedback. It does NOT execute checks for you.
7. Create a `kind: review` task referencing exactly those `review_of` route IDs and
   that `verification_id`; plan it separately. Its floor is one tier above the
   strongest target where possible (Sol uses a fresh Sol reviewer), never below the
   target's safety floor. Fresh context, an independent agent identity and read-only
   review are mandatory. Record `ship`, `fix-first` or `rethink` with evidence.
8. Run `gate --review REVIEW_ROUTE_ID`. Only successful exit with verdict `ship`
   permits substantial-work acceptance. Any source change, changed test receipt,
   revised worker feedback, missing runtime confirmation, or non-ship review requires
   new verification/review. The parent still makes the final decision. Keep the
   existing cost receipt and lifecycle reporting requirements.

For `fix-first`, repair/reverify/review afresh. A new pass may be recorded on the old
route after parent correction, while previous failed attempts remain learning data.
Reviewers never fix their own findings. `ship` is a necessary gate, not a mathematical
proof of correctness or authorization to merge/deploy/pay without the user's scope.

## Task JSON and rubric

Required fields: `task_id`, `kind`, `domain`, `risk`, `critical_flags`, `bounded`,
`independent`. Optional nonsecret opaque `pattern` and `scope` identify the technical
failure family and module boundary; use stable labels, not the complete task text.
Reviews additionally require `review_of` and `verification_id`.

`kind`: implementation, debug, refactor, research, test, review, docs.
`domain`: general, auth, payments, data, concurrency, api, ui, build, docs, tests.

Score each risk dimension 0..3 based on evidence, not lines of code:

| Dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| judgment | mechanical | local choices | multiple tradeoffs | novel/systemic reasoning |
| context | self-contained | nearby files | multiple modules | system-wide invariants |
| blast_radius | reversible local | module | several consumers | security/data/system boundary |
| spec_gap | exact checks | small omissions | important unknowns | no executable acceptance contract |
| uncertainty | known reproduction | limited unknowns | competing hypotheses | poorly understood failure |

Sum <=3 selects Luna/medium, 4..8 Terra/high, >=9 Sol/high. Any critical flag
(security, payments, data_loss, concurrency, public_contract) or blast_radius=3
sets a Sol floor. spec_gap=3, unbounded or dependent tasks stay with the parent
until clarified/decomposed. These are initial conservative heuristics, NOT measured
universal rankings. Risk assessment can still be wrong. Do not game the score to
obtain a cheaper lane. User-selected parent effort is unchanged.

## Runtime contract

Runtime JSON contains `epoch`, `models` (model -> exposed effort list), `controls`
and `evidence` (private filenames with the observed native schema/metadata).
Required controls are `model`, `reasoning_effort`, `fork_turns:none`. The supported
model vocabulary is inherited from upstream: gpt-5.6-luna, gpt-5.6-terra, gpt-5.6-sol.
The actual runtime must expose a selected model/effort. Missing availability blocks
the selected route; no silent substitution. Change the epoch when the model revision,
Codex runtime or meaningful capability contract changes. Evidence files establish
provenance but their authenticity cannot be established by this local script; the
parent must not fabricate them. Empty template catalogs deliberately fail validation.

## Outcome contract and learning

Each feedback input has a unique `event_id`, `route_id`, `agent_id`, `status`
(pass/fail/blocked/cancelled), `cause`, `attribution_confirmed`, observed_model,
observed_effort, runtime_evidence, and evidence. Unknown observed values are JSON
null, not the requested values. Runtime mismatch/unobservable settings are never
used to train the requested model's reliability. Optional metrics are observed
input_tokens, output_tokens, latency_ms; missing is null. Do not estimate these from
text length. Metrics are descriptive and are not summed into upstream cost receipts.

For capability attribution, diagnostics must explicitly confirm spec_reviewed,
context_sufficient and environment_healthy. This is a parent-reviewed judgment with
evidence, not an automatic causal oracle. Otherwise use the actual process cause
or unknown; an unconfirmed attribution does not generate a learned policy.

| Failure cause | Next matching task's required action |
|---|---|
| capability | reassess model/effort, potentially raise floor |
| spec_gap | rewrite acceptance criteria |
| context_gap | supply missing context |
| ownership_conflict | serialize overlapping writes |
| verification_gap | add regression check and independent review |
| environment | repair/reproduce environment, do not blame model |
| runtime_mismatch | repeat preflight |
| unknown | investigate root cause |

Learning is deliberately narrow: same repository, runtime epoch, policy version,
kind/domain/pattern/scope, risk vector and critical flags. This is an exact assessment
bucket, NOT semantic similarity search or proof that two tasks have equal difficulty.
One confirmed capability failure raises the matching lane one model tier for seven
days (Sol/high -> Sol/xhigh). Repeated evidence persists beyond that provisional
period when there are >=3 distinct failed tasks, decayed effective sample mass >=3,
and decayed failure fraction >=0.35. Evidence decays with a 30-day half-life and
expires at 90 days. If the newly selected lane has its own failure evidence, its
floor can be raised too. No data ever lowers the static safety floor. Sol/xhigh
failure requires parent rethink/reduced scope, not unbounded model or effort growth.

These thresholds are versioned implementation defaults, not benchmark-calibrated
probabilities. One task's repeated retries count once per model/effort; a later pass
does not erase the original failure. Evidence of bad routing is retained even after
parent fixes. Rich failure logs stay in private evidence, not executable instructions
in memory. The implementation uses fixed action codes; it does not execute text
from logs, mutate its own prompt/source, or upload lessons to any service.

## Audit, correction and privacy

`report` gives descriptive coverage/failure counts; `export` writes audit JSON to
stdout only when explicitly invoked. Export can disclose task labels/metadata;
review it before sharing. `void --event ID --reason misattribution --evidence FILE`
invalidates a bad observation without deleting the original. Other void reasons:
duplicate_task, bad_evidence, operator_correction. Only invalidate with new evidence,
not to improve an apparent pass rate. Restoring a voided event requires recording a
new reviewed event. Restarting/changing epoch isolates future learning without
rewriting history. To disable the extension, stop invoking it and disclose degraded
mode; do not delete the database to manufacture a clean success history.

SQLite transactions, uniqueness checks and append-only triggers guard accidental
loss/duplication across concurrent sessions. They are not a tamper-proof security
boundary against the same OS user. Back up via SQLite backup tooling, not by copying
a live database without its WAL. No automatic pruning or cross-project sharing is
performed. Local history, artifact hashes and snapshot receipts never reach GitHub
unless the user deliberately exports them.

Snapshotting covers HEAD and tracked/non-ignored untracked files, symlink targets
and executable bits. Ignored/generated files, external services, uninitialized repos,
submodules and huge artifacts are not silently claimed as verified. Submodules and
special files fail closed; limits are 50 MB per file / 500 MB total. Recompute parent
verification and review after any relevant change. The gate checks receipt consistency,
not whether a test command was truthful, complete or logically sufficient.

## CLI results

Exit 0: valid operation; inspect returned verdict/status. Exit 3: valid but blocked,
parent_only or rethink_parent plan, so do not dispatch. Exit 2: invalid/stale/missing
evidence or a storage failure. Stop affected delegation on either nonzero code.
The policy has synthetic invariant tests, not a live Astra routing benchmark; do not
claim a measured improvement until real task outcomes support that claim.
