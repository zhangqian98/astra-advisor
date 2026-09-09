# Token-efficient task profiles (handoff-v2)

This reference defines the compact child-message renderer used by
[`profile_handoff.py`](../../../scripts/profile_handoff.py). It replaces only prompt
rendering and policy labeling. The existing `handoff.py` assessment and packet schema,
routing-memory model floors, reuse reservations, evidence checks, and acceptance gates
remain authoritative.

## Official guidance used

Reviewed 2026-09-09. Public documentation and tool schemas can change.

| OpenAI source | Principle applied |
| --- | --- |
| [Codex Subagents](https://developers.openai.com/codex/subagents/) | Subagents add their own model/tool token use. Prefer independent parallel work, especially read-heavy exploration, tests, triage, and summarization. Be cautious with parallel writes. State division, join/wait behavior, and returned output. |
| [Codex best practices](https://developers.openai.com/codex/learn/best-practices/) | A useful prompt supplies Goal, Context, Constraints, and Done when. |
| [GPT-6 Astra model guidance](https://developers.openai.com/api/docs/guides/latest-model/) | Tell Astra when and how strongly to delegate; use collaboration only when it can improve time or quality. Calibrate verification to the change. |
| [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching/) | Keep reusable instructions and shared reference material stable and early; append changing content. Cache matching, eligibility, and savings must be measured rather than assumed. |

OpenAI also recommends narrow, opinionated custom agents with a clear job and tools
that match that job. This fork applies that behavior with micro-profiles rather than
installing persistent role TOMLs. The three profiles, modifiers, size guard, and exact
wording below are local policy choices, not OpenAI performance guarantees.

## Profiles

Each task gets exactly one base profile and at most one modifier. Profiles contain
behavior only. Paths, facts, interfaces, risks, and acceptance criteria belong in the
dynamic task contract.

| Task kind | Profile | Compact behavior |
| --- | --- | --- |
| `research` | `EXPLORE` | Read-only; trace real paths; cite files/symbols/artifacts; return distilled evidence. |
| `docs` | `EXPLORE+DOCS` | Add authoritative, version-specific reference checks; no code edits unless explicitly owned. |
| `implementation`, `refactor` | `WORK` | Make the smallest scoped change; preserve contracts; run targeted checks. |
| `debug` | `WORK+DEBUG` | Reproduce first; test competing hypotheses; avoid broad changes before evidence supports a root cause. |
| `test` | `WORK+TEST` | Verify observable behavior; report exact checks/results; change only owned files. |
| `review` | `REVIEW` | Fresh read-only context; findings first; inspect correctness, security, regressions, and meaningful test gaps. |

Do not create personality prose such as “you are an expert.” Do not stack unrelated
modifiers. Security, payments, data loss, public contracts, and other task-specific
risks belong in `KEEP`, `DONE`, and the routing-memory risk floor.

## Minimal contract

The stable prefix appears first:

```text
ASTRA SUBAGENT
<higher-priority instructions, prompt-injection boundary, scope and action limits>
PROFILE <base[+modifier]>: <short behavior rules>
```

Dynamic content follows:

- `TASK`: opaque task ID.
- `GOAL`: one local end state.
- `SCOPE`: read-only or exact owned write paths.
- `KEEP`: only invariants that constrain the selected task.
- `INPUT`: accessible canonical references for fresh workers and reviewers.
- `CONTEXT`: sourced observations (`[O]`) and hypotheses (`[H]`) for fresh workers.
- `DELTA`: findings and changed references for reused workers. Do not replay prior
  inputs, facts, or the parent transcript.
- `CHANGE` and `VERIFY`: actual diff/change and verification references for reviewers.
- `DONE`: checks paired with expected evidence.
- `STOP`: missing/contradictory input, ownership/permission conflicts, required scope
  growth, repeated failure without new evidence, and task-specific escalation rules.
- `RETURN`: status, exact references, actual checks/results, blockers, and residual risk.

The renderer collapses prose whitespace and omits optional empty sections. It keeps a
6,000-byte safety guard to force artifact references instead of embedding large logs or
diffs. This byte guard is not a model token limit. For routine tasks, keep the packet
well below the guard and retain only facts that change the worker's actions.

## Fresh, reuse, and review

A fresh worker must be self-contained because `fork_turns: none` may provide no parent
conversation. It receives accessible inputs and the smallest relevant set of facts.

A reused worker receives the bounded delta, current constraints, done criteria, and
stop/return contract. Conversation continuity may reduce repeated exploration, but it
can also grow context. The reuse policy decides whether continuation is still safe.

A final reviewer is always fresh and read-only. It receives the actual change and
verification artifacts, not the implementer's success narrative or prior reviewer
reasoning. Reviewer independence has priority over token minimization.

## Caching and measurement

The stable prefix comes before dynamic task content because OpenAI recommends stable
shared material first. The compact messages may be shorter than a model's minimum
cacheable visible prefix, and native Codex may manage context differently from direct
Responses API calls. Never claim a cache hit from ordering alone.

Use observed atomic usage when available. Compare fresh and reused attempts only as
descriptive history unless task matching and experimental controls justify a causal
claim. A smaller prompt does not by itself prove lower total task cost if it increases
errors, retries, or broad follow-up work.

## Activation and compatibility

Use:

```sh
python3 profile_handoff.py assess --input ASSESSMENT.json
python3 profile_handoff.py --repo WORKTREE prepare --decision DECISION_ID --input PACKET.json
python3 profile_handoff.py --repo WORKTREE claim --handoff HANDOFF_ID
python3 profile_handoff.py --repo WORKTREE gate --review REVIEW_ROUTE_ID
```

The wrapper lazily patches `handoff.POLICY` to `handoff-v2` and replaces
`handoff.render`, then delegates to the existing implementation. Existing handoff-v1
records cannot be claimed as v2; re-plan and prepare unfinished work. Calling legacy
`handoff.py` directly remains available for compatibility but does not establish the
v2 prompt contract.
