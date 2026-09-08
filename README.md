# Astra Advisor

**GPT-6 Astra plans the work, chooses useful bounded delegation dynamically, and
owns verification and acceptance.**

Astra Advisor is a Codex plugin for capability-routed software delivery. Give Astra
the goal, constraints, and repository context; it decides whether independent work
should run alongside the parent session and chooses a supported native subagent
model and effort for each bounded deliverable.

## Adaptive routing and safe worker reuse (this fork)

This checkout adds local evidence-backed model routing and **reuse-first worker
continuation** for same-task fixes and compatible bounded follow-ups. A suitable
worker keeps its task context and receives a small delta rather than rereading the
whole project. Model upgrades, stale/suspect context, repeated failure and ownership
conflicts take precedence. Final reviewers always get a new independent context.

The [reuse protocol](plugins/astra-advisor/skills/orchestration/references/agent-reuse.md)
and [Chinese guide](docs/AGENT_REUSE.zh-CN.md) explain activation, native-tool
preflight, reservations, late-failure feedback, audit and usage accounting. These
are local policy tools called by the skill, not an automatic native-tool hook.
They preserve the [routing-memory constraints](plugins/astra-advisor/skills/orchestration/references/routing-memory.md).
Observed reuse does not guarantee cache hits or net savings; there is no live
quality/cost benchmark. Learning changes routing/context policy, not model weights.

## Cloud limitation

ChatGPT Work cloud `create_thread` must omit `model` and
`thinking`, so it cannot currently promise arbitrary model or effort control. Astra
does not dispatch a model-pinned request there by default. Native Codex subagents are usable
where the current tool schema exposes the needed controls.

## Go deeper

I write [Attention Heads](https://attentionheads.substack.com/) — deep,
evidence-backed writing on AI, cognition, and agentic engineering. The **Agentic
Engineering Field Notes** series covers the craft of using AI. [Subscribe](https://attentionheads.substack.com/subscribe?utm_source=github&utm_medium=readme&utm_campaign=astra-advisor)
to get new posts in your inbox.

## Quick start

Install the plugin in a current Codex CLI or ChatGPT desktop app with plugins
enabled. Start a fresh task after installation and select GPT-6 Astra at any effort
supported by the current Codex host. To use this enhanced fork, install the local
checkout (replace the placeholder path), not the upstream marketplace:

~~~sh
codex plugin marketplace add /absolute/path/to/astra-advisor
codex plugin add astra-advisor@astra-advisor
~~~

Start a task with:

~~~text
Use $astra-advisor:orchestration to plan, build, verify, and review this work.
~~~

## How routing works

Astra remains the architect and acceptance owner in the primary GPT-6 Astra session
at the effort selected by the user. After capability preflight, Astra records the
parent model and effort as observed or unobservable before implementation or
delegation begins. The skill never changes the parent session.

When a fresh worker is needed, Astra uses the exposed native spawn tool with an
explicit `model`, `reasoning_effort`, and `fork_turns: none`. Eligible follow-ups use
the existing worker through the actual native continuation interface. It chooses
among `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` from the task's risk,
context, and independent work. There are no predefined role TOMLs, companion
installer, role-to-model mapping, or fixed subagent count cap. Astra gives each
subagent a concrete bounded deliverable and continues useful parent work while it
runs.

Live tool metadata is authoritative. The current documented effort snapshot is:

| Model | Known efforts |
| --- | --- |
| `gpt-5.6-sol` | `low`, `medium`, `high`, `xhigh`, `max`, `ultra` |
| `gpt-5.6-terra` | `low`, `medium`, `high`, `xhigh`, `max`, `ultra` |
| `gpt-5.6-luna` | `low`, `medium`, `high`, `xhigh`, `max` |

If a selected model, effort, control, or tool is unavailable, conflicting, or
unobservable, Astra fails that delegation closed and reports the limitation. It does
not silently substitute a model, effort, role, or fabricated tool. Chosen values and
runtime-confirmed values are reported separately.

For substantial implementation, Astra inspects the complete diff and reruns the
requested checks, then sends the accumulated change set to a fresh read-only
reviewer. This fork derives a stronger reviewer floor from the implementation route
and records a fresh dispatch receipt. Astra accepts work only after `ship` and the
reuse-aware snapshot gate succeed; `fix-first`
requires a new parent verification and fresh review, while `rethink` requires a
revised plan.

## Live visibility and cost receipts (0.2.0)

Every delegation announces its name, bounded task, selected model and reasoning
effort, and selection reason. Its result reports actual status and runtime-observed
settings, or explicitly says those settings are unobservable. These updates also
cover fresh reviewers. A requested setting is not proof of the realized setting.

Every task ends with an API-equivalent cost receipt. When native tools expose token
usage, the receipt estimates its USD price using the versioned snapshot and compares
that same token workload repriced entirely at Astra. It separates whole-task,
delegated-only, and partial coverage. Missing parent or reviewer usage prevents a
whole-task claim. Without observed usage, the receipt says why it is unavailable.

The difference is a **same-token API price comparison**. It does not measure what an
all-Astra run would actually consume, actual net task savings, quality, speed, or a
change to ChatGPT subscription charges or usage credits. No subagents means no
delegation savings. Reasoning effort does not multiply the token price.

The [pricing snapshot](plugins/astra-advisor/pricing/2026-09-04.json) records official
source URLs and standard short-context USD rates per million tokens, verified by
the recording coordinator on September 4, 2026. These are historical estimates;
Sol pricing is promotional and may change. The calculator rejects unsupported
long-context, service-tier, and cache-write cases instead of assuming standard rates.
It conservatively supports at most 128,000 input tokens per call; this is an
implementation support boundary, not a claimed official pricing threshold.

Try the clearly labeled illustrative workload (not a receipt for your task):

~~~sh
python3 plugins/astra-advisor/scripts/cost_receipt.py plugins/astra-advisor/examples/illustrative-usage.json
sh plugins/astra-advisor/scripts/verify.sh
~~~

The calculator emits JSON and accepts `--pricing PATH` for another verified snapshot.
Its input lists agents and unique atomic calls, usage provenance, coverage assertions,
and explicit pricing eligibility. It validates cached-input and reasoning-output
subsets, refuses overlapping aggregates, and keeps unknown usage separate from zero.
See the [operations reference](plugins/astra-advisor/skills/orchestration/references/operations.md)
for the input contract and receipt policy.

## ChatGPT app tasks

Separate app tasks require an explicit user request. For an explicit Codex app task,
`mcp__codex_app__create_thread` supports `model` and `thinking`; call
`mcp__codex_app__list_projects` first for project targets, use a worktree by default
for Git projects, and use local otherwise. Cloud `create_thread` omits both controls,
so the bounded limitation above applies. Do not use an API key, nested CLI, or
invented tool as a workaround.

## Updating

~~~sh
codex plugin marketplace upgrade astra-advisor
codex plugin add astra-advisor@astra-advisor
~~~

For local development, install this checkout as a marketplace:

~~~sh
cd /absolute/path/to/astra-advisor
codex plugin marketplace add /absolute/path/to/astra-advisor
codex plugin add astra-advisor@astra-advisor
~~~

For operational details, read
[the orchestration operations reference](plugins/astra-advisor/skills/orchestration/references/operations.md).
