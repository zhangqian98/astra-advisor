#!/usr/bin/env python3
"""Local, evidence-backed routing memory. Python 3.10+, standard library only.

This is policy adaptation, NOT weight training or an autonomous native-tool hook.
The parent must execute the documented lifecycle. No network calls are made.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
import time
from typing import Any
import uuid

POLICY = "feedback-v1"
MODELS = ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")
DIMENSIONS = ("judgment", "context", "blast_radius", "spec_gap", "uncertainty")
KINDS = {"implementation", "debug", "refactor", "research", "test", "review", "docs"}
DOMAINS = {"general", "auth", "payments", "data", "concurrency", "api", "ui", "build", "docs", "tests"}
CRITICAL = {"security", "payments", "data_loss", "concurrency", "public_contract"}
CAUSES = {"none", "capability", "spec_gap", "context_gap", "ownership_conflict",
          "verification_gap", "environment", "runtime_mismatch", "unknown"}
ACTIONS = {
    "capability": "reassess_model_and_effort",
    "spec_gap": "rewrite_acceptance_criteria_before_dispatch",
    "context_gap": "supply_missing_context_before_dispatch",
    "ownership_conflict": "serialize_overlapping_writes",
    "verification_gap": "add_regression_check_and_independent_review",
    "environment": "repair_or_reproduce_environment_before_retry",
    "runtime_mismatch": "repeat_runtime_preflight",
    "unknown": "investigate_root_cause_before_retry",
}
DAY = 86400
WINDOW = 90 * DAY
HALF_LIFE = 30 * DAY
PROVISIONAL = 7 * DAY


class Invalid(ValueError):
    """Invalid input, stale evidence, or an unsupported operation."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fields(obj: Any, required: set[str], optional: set[str] | None = None) -> None:
    if not isinstance(obj, dict):
        raise Invalid("expected a JSON object")
    if required - obj.keys() or obj.keys() - required - (optional or set()):
        raise Invalid(f"missing/unknown fields; expected {sorted(required)}, optional {sorted(optional or set())}")


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
        raise Invalid("IDs must be opaque 1-128 character identifiers, not prompts or paths")
    return value


def boolean(value: Any) -> bool:
    if type(value) is not bool:
        raise Invalid("expected a boolean")
    return value


def git(root: Path, *args: str) -> bytes:
    try:
        p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True, timeout=30)
        return p.stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise Invalid("Git operation failed; use a readable, initialized working repository") from exc


def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Invalid("duplicate JSON key")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    if path.stat().st_size > 2_000_000:
        raise Invalid("JSON input exceeds 2 MB")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_keys,
                      parse_constant=lambda _: (_ for _ in ()).throw(Invalid("non-finite JSON number")))


