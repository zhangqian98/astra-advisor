#!/usr/bin/env python3
"""Evidence-backed worker continuation. No native calls, credentials or network access.

Use after routing_memory.plan; model/risk floors and fresh review always win.
Local receipts do not prove runtime behavior, cache hits or monetary savings.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import sqlite3
import sys
import uuid
from typing import Any

from routing_memory import Advisor, Invalid, canonical, digest, fields, identifier, boolean, read_json
from routing_memory import DAY, HALF_LIFE, WINDOW

POLICY = "reuse-v1"
DECISION_TTL = 300
IDLE_TTL = 6 * 3600
MAX_CONTINUATIONS = 4
CONTEXT_FAILURES = {"stale_context", "anchoring", "context_overflow"}
CONTEXT_STATES = {"usable", "unknown", "stale", "suspect", "near_limit"}
LIMITS = "Selected-history observations, not matched experiments or guaranteed cache/cost savings."


def nonnegative(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise Invalid("usage must be observed nonnegative integers or null")
    return value


def ownership(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > 256:
        raise Invalid("ownership must list at most 256 exact relative file paths")
    result = []
    for item in value:
        if (not isinstance(item, str) or not item or len(item) > 512 or "\\" in item
                or any(c in item for c in "*?[]:\n\r\0") or item.startswith("/")):
            raise Invalid("ownership must use exact portable relative file paths, no globs")
        path = PurePosixPath(item)
        if not path.parts or any(p.casefold() in {"..", ".git"} for p in path.parts) or str(path) != item:
            raise Invalid("invalid ownership path")
        result.append(item)
    if len(result) != len(set(result)):
        raise Invalid("duplicate owned file")
    return sorted(result)


class Reuse:
    def __init__(self, advisor: Advisor):
        self.a = advisor
        # Store a hash, not an absolute local path. Worktrees share history, not live workers.
        self.worktree = digest(str(advisor.root))

    def context(self, value: Any) -> dict:
        fields(value, {"session_id", "ownership", "continuation", "candidate_agent_id",
                       "agent_state", "context_state", "delta_ready", "observed_model",
                       "observed_effort", "continuation_tool", "evidence"},
               {"context_tokens", "context_limit"})
        c = json.loads(canonical(value))
        identifier(c["session_id"])
        c["ownership"] = ownership(c["ownership"])
        for name in c["ownership"]:
            path = self.a.root / name
            if not path.resolve().is_relative_to(self.a.root) or path.is_dir():
                raise Invalid("ownership must name files within this working repository")
        boolean(c["delta_ready"])
        if c["continuation"] not in {"same_task", "related_task", "fresh"}:
            raise Invalid("invalid continuation intent")
        if c["agent_state"] not in {"idle", "closed", "running", "unobservable"}:
            raise Invalid("invalid agent state")
        if c["context_state"] not in CONTEXT_STATES:
            raise Invalid("invalid context state")
        for key in ("candidate_agent_id", "observed_model", "observed_effort", "continuation_tool"):
            if c[key] is not None:
                identifier(c[key])
        c["evidence"] = self.a.capture(c["evidence"])
        for key in ("context_tokens", "context_limit"):
            if c.get(key) is not None:
                nonnegative(c[key])
        if c.get("context_limit") == 0:
            raise Invalid("context limit must be positive or null")
        return c

    def pending(self) -> list[dict]:
        done = {r["claim_id"] for r in self.a.records("reuse_result")}
        return [r for r in self.a.records("reuse_claim") if r["id"] not in done]

    def outcomes(self) -> list[dict]:
        """Re-read live feedback, including later failures and voided attributions."""
        active = {e["id"]: e for e in self.a.active_events()}
        lessons = self.a.records("reuse_lesson")
        rows = []
        for result in self.a.records("reuse_result"):
            decision = self.a.get(result["decision_id"], "reuse_decision")
            route = self.a.get(decision["route_id"], "plan")
            events = [e for e in active.values() if e["route_id"] == route["id"]
                      and e["agent_id"] == result["agent_id"]]
            bad = [l for l in lessons if l["feedback_id"] in active
                   and active[l["feedback_id"]]["route_id"] == route["id"]]
            # A pass never erases a later-discovered context failure.
            rows.append({"result": result, "decision": decision, "route": route,
                         "events": events, "lessons": bad})
        return rows

    def caution(self, route: dict) -> list[str]:
        samples: dict[str, dict] = {}
        now = self.a.clock()
        for row in self.outcomes():
            old, d, r = row["route"], row["decision"], row["result"]
            if (d["policy"] != POLICY or r["actual_mode"] != "reuse" or old["family"] != route["family"]
                    or old["epoch"] != route["epoch"] or old["model"] != route["model"]
                    or old["effort"] != route["effort"]):
                continue
            bad = []
            for lesson in row["lessons"]:
                e = self.a.get(lesson["feedback_id"], "feedback")
                if (e["runtime_match"] and e["attribution_confirmed"] and e["status"] == "fail"
                        and 0 <= now - lesson["created"] <= WINDOW):
                    try:
                        self.a.recheck(lesson["evidence"])
                        self.a.recheck(e["evidence"])
                        self.a.recheck(e["runtime_evidence"])
                    except (Invalid, OSError):
                        continue  # stale evidence cannot teach a rule
                    bad.append(lesson)
            good = [e for e in row["events"] if e["status"] == "pass" and e["runtime_match"]
                    and e["attribution_confirmed"] and 0 <= now - e["created"] <= WINDOW]
            if not bad and not good:
                continue
            event = bad[-1] if bad else good[-1]
            sample = {"failed": bool(bad), "created": event["created"], "id": event["id"]}
            key = old["task"]["task_id"]
            prev = samples.get(key)
            if prev is None or (sample["failed"] and not prev["failed"]):
                samples[key] = sample
        failed = [s for s in samples.values() if s["failed"]]
        mass = sum(2 ** (-(now - s["created"]) / HALF_LIFE) for s in samples.values())
        bad_mass = sum(2 ** (-(now - s["created"]) / HALF_LIFE) for s in failed)
        provisional = any(now - s["created"] <= 7 * DAY for s in failed)
        persistent = len(failed) >= 3 and mass >= 2 and bad_mass / mass >= 0.35
        return sorted(s["id"] for s in failed) if provisional or persistent else []

    def choose(self, route: dict, c: dict) -> tuple[str, str]:
        if route["status"] != "ready":
            return "blocked", "model_route_not_ready"
        if route["task"]["kind"] == "review":
            return "fresh", "independent_review_requires_new_context"
        if c["continuation"] == "fresh" or c["candidate_agent_id"] is None:
            return "fresh", "no_eligible_worker_requested"
        if self.caution(route):
            return "fresh", "history_context_failure_caution"
        matches = [row for row in self.outcomes() if row["result"]["agent_id"] == c["candidate_agent_id"]
                   and row["decision"]["worktree"] == self.worktree
                   and row["decision"]["context"]["session_id"] == c["session_id"]]
        if not matches:
            return "fresh", "worker_not_registered_in_this_session_and_worktree"
        row = matches[-1]
        previous, old, result = row["decision"], row["route"], row["result"]
        if old["task"]["kind"] == "review":
            return "fresh", "never_repurpose_a_reviewer"
        if old["epoch"] != route["epoch"]:
            return "fresh", "runtime_epoch_changed"
        if (old["model"] != route["model"] or old["effort"] != route["effort"]
                or c["observed_model"] != route["model"] or c["observed_effort"] != route["effort"]):
            return "fresh", "model_or_effort_changed_or_unconfirmed"
        same = old["task"]["task_id"] == route["task"]["task_id"]
        if not same and c["continuation"] != "related_task":
            return "fresh", "different_task_not_explicitly_approved"
        if any(old["task"][k] != route["task"][k] for k in ("kind", "domain", "pattern", "scope")):
            return "fresh", "task_boundary_drift"
        if c["ownership"] != previous["context"]["ownership"]:
            return "fresh", "ownership_changed"
        if c["agent_state"] == "running":
            return "wait", "worker_is_busy_do_not_duplicate_or_interrupt"
        if c["agent_state"] not in {"idle", "closed"} or c["continuation_tool"] is None:
            return "fresh", "native_continuation_unavailable_or_unobservable"
        if c["context_state"] != "usable" or not c["delta_ready"]:
            return "fresh", "context_not_trusted_or_delta_not_prepared"
        if (c.get("context_tokens") is not None and c.get("context_limit") is not None
                and c["context_tokens"] >= 0.75 * c["context_limit"]):
            return "fresh", "context_pressure"
        if not 0 <= self.a.clock() - result["created"] <= IDLE_TTL:
            return "fresh", "worker_context_too_old"
        if result["actual_mode"] == "unobservable" or not row["events"]:
            return "fresh", "previous_continuation_unconfirmed"
        last = row["events"][-1]
        if not last["runtime_match"] or last["status"] not in {"pass", "fail"}:
            return "fresh", "previous_runtime_or_execution_unconfirmed"
        try:
            self.a.recheck(last["runtime_evidence"])
            self.a.recheck(last["evidence"])
            self.a.recheck(result["evidence"])
        except (Invalid, OSError):
            return "fresh", "previous_evidence_stale"
        recent = []
        for item in reversed(matches):
            if item["route"]["epoch"] != route["epoch"]:
                break
            recent.append(item)
            if item["result"]["actual_mode"] == "fresh":
                break
        if sum(item["result"]["actual_mode"] == "reuse" for item in recent) >= MAX_CONTINUATIONS:
            return "fresh", "continuation_budget_exhausted"
        if sum(any(e["status"] == "fail" for e in item["events"]) for item in recent) >= 2:
            return "fresh", "repeated_worker_failures"
        return "reuse", "trusted_context_and_bounded_delta"

    def current_route(self, route_id: str) -> None:
        row = self.a.db.execute("SELECT seq FROM records WHERE id=? AND kind='plan'", (route_id,)).fetchone()
        if row is None or self.a.db.execute(
                "SELECT 1 FROM records WHERE kind IN ('feedback','void') AND seq>? LIMIT 1", (row[0],)).fetchone():
            raise Invalid("feedback changed since model selection; run routing_memory plan again")

    def plan(self, route_id: str, context: dict) -> dict:
        route = self.a.get(route_id, "plan")
        self.current_route(route_id)
        self.a.recheck(route["runtime_evidence"])
        c = self.context(context)
        mode, reason = self.choose(route, c)
        return self.a.put("reuse_decision", {
            "policy": POLICY, "route_id": route_id, "worktree": self.worktree,
            "context": c, "mode": mode, "reason": reason,
            "source_lesson_ids": self.caution(route), "snapshot": self.a.snapshot(),
            "handoff": "bounded_delta_only" if mode == "reuse" else "bounded_fresh_packet",
            "limits": LIMITS})

    def _insert(self, kind: str, payload: dict) -> dict:
        rid = uuid.uuid4().hex
        self.a.db.execute("INSERT INTO records(id,kind,created,data) VALUES(?,?,?,?)",
                          (rid, kind, self.a.clock(), canonical(payload)))
        return {"id": rid, **payload}

    def claim(self, decision_id: str) -> dict:
        # No timeout releases a live worker. A parent must reconcile every interrupted claim.
        self.a.db.execute("BEGIN IMMEDIATE")
        try:
            d = self.a.get(decision_id, "reuse_decision")
            route = self.a.get(d["route_id"], "plan")
            self.current_route(route["id"])
            if d["worktree"] != self.worktree or not 0 <= self.a.clock() - d["created"] <= DECISION_TTL:
                raise Invalid("decision expired or belongs to a different worktree; replan")
            for evidence in (d["context"]["evidence"], route["runtime_evidence"]):
                self.a.recheck(evidence)
            if d["snapshot"] != self.a.snapshot():
                raise Invalid("working tree changed; refresh the handoff and replan")
            mode, reason = self.choose(route, d["context"])
            if mode not in {"reuse", "fresh"} or (mode, reason) != (d["mode"], d["reason"]):
                raise Invalid("decision blocked or changed; replan before native dispatch")
            if (any(r["route_id"] == route["id"] for r in self.a.records("reuse_claim"))
                    or any(e["route_id"] == route["id"] for e in self.a.records("feedback"))):
                raise Invalid("route was already dispatched; every attempt needs a new route")
            for pending in self.pending():
                other = self.a.get(pending["decision_id"], "reuse_decision")
                same_agent = (mode == "reuse" and other["mode"] == "reuse"
                              and other["context"]["candidate_agent_id"] == d["context"]["candidate_agent_id"])
                # Windows paths are case-insensitive; conservative case-folding is safe elsewhere.
                conflict = other["worktree"] == self.worktree and bool(
                    {p.casefold() for p in other["context"]["ownership"]}
                    & {p.casefold() for p in d["context"]["ownership"]})
                if same_agent or conflict:
                    raise Invalid("worker or owned files already reserved; wait, do not spawn a duplicate")
            result = self._insert("reuse_claim", {"decision_id": decision_id, "route_id": route["id"]})
            self.a.db.commit()
            return result
        except Exception:
            self.a.db.rollback()
            raise

    def finish(self, value: dict) -> dict:
        fields(value, {"claim_id", "feedback_id", "actual_mode", "agent_state", "evidence"}, {"usage"})
        self.a.db.execute("BEGIN IMMEDIATE")
        try:
            claim = self.a.get(value["claim_id"], "reuse_claim")
            d = self.a.get(claim["decision_id"], "reuse_decision")
            e = self.a.get(value["feedback_id"], "feedback")
            if (d["worktree"] != self.worktree or e["route_id"] != claim["route_id"]
                    or e["id"] not in {x["id"] for x in self.a.active_events()}
                    or e["created"] < claim["created"]):
                raise Invalid("feedback must be active, post-dispatch and from this claim/worktree")
            if any(r["claim_id"] == claim["id"] for r in self.a.records("reuse_result")):
                raise Invalid("claim already completed; use lesson for later-discovered mistakes")
            if value["agent_state"] not in {"idle", "closed", "not_started"}:
                raise Invalid("confirm worker stopped before releasing ownership")
            if value["agent_state"] == "not_started" and e["status"] not in {"blocked", "cancelled"}:
                raise Invalid("not-started dispatch cannot have executed feedback")
            mode = value["actual_mode"]
            if mode not in {"fresh", "reuse", "unobservable"}:
                raise Invalid("invalid actual mode")
            if mode != "unobservable" and mode != d["mode"]:
                raise Invalid("actual mode contradicts decision; disclose as unobservable, then replan")
            if mode == "reuse" and e["agent_id"] != d["context"]["candidate_agent_id"]:
                raise Invalid("reuse requires the same runtime-confirmed native agent ID")
            if mode == "fresh" and any(x["agent_id"] == e["agent_id"] and x["route_id"] != e["route_id"]
                                       for x in self.a.records("feedback")):
                raise Invalid("fresh dispatch must use a new independent agent identity")
            self.a.recheck(e["evidence"])
            self.a.recheck(e["runtime_evidence"]) if e["runtime_evidence"] else None
            if mode != "unobservable" and not e["runtime_match"]:
                raise Invalid("confirmed dispatch mode requires observed matching model and effort")
            usage = value.get("usage")
            if usage is not None:
                fields(usage, {"call_id", "input_tokens", "cached_input_tokens", "output_tokens", "latency_ms"})
                identifier(usage["call_id"])
                for k, v in usage.items():
                    if k != "call_id" and v is not None:
                        nonnegative(v)
                if usage["cached_input_tokens"] is not None and (usage["input_tokens"] is None
                        or usage["cached_input_tokens"] > usage["input_tokens"]):
                    raise Invalid("cached input is a known subset of input, not additional tokens")
                if any(r.get("usage") and r["usage"]["call_id"] == usage["call_id"]
                       for r in self.a.records("reuse_result")):
                    raise Invalid("usage call ID already recorded; cumulative totals are not atomic calls")
            result = self._insert("reuse_result", {
                "claim_id": claim["id"], "decision_id": d["id"], "feedback_id": e["id"],
                "agent_id": e["agent_id"], "actual_mode": mode, "agent_state": value["agent_state"],
                "usage": usage, "evidence": self.a.capture(value["evidence"])})
            self.a.db.commit()
            return result
        except Exception:
            self.a.db.rollback()
            raise

    def lesson(self, feedback_id: str, cause: str, evidence: list[str]) -> dict:
        e = self.a.get(feedback_id, "feedback")
        if (cause not in CONTEXT_FAILURES or e["status"] != "fail" or not e["attribution_confirmed"]
                or not e["runtime_match"] or e["id"] not in {x["id"] for x in self.a.active_events()}):
            raise Invalid("context lessons require an active confirmed failure with observed runtime")
        if not any(row["route"]["id"] == e["route_id"] and row["result"]["actual_mode"] == "reuse"
                   and row["result"]["agent_id"] == e["agent_id"] for row in self.outcomes()):
            raise Invalid("lesson must refer to an actually reused worker")
        if e["cause"] not in {"context_gap", "verification_gap", "unknown"}:
            raise Invalid("do not relabel a capability/environment/spec failure as a context failure")
        self.a.recheck(e["evidence"])
        return self.a.put("reuse_lesson", {"feedback_id": feedback_id, "cause": cause,
                                          "evidence": self.a.capture(evidence)},
                          "lesson-" + digest([feedback_id, cause]))

    def gate(self, review_id: str) -> dict:
        """Add actual dispatch/continuation checks to the existing snapshot-bound gate."""
        review = self.a.get(review_id, "plan")
        if review["task"]["kind"] != "review":
            raise Invalid("acceptance requires a review route")
        required = set(review["task"]["review_of"]) | {review_id}
        rows = self.outcomes()
        for rid in required:
            matches = [r for r in rows if r["route"]["id"] == rid]
            if len(matches) != 1:
                raise Invalid("each accepted route needs exactly one completed dispatch receipt")
            row = matches[0]
            result, decision = row["result"], row["decision"]
            if decision["worktree"] != self.worktree or result["actual_mode"] == "unobservable":
                raise Invalid("dispatch mode/worktree is unconfirmed")
            if rid == review_id and result["actual_mode"] != "fresh":
                raise Invalid("final reviewer must be a freshly spawned independent agent")
            self.a.recheck(result["evidence"])
            latest = self.a.latest(rid)
            if latest["agent_id"] != result["agent_id"]:
                raise Invalid("feedback identity changed since the dispatch receipt")
        if any(c["route_id"] in required for c in self.pending()):
            raise Invalid("accepted routes still have unresolved native dispatches")
        return self.a.gate(review_id)

    def report(self) -> dict:
        rows = self.outcomes()
        groups = {}
        for mode in ("fresh", "reuse", "unobservable"):
            selected = [r for r in rows if r["result"]["actual_mode"] == mode]
            usages = [r["result"]["usage"] for r in selected if r["result"].get("usage")]
            groups[mode] = {"attempts": len(selected), "usage_calls": len(usages),
                            "failed_attempts": sum(any(e["status"] == "fail" for e in r["events"]) for r in selected),
                            "metrics": {k: {"observed_calls": sum(u[k] is not None for u in usages),
                                             "observed_sum": sum(u[k] for u in usages if u[k] is not None)
                                             if any(u[k] is not None for u in usages) else None}
                                        for k in ("input_tokens", "cached_input_tokens", "output_tokens", "latency_ms")}}
        return {"policy": POLICY, "pending_claims": len(self.pending()), "by_mode": groups, "limits": LIMITS}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path.cwd())
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("plan")
    s.add_argument("--route", required=True)
    s.add_argument("--context", type=Path, required=True)
    s = sub.add_parser("claim")
    s.add_argument("--decision", required=True)
    s = sub.add_parser("finish")
    s.add_argument("--input", type=Path, required=True)
    s = sub.add_parser("lesson")
    s.add_argument("--feedback", required=True)
    s.add_argument("--cause", choices=sorted(CONTEXT_FAILURES), required=True)
    s.add_argument("--evidence", nargs="+", required=True)
    s = sub.add_parser("gate")
    s.add_argument("--review", required=True)
    sub.add_parser("report")
    args = p.parse_args(argv)
    try:
        with Advisor(args.repo) as a:
            reuse = Reuse(a)
            if args.command == "plan":
                output = reuse.plan(args.route, read_json(args.context))
            elif args.command == "claim":
                output = reuse.claim(args.decision)
            elif args.command == "finish":
                output = reuse.finish(read_json(args.input))
            elif args.command == "lesson":
                output = reuse.lesson(args.feedback, args.cause, args.evidence)
            elif args.command == "gate":
                output = reuse.gate(args.review)
            else:
                output = reuse.report()
        print(json.dumps(output, indent=2, allow_nan=False))
        return 3 if output.get("mode") in {"blocked", "wait"} else 0
    except (Invalid, OSError, sqlite3.Error, json.JSONDecodeError, TypeError, KeyError) as exc:
        print(json.dumps({"error": str(exc), "action": "stop_affected_dispatch"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
