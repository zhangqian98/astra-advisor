# Adaptive routing feedback extension

This repository includes an optional local feedback loop for Astra orchestration. It adapts routing policy from evidence-backed delegation outcomes; it does not train or modify model weights.

The implementation is deliberately conservative: model capability failures are separated from specification, context, ownership, verification, environment, and runtime-mismatch failures; one recent confirmed capability failure only creates temporary caution, while persistent escalation requires repeated distinct-task evidence with decay. Historical observations are repository- and runtime-scoped, append-only, and can be invalidated with evidence when attribution was wrong.

For substantial changes, parent verification is bound to the current working-tree snapshot, a fresh read-only reviewer is planned with a stronger reviewer floor, and acceptance fails closed if source, evidence, runtime observations, or implementation feedback changes after verification.

The local state is stored under the Git common directory and is not committed or uploaded automatically. The policy has synthetic invariant tests, not a live Astra routing benchmark; no measured quality or cost improvement is claimed.

See `plugins/astra-advisor/skills/orchestration/references/routing-memory.md` for the full protocol and `plugins/astra-advisor/scripts/routing_memory.py` for the implementation.