class Advisor:
    def __init__(self, root: Path, *, clock=time.time):
        self.root = Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
        common = Path(os.fsdecode(git(self.root, "rev-parse", "--git-common-dir")).strip())
        self.common = (common if common.is_absolute() else self.root / common).resolve()
        # Git worktrees share memory, but runtime epoch + exact task signature scope its use.
        self.state = self.common / "astra-advisor"
        if self.state.is_symlink():
            raise Invalid("state directory must not be a symlink")
        self.state.mkdir(mode=0o700, exist_ok=True)
        os.chmod(self.state, 0o700)
        self.evidence_dir = self.state / "evidence"
        if self.evidence_dir.is_symlink():
            raise Invalid("evidence directory must not be a symlink")
        self.evidence_dir.mkdir(mode=0o700, exist_ok=True)
        dbfile = self.state / "history.sqlite3"
        if dbfile.is_symlink():
            raise Invalid("database must not be a symlink")
        self.db = sqlite3.connect(dbfile, timeout=15)
        os.chmod(dbfile, 0o600)
        self.db.row_factory = sqlite3.Row
        self.clock = clock
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=15000")
        self.db.execute("PRAGMA journal_mode=WAL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.db.close()
            raise Invalid("unsupported history schema; do not overwrite it")
        with self.db:
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS records (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    created REAL NOT NULL,
                    data TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS records_kind ON records(kind);
                CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON records
                    BEGIN SELECT RAISE(ABORT, 'append-only history'); END;
                CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON records
                    BEGIN SELECT RAISE(ABORT, 'append-only history'); END;
                PRAGMA user_version=1;
            """)

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def put(self, kind: str, data: dict[str, Any], record_id: str | None = None) -> dict[str, Any]:
        record_id = identifier(record_id or uuid.uuid4().hex)
        raw = canonical(data)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO records(id,kind,created,data) VALUES(?,?,?,?)",
                            (record_id, kind, self.clock(), raw))
            row = self.db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
            if row["kind"] != kind or row["data"] != raw:
                raise Invalid("record ID already exists with a different payload")
        return {"id": record_id, **data}

    def get(self, record_id: str, kind: str | None = None) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM records WHERE id=?", (identifier(record_id),)).fetchone()
        if row is None or (kind is not None and row["kind"] != kind):
            raise Invalid("record does not exist or has the wrong kind")
        return {"id": row["id"], "created": row["created"], **json.loads(row["data"])}

    def records(self, kind: str) -> list[dict[str, Any]]:
        return [{"id": row["id"], "created": row["created"], **json.loads(row["data"])}
                for row in self.db.execute("SELECT * FROM records WHERE kind=? ORDER BY seq", (kind,))]

    def capture(self, paths: Any) -> list[dict[str, Any]]:
        if not isinstance(paths, list) or not paths or len(paths) > 16:
            raise Invalid("supply 1-16 evidence files under the private evidence directory")
        result = []
        seen = set()
        for value in paths:
            if not isinstance(value, str):
                raise Invalid("evidence path must be a string")
            path = Path(value)
            path = path if path.is_absolute() else self.evidence_dir / path
            path = path.resolve(strict=True)
            if not path.is_relative_to(self.evidence_dir.resolve()) or not path.is_file():
                raise Invalid("evidence must be a regular file within the private evidence directory")
            if path.stat().st_size > 8_000_000:
                raise Invalid("evidence file exceeds 8 MB; save a concise relevant receipt")
            key = path.relative_to(self.evidence_dir).as_posix()
            if key in seen:
                raise Invalid("duplicate evidence file")
            seen.add(key)
            result.append({"path": key, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        return result

    def recheck(self, evidence: list[dict[str, Any]]) -> None:
        if self.capture([e["path"] for e in evidence]) != evidence:
            raise Invalid("evidence changed since it was recorded")

    def snapshot(self) -> str:
        """Hash HEAD plus tracked/non-ignored untracked working files, never their contents in DB."""
        head = git(self.root, "rev-parse", "HEAD").strip().decode("ascii")
        paths = sorted(set(git(self.root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0")) - {b""})
        parts: list[Any] = [["HEAD", head]]
        total = 0
        for name in paths:
            rel = os.fsdecode(name)
            path = self.root / rel
            # A symlink in a parent could otherwise make snapshotting read outside this repo.
            parent = path.parent.resolve()
            if not parent.is_relative_to(self.root):
                raise Invalid("working-tree path escapes repository")
            if not path.exists() and not path.is_symlink():
                parts.append([rel, "deleted"])
                continue
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                parts.append([rel, "symlink", os.readlink(path)])
            elif stat.S_ISREG(info.st_mode):
                total += info.st_size
                if info.st_size > 50_000_000 or total > 500_000_000:
                    raise Invalid("snapshot exceeds safety limit (50 MB/file, 500 MB total)")
                parts.append([rel, bool(info.st_mode & stat.S_IXUSR), hashlib.sha256(path.read_bytes()).hexdigest()])
            else:
                raise Invalid("submodules and special files require an external reviewed snapshot adapter")
        return digest(parts)

    def active_events(self) -> list[dict[str, Any]]:
        voided = {v["event_id"] for v in self.records("void")}
        return [e for e in self.records("feedback") if e["id"] not in voided]

    def history_for(self, family: str, epoch: str) -> tuple[dict[tuple[int, str], dict], list[str], list[str]]:
        plans = {p["id"]: p for p in self.records("plan")}
        # One independent task/model/effort is one observation; retries are NOT independent samples.
        samples: dict[tuple[str, int, str], dict[str, Any]] = {}
        actions: set[str] = set()
        source_ids: list[str] = []
        now = self.clock()
        for event in self.active_events():
            plan = plans[event["route_id"]]
            age = now - event["created"]
            if (plan["family"] != family or plan["epoch"] != epoch or plan["policy"] != POLICY
                    or age < 0 or age > WINDOW):
                continue
            if event["status"] == "fail" and event["attribution_confirmed"]:
                actions.add(ACTIONS[event["cause"]])
                source_ids.append(event["id"])
            if not event["runtime_match"] or not event["attribution_confirmed"]:
                continue
            if event["status"] not in {"pass", "fail"}:
                continue
            if event["status"] == "fail" and event["cause"] != "capability":
                continue
            tier = MODELS.index(plan["model"])
            key = (plan["task"]["task_id"], tier, plan["effort"])
            failed = event["status"] == "fail"
            prev = samples.get(key)
            # A later pass does not erase an earlier failed first attempt.
            if prev is None or (failed and not prev["failed"]) or (failed == prev["failed"] and event["created"] > prev["created"]):
                samples[key] = {"failed": failed, "created": event["created"], "id": event["id"]}
        groups: dict[tuple[int, str], dict] = {}
        for (_, tier, effort), sample in samples.items():
            group = groups.setdefault((tier, effort), {"tasks": 0, "failures": 0, "effective_n": 0.0,
                                                        "weighted_failures": 0.0, "recent_failure": False, "event_ids": []})
            age = now - sample["created"]
            weight = 2 ** (-age / HALF_LIFE)
            group["tasks"] += 1
            group["failures"] += int(sample["failed"])
            group["effective_n"] += weight
            group["weighted_failures"] += weight * sample["failed"]
            group["recent_failure"] |= sample["failed"] and age <= PROVISIONAL
            group["event_ids"].append(sample["id"])
        return groups, sorted(actions), sorted(set(source_ids))

    def validate_task(self, task: Any) -> dict[str, Any]:
        fields(task, {"task_id", "kind", "domain", "risk", "critical_flags", "bounded", "independent"},
               {"review_of", "verification_id", "pattern", "scope"})
        identifier(task["task_id"])
        if task["kind"] not in KINDS or task["domain"] not in DOMAINS:
            raise Invalid("unknown task kind/domain")
        fields(task["risk"], set(DIMENSIONS))
        if any(type(v) is not int or not 0 <= v <= 3 for v in task["risk"].values()):
            raise Invalid("risk dimensions must be integers 0..3 (not booleans)")
        flags = task["critical_flags"]
        if not isinstance(flags, list) or any(not isinstance(f, str) or f not in CRITICAL for f in flags) or len(flags) != len(set(flags)):
            raise Invalid("critical_flags must be a unique list of documented risk flags")
        boolean(task["bounded"])
        boolean(task["independent"])
        if task["kind"] == "review":
            targets = task.get("review_of")
            if not isinstance(targets, list) or not targets or len(set(targets)) != len(targets):
                raise Invalid("review must name unique implementation route IDs")
            for rid in targets:
                if self.get(rid, "plan")["task"]["kind"] == "review":
                    raise Invalid("review targets must not be reviews")
            self.get(task.get("verification_id", ""), "verification")
        elif "review_of" in task or "verification_id" in task:
            raise Invalid("review fields are only valid for reviews")
        task = json.loads(canonical(task))
        task["critical_flags"] = sorted(task["critical_flags"])
        task["pattern"] = identifier(task.get("pattern", "general"))
        task["scope"] = identifier(task.get("scope", "repository"))
        return task

    def validate_runtime(self, runtime: Any) -> tuple[str, dict, list[dict]]:
        fields(runtime, {"epoch", "models", "controls", "evidence"})
        epoch = identifier(runtime["epoch"])
        models = runtime["models"]
        if not isinstance(models, dict) or not models:
            raise Invalid("runtime models must be a nonempty object")
        for model, efforts in models.items():
            if model not in MODELS or not isinstance(efforts, list) or not efforts:
                raise Invalid("unsupported model or empty effort list")
            if any(not isinstance(e, str) or e not in EFFORTS for e in efforts) or len(efforts) != len(set(efforts)):
                raise Invalid("invalid supported-effort list")
        controls = runtime["controls"]
        if not isinstance(controls, list) or any(not isinstance(c, str) for c in controls):
            raise Invalid("runtime controls must be an array of strings")
        evidence = self.capture(runtime["evidence"])
        return epoch, models, evidence

    def plan(self, task: dict, runtime: dict) -> dict:
        task = self.validate_task(task)
        epoch, models, runtime_evidence = self.validate_runtime(runtime)
        family = digest({k: task[k] for k in ("kind", "domain", "risk", "critical_flags", "pattern", "scope")})
        groups, actions, source_ids = self.history_for(family, epoch)
        score = sum(task["risk"].values())
        tier = 0 if score <= 3 else 1 if score <= 8 else 2
        if task["critical_flags"] or task["risk"]["blast_radius"] == 3:
            tier = 2
        baseline = tier
        effort = "medium" if tier == 0 else "high"
        reasons = [f"rubric_score={score};baseline={MODELS[tier]}"]
        status = "ready"
        if not task["bounded"] or not task["independent"] or task["risk"]["spec_gap"] == 3:
            status = "parent_only"
            reasons.append("clarify_or_decompose_before_delegation")
        # Never inherit a hard reviewer policy from a role name; derive it from actual targets.
        if task["kind"] == "review":
            verification = self.get(task["verification_id"], "verification")
            self.recheck(verification["evidence"])
            if verification["snapshot"] != self.snapshot():
                raise Invalid("parent verification is stale; rerun it before review")
            if set(verification["route_ids"]) != set(task["review_of"]):
                raise Invalid("review targets differ from parent verification")
            target_tiers = []
            for rid in task["review_of"]:
                target = self.get(rid, "plan")
                if target["epoch"] != epoch:
                    raise Invalid("review runtime epoch differs from implementation")
                target_tiers.append(MODELS.index(target["model"]))
                baseline = max(baseline, target["baseline_tier"])
            tier = max(tier, baseline, min(2, max(target_tiers) + 1))
            effort = "high"
            reasons.append("fresh_reviewer_at_least_one_tier_above_target_unless_target_is_sol")
        # Evidence only RAISES the rubric floor; absence of evidence is never evidence of success.
        while True:
            g = groups.get((tier, effort))
            if not g:
                break
            stable = (g["failures"] >= 3 and g["effective_n"] >= 3
                      and g["weighted_failures"] / g["effective_n"] >= 0.35)
            if not (g["recent_failure"] or stable):
                break
            reasons.append("history:" + ("repeated_failures" if stable else "7_day_provisional_caution"))
            source_ids.extend(g["event_ids"])
            if tier < 2:
                tier += 1
                effort = "high"
            elif effort == "high":
                effort = "xhigh"
            else:
                actions = sorted(set(actions) | {"parent_rethink_or_reduce_scope"})
                status = "rethink_parent"
                break
        # A failed task must not repeatedly retry the same inadequate lane, even after re-scoring.
        same_task_failures = []
        for event in self.active_events():
            old = self.get(event["route_id"], "plan")
            if (old["task"]["task_id"] == task["task_id"] and old["task"]["kind"] == task["kind"]
                    and old["epoch"] == epoch and event["status"] == "fail"):
                same_task_failures.append(event)
                if event["cause"] == "capability" and event["runtime_match"] and event["attribution_confirmed"]:
                    failed_tier = MODELS.index(old["model"])
                    tier = max(tier, min(2, failed_tier + 1))
                    retry_effort = "xhigh" if failed_tier == 2 else "high"
                    effort = EFFORTS[max(EFFORTS.index(effort), EFFORTS.index(retry_effort))]
                    if failed_tier == 2 and EFFORTS.index(old["effort"]) >= EFFORTS.index("xhigh"):
                        status = "rethink_parent"
                        reasons.append("strongest_configured_lane_failed;parent_rethink_required")
        if len({e["route_id"] for e in same_task_failures}) >= 3:
            status = "rethink_parent"
            reasons.append("three_failed_attempts_in_same_task;stop_automatic_retries")
        if not {"model", "reasoning_effort", "fork_turns:none"}.issubset(runtime["controls"]):
            status = "blocked"
            reasons.append("required_native_controls_unavailable")
        model = MODELS[tier]
        if effort not in models.get(model, []):
            status = "blocked"
            reasons.append("selected_model_or_effort_unavailable;no_silent_substitution")
        summary = {f"{MODELS[t]}/{e}": {k: round(v, 4) if isinstance(v, float) else v
                                         for k, v in g.items()} for (t, e), g in groups.items()}
        return self.put("plan", {"policy": POLICY, "task": task, "family": family, "epoch": epoch,
                                "baseline_tier": baseline, "model": model, "effort": effort,
                                "status": status, "reasons": reasons, "required_actions": sorted(set(actions)),
                                "history": summary, "source_event_ids": sorted(set(source_ids)),
                                "runtime_evidence": runtime_evidence,
                                "warning": "Heuristic, selected-history evidence; not a routing accuracy benchmark."})

    def feedback(self, data: dict) -> dict:
        fields(data, {"event_id", "route_id", "agent_id", "status", "cause", "attribution_confirmed",
                      "observed_model", "observed_effort", "runtime_evidence", "evidence"},
               {"diagnostics", "verdict", "fresh_context", "read_only", "metrics"})
        identifier(data["event_id"])
        identifier(data["agent_id"])
        plan = self.get(data["route_id"], "plan")
        if data["status"] not in {"pass", "fail", "blocked", "cancelled"} or data["cause"] not in CAUSES:
            raise Invalid("unknown status/cause")
        if data["status"] == "pass" and data["cause"] != "none":
            raise Invalid("a pass must have cause=none")
        if data["status"] == "fail" and data["cause"] == "none":
            raise Invalid("a failure must include a cause, possibly unknown")
        boolean(data["attribution_confirmed"])
        if data["cause"] == "capability":
            diag = data.get("diagnostics", {})
            fields(diag, {"spec_reviewed", "context_sufficient", "environment_healthy"})
            if not all(boolean(v) for v in diag.values()) or not data["attribution_confirmed"]:
                raise Invalid("confirm specification, context and environment before blaming model capability")
        elif "diagnostics" in data:
            raise Invalid("diagnostics are only used for confirmed capability attribution")
        for key in ("observed_model", "observed_effort"):
            if data[key] is not None:
                identifier(data[key])  # Preserve unexpected actual settings; never credit the requested model.
        observed = data["observed_model"] is not None and data["observed_effort"] is not None
        runtime_evidence = self.capture(data["runtime_evidence"]) if data["runtime_evidence"] else []
        if observed and not runtime_evidence:
            raise Invalid("observable settings require runtime evidence")
        runtime_match = observed and data["observed_model"] == plan["model"] and data["observed_effort"] == plan["effort"]
        if data["status"] in {"pass", "fail"} and plan["status"] != "ready":
            raise Invalid("cannot report execution of a blocked or parent-only delegation")
        if plan["task"]["kind"] == "review":
            if data["status"] in {"pass", "fail"}:
                for flag in ("fresh_context", "read_only"):
                    boolean(data.get(flag))
                if data.get("verdict") not in {"ship", "fix-first", "rethink"}:
                    raise Invalid("completed review verdict is required")
                if (data["status"] == "pass") != (data["verdict"] == "ship"):
                    raise Invalid("review verdict contradicts status")
            else:
                if data.get("verdict") is not None:
                    raise Invalid("blocked/cancelled review must not invent a verdict")
                for flag in ("fresh_context", "read_only"):
                    if flag in data:
                        boolean(data[flag])
            target_agents = {e["agent_id"] for e in self.active_events() if e["route_id"] in plan["task"]["review_of"]}
            if data["agent_id"] in target_agents:
                raise Invalid("reviewer must not be an implementing agent")
        elif any(k in data for k in ("fresh_context", "read_only", "verdict")):
            raise Invalid("review fields are only valid on review feedback")
        if "metrics" in data:
            fields(data["metrics"], set(), {"input_tokens", "output_tokens", "latency_ms"})
            for value in data["metrics"].values():
                if value is not None and (type(value) is not int or value < 0):
                    raise Invalid("metrics must be observed nonnegative integers or null")
        payload = {k: v for k, v in data.items() if k not in {"event_id", "evidence", "runtime_evidence"}}
        payload.update(evidence=self.capture(data["evidence"]), runtime_evidence=runtime_evidence,
                       runtime_match=runtime_match, snapshot=self.snapshot())
        return self.put("feedback", payload, data["event_id"])

    def void(self, event_id: str, reason: str, evidence: list[str]) -> dict:
        self.get(event_id, "feedback")
        if reason not in {"misattribution", "duplicate_task", "bad_evidence", "operator_correction"}:
            raise Invalid("unknown invalidation reason")
        return self.put("void", {"event_id": event_id, "reason": reason, "evidence": self.capture(evidence)})

    def latest(self, route_id: str) -> dict:
        events = [e for e in self.active_events() if e["route_id"] == route_id]
        if not events:
            raise Invalid("missing execution feedback")
        return events[-1]

    def verify(self, route_ids: list[str], evidence: list[str]) -> dict:
        if not route_ids or len(route_ids) != len(set(route_ids)):
            raise Invalid("verification must cover unique implementation routes")
        snap = self.snapshot()
        feedback_ids = {}
        for rid in route_ids:
            plan = self.get(rid, "plan")
            event = self.latest(rid)
            if plan["task"]["kind"] == "review" or event["status"] != "pass" or not event["runtime_match"]:
                raise Invalid("verification requires observed successful implementation routes")
            # Parent integration can change the cumulative snapshot after a worker returns.
            # Its new verification and review must cover that current snapshot, not stale worker diffs.
            self.recheck(event["evidence"])
            self.recheck(event["runtime_evidence"])
            feedback_ids[rid] = event["id"]
        return self.put("verification", {"route_ids": sorted(route_ids), "feedback_ids": feedback_ids, "snapshot": snap,
                                         "evidence": self.capture(evidence)})

    def gate(self, review_id: str) -> dict:
        plan = self.get(review_id, "plan")
        if plan["task"]["kind"] != "review":
            raise Invalid("gate requires a review route")
        review = self.latest(review_id)
        verification = self.get(plan["task"]["verification_id"], "verification")
        current = self.snapshot()
        if (review["status"] != "pass" or review.get("verdict") != "ship" or not review["runtime_match"]
                or not review["fresh_context"] or not review["read_only"]):
            raise Invalid("review is not an observed, fresh, read-only ship verdict")
        if current != review["snapshot"] or current != verification["snapshot"]:
            raise Invalid("working tree changed since verification/review; verify and review again")
        for evidence in (review["evidence"], review["runtime_evidence"], verification["evidence"]):
            self.recheck(evidence)
        for rid in plan["task"]["review_of"]:
            event = self.latest(rid)
            if event["status"] != "pass" or not event["runtime_match"]:
                raise Invalid("implementation has an unresolved failure or runtime mismatch")
            if verification["feedback_ids"].get(rid) != event["id"]:
                raise Invalid("implementation feedback changed after verification; verify and review again")
        return self.put("acceptance", {"review_id": review_id, "snapshot": current,
                                       "verdict": "ship", "limits": "Checks evidence consistency; does not prove code correctness or run tests."})

    def report(self) -> dict:
        events = self.active_events()
        tasks: dict[str, dict] = {}
        for event in events:
            plan = self.get(event["route_id"], "plan")
            key = plan["task"]["task_id"] + ":" + plan["task"]["kind"]
            item = tasks.setdefault(key, {"failed_attempt": False, "pass": False})
            item["failed_attempt"] |= event["status"] == "fail"
            item["pass"] |= event["status"] == "pass"
        completed = [v for v in tasks.values() if v["pass"] or v["failed_attempt"]]
        first_pass = sum(v["pass"] and not v["failed_attempt"] for v in completed)
        return {"policy": POLICY, "plans": len(self.records("plan")), "active_events": len(events),
                "invalidated_events": len({v["event_id"] for v in self.records("void")}),
                "observed_tasks": len(completed), "observed_first_pass_tasks": first_pass,
                "observed_first_pass_fraction": first_pass / len(completed) if completed else None,
                "runtime_unconfirmed_events": sum(not e["runtime_match"] for e in events),
                "by_cause": {c: sum(e["cause"] == c and e["status"] == "fail" for e in events) for c in sorted(CAUSES - {"none"})},
                "limits": "Incomplete/skipped feedback and self-attribution bias these descriptive counts. No causal improvement claim."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("snapshot")
    sub.add_parser("report")
    sub.add_parser("export")
    p = sub.add_parser("plan")
    p.add_argument("--task", type=Path, required=True)
    p.add_argument("--runtime", type=Path, required=True)
    p = sub.add_parser("feedback")
    p.add_argument("--input", type=Path, required=True)
    p = sub.add_parser("void")
    p.add_argument("--event", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--evidence", nargs="+", required=True)
    p = sub.add_parser("verify")
    p.add_argument("--routes", nargs="+", required=True)
    p.add_argument("--evidence", nargs="+", required=True)
    p = sub.add_parser("gate")
    p.add_argument("--review", required=True)
    args = parser.parse_args(argv)
    try:
        with Advisor(args.repo) as advisor:
            if args.command == "init":
                output = {"state_dir": str(advisor.state), "evidence_dir": str(advisor.evidence_dir), "policy": POLICY}
            elif args.command == "snapshot":
                output = {"snapshot": advisor.snapshot()}
            elif args.command == "plan":
                output = advisor.plan(read_json(args.task), read_json(args.runtime))
            elif args.command == "feedback":
                output = advisor.feedback(read_json(args.input))
            elif args.command == "void":
                output = advisor.void(args.event, args.reason, args.evidence)
            elif args.command == "verify":
                output = advisor.verify(args.routes, args.evidence)
            elif args.command == "gate":
                output = advisor.gate(args.review)
            elif args.command == "report":
                output = advisor.report()
            else:
                output = {k: advisor.records(k) for k in ("plan", "feedback", "void", "verification", "acceptance")}
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
        # A valid JSON blocked/parent-only result is NOT permission to dispatch.
        return 3 if args.command == "plan" and output["status"] != "ready" else 0
    except (Invalid, OSError, sqlite3.Error, json.JSONDecodeError, TypeError, KeyError) as exc:
        print(json.dumps({"error": str(exc), "action": "stop_affected_delegation;do_not_ignore"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
