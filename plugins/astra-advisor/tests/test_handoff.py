"""Synthetic contract/policy/integration tests, not a live multi-agent benchmark."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import routing_memory as rm
from agent_reuse import Reuse
from handoff import Handoff, assess, validate_packet, render


def assessment(**kw):
    result = {"purpose": "work", "request": "auto", "bounded": True, "independent": True,
              "inputs_ready": True, "duplicate_work": False, "ownership_clear": True,
              "budget_available": True, "benefit": "parallel_progress", "overhead": "low",
              "parent_work": "Inspect separate documentation while the worker implements the bounded change.",
              "wait_for": "before_integration", "reason": "The interface is settled and the files do not overlap."}
    result.update(kw)
    return result


def packet(**kw):
    result = {"goal": "Preserve the answer contract while adding a focused regression check.",
              "read_only": False, "ownership": ["app.py"], "access_confirmed": True,
              "inputs": [{"ref": "app.py", "purpose": "Current implementation and public answer contract."}],
              "facts": [{"statement": "The current answer is 42.", "source": "app.py", "status": "observed"}],
              "constraints": ["Do not change the public interface or unrelated files."],
              "acceptance": [{"check": "Inspect the answer and run relevant authorized checks.",
                              "expected": "The answer stays 42; return actual results or an explicit verification limit."}],
              "stop_conditions": ["Report a blocker if a public interface change becomes necessary."]}
    result.update(kw)
    return result


class AssessmentTests(unittest.TestCase):
    def test_parallel_independent_work(self):
        self.assertEqual(assess(assessment())["mode"], "delegate")

    def test_no_parallel_progress_when_parent_immediately_waits(self):
        self.assertEqual(assess(assessment(parent_work=None))["mode"], "parent")

    def test_isolate_large_read_only_context(self):
        self.assertEqual(assess(assessment(parent_work=None, benefit="context_isolation"))["mode"], "delegate")

    def test_independent_check_is_useful_without_parallel_parent(self):
        self.assertEqual(assess(assessment(parent_work=None, benefit="independent_check"))["mode"], "delegate")

    def test_trivial_work_without_benefit_stays_local(self):
        self.assertEqual(assess(assessment(benefit="none"))["mode"], "parent")

    def test_coordination_dominates(self):
        self.assertEqual(assess(assessment(overhead="dominates"))["mode"], "parent")

    def test_explicit_user_request_preserved_with_cost_rationale(self):
        self.assertEqual(assess(assessment(request="explicit", overhead="dominates", benefit="none"))["mode"], "delegate")

    def test_no_user_permission_override(self):
        self.assertEqual(assess(assessment(request="forbidden"))["mode"], "parent")

    def test_required_review_not_removed_by_cost_heuristic(self):
        self.assertEqual(assess(assessment(purpose="final_review", overhead="dominates", parent_work=None))["mode"], "delegate")

    def test_required_review_with_forbidden_delegation_is_blocked_not_skipped(self):
        self.assertEqual(assess(assessment(purpose="final_review", request="forbidden"))["mode"], "blocked")

    def test_pending_inputs_wait(self):
        self.assertEqual(assess(assessment(inputs_ready=False))["mode"], "wait")

    def test_duplicate_work_waits_not_respawn(self):
        self.assertEqual(assess(assessment(duplicate_work=True))["mode"], "wait")

    def test_unclear_ownership_waits(self):
        self.assertEqual(assess(assessment(ownership_clear=False))["mode"], "wait")

    def test_no_budget(self):
        self.assertEqual(assess(assessment(budget_available=False))["mode"], "parent")
        self.assertEqual(assess(assessment(purpose="final_review", budget_available=False))["mode"], "blocked")

    def test_unbounded_or_dependent_work_needs_decomposition(self):
        for key in ("bounded", "independent"):
            with self.subTest(key=key):
                self.assertEqual(assess(assessment(**{key: False}))["mode"], "parent")
                self.assertEqual(assess(assessment(request="explicit", **{key: False}))["mode"], "blocked")

    def test_invalid_fields_and_booleans(self):
        for change in ({"bounded": 1}, {"benefit": "magic"}, {"overhead": None}, {"reason": ""}, {"extra": True}):
            with self.subTest(change=change), self.assertRaises((rm.Invalid, TypeError)):
                assess(assessment(**change))

    def test_wait_boundary_is_explicit(self):
        self.assertEqual(assess(assessment())["wait_for"], "before_integration")
        with self.assertRaises(rm.Invalid):
            assess(assessment(wait_for="never_collect_results"))

    def test_assess_cli_does_not_need_a_git_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "assessment.json"
            path.write_text(json.dumps(assessment(benefit="none")), encoding="utf-8")
            process = subprocess.run([sys.executable, str(SCRIPTS / "handoff.py"), "assess", "--input", str(path)],
                                     cwd=tmp, capture_output=True, text=True)
            self.assertEqual(process.returncode, 3, process.stderr)
            self.assertEqual(json.loads(process.stdout)["mode"], "parent")
            self.assertFalse((Path(tmp) / ".git").exists())


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for args in (("init", "-q"), ("config", "user.name", "Synthetic fixture"),
                     ("config", "user.email", "fixture@example.invalid")):
            self.git(*args)
        (self.root / "app.py").write_text("answer = 42\n", encoding="utf-8")
        self.git("add", "app.py")
        self.git("commit", "-qm", "Synthetic fixture")
        self.now = 1800000000.0
        self.a = rm.Advisor(self.root, clock=lambda: self.now)
        self.reuse, self.h = Reuse(self.a), Handoff(self.a)
        for name in ("runtime.json", "checks.txt"):
            (self.a.evidence_dir / name).write_text("SYNTHETIC evidence only\n", encoding="utf-8")
        self.runtime = {"epoch": "fixture-v1", "models": {m: list(rm.EFFORTS) for m in rm.MODELS},
                        "controls": ["model", "reasoning_effort", "fork_turns:none"], "evidence": ["runtime.json"]}
        self.counter = 0

    def tearDown(self):
        self.a.close()
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, check=True).stdout

    def task(self, **kw):
        self.counter += 1
        t = {"task_id": f"t{self.counter}", "kind": "implementation", "domain": "general",
             "risk": dict.fromkeys(rm.DIMENSIONS, 0), "critical_flags": [], "bounded": True, "independent": True}
        t.update(kw)
        return t

    def context(self, **kw):
        c = {"session_id": "fixture-session", "ownership": ["app.py"], "continuation": "same_task",
             "candidate_agent_id": None, "agent_state": "unobservable", "context_state": "unknown",
             "delta_ready": False, "observed_model": None, "observed_effort": None,
             "continuation_tool": None, "evidence": ["runtime.json"]}
        c.update(kw)
        return c

    def decision(self, task=None, context=None):
        r = self.a.plan(task or self.task(), self.runtime)
        d = self.reuse.plan(r["id"], context or self.context())
        return r, d

    def source(self, r, *, p=None, intent=None):
        self.counter += 1
        value = {"schema_version": 1, "task_id": r["task"]["task_id"],
                 "assessment": intent or assessment(), "packet": p or packet()}
        path = self.a.evidence_dir / f"packet-{self.counter}.json"
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def prepare(self, r, d, **kw):
        path = self.source(r, **kw)
        return self.h.prepare(d["id"], path), path

    def complete(self, r, claim, agent, mode="fresh", **kw):
        self.counter += 1
        event = {"event_id": f"feedback-{self.counter}", "route_id": r["id"], "agent_id": agent,
                 "status": "pass", "cause": "none", "attribution_confirmed": True,
                 "observed_model": r["model"], "observed_effort": r["effort"],
                 "runtime_evidence": ["runtime.json"], "evidence": ["checks.txt"]}
        if r["task"]["kind"] == "review":
            event.update(verdict="ship", fresh_context=True, read_only=True)
        event.update(kw)
        e = self.a.feedback(event)
        self.reuse.finish({"claim_id": claim["claim_id"], "feedback_id": e["id"], "actual_mode": mode,
                           "agent_state": "idle", "evidence": ["runtime.json"]})
        return e

    def worker(self):
        r, d = self.decision()
        prepared, path = self.prepare(r, d)
        claim = self.h.claim(prepared["id"])
        self.complete(r, claim, "worker-" + r["id"])
        return r, path

    def review(self, worker, **kw):
        v = self.a.verify([worker["id"]], ["checks.txt"])
        r, d = self.decision(self.task(kind="review", review_of=[worker["id"]], verification_id=v["id"]),
                             self.context(ownership=[]))
        p = packet(read_only=True, ownership=[], review={"change_refs": ["current diff: app.py"],
                                                        "verification_refs": ["evidence:checks.txt"]})
        prepared, path = self.prepare(r, d, p=p, intent=assessment(purpose="final_review", parent_work=None,
                                                                  wait_for="before_acceptance"))
        claim = self.h.claim(prepared["id"])
        self.complete(r, claim, "reviewer-" + r["id"], **kw)
        return r, path

    def test_fresh_packet_contains_goal_boundary_checks_stop_and_output(self):
        r, d = self.decision()
        prepared, _ = self.prepare(r, d)
        for section in ("ASTRA HANDOFF TASK", "GOAL", "BOUNDARIES", "INPUTS", "ACCEPTANCE", "STOP / ESCALATE", "RETURN"):
            self.assertIn(section, prepared["message"])
        self.assertNotIn("rationale", prepared["message"])
        self.assertNotIn("gpt-5.6", prepared["message"])

    def test_preparing_does_not_reserve_or_dispatch(self):
        r, d = self.decision()
        self.prepare(r, d)
        self.assertEqual(self.reuse.pending(), [])
        self.assertEqual(self.a.records("handoff_dispatch"), [])

    def test_claim_preserves_model_and_exposes_only_child_message(self):
        r, d = self.decision()
        prepared, _ = self.prepare(r, d)
        claim = self.h.claim(prepared["id"])
        self.assertEqual(claim["requested_model"], r["model"])
        self.assertEqual(claim["message"], prepared["message"])
        self.assertEqual(len(self.reuse.pending()), 1)

    def test_no_prompt_text_in_history(self):
        r, d = self.decision()
        prepared, _ = self.prepare(r, d)
        self.h.claim(prepared["id"])
        stored = json.dumps(self.a.records("handoff") + self.a.records("handoff_dispatch"))
        self.assertNotIn(packet()["goal"], stored)
        self.assertNotIn(assessment()["parent_work"], stored)
        self.assertIn("message_sha256", stored)

    def test_changed_packet_rejected_before_claim(self):
        r, d = self.decision()
        prepared, path = self.prepare(r, d)
        path.write_text(path.read_text() + "\n")
        with self.assertRaises(rm.Invalid): self.h.claim(prepared["id"])
        self.assertEqual(self.reuse.pending(), [])

    def test_changed_source_rejected_before_dispatch(self):
        r, d = self.decision()
        prepared, _ = self.prepare(r, d)
        (self.root / "app.py").write_text("answer = 43\n")
        with self.assertRaises(rm.Invalid): self.h.claim(prepared["id"])

    def test_expired_decision_rejected(self):
        r, d = self.decision()
        prepared, _ = self.prepare(r, d)
        self.now += 301
        with self.assertRaises(rm.Invalid): self.h.claim(prepared["id"])

    def test_new_feedback_requires_model_replan(self):
        r, d = self.decision()
        prepared, _ = self.prepare(r, d)
        self.a.feedback({"event_id": "cancelled", "route_id": r["id"], "agent_id": "not-started",
                         "status": "cancelled", "cause": "unknown", "attribution_confirmed": False,
                         "observed_model": None, "observed_effort": None, "runtime_evidence": [], "evidence": ["checks.txt"]})
        with self.assertRaises(rm.Invalid): self.h.claim(prepared["id"])

    def test_no_duplicate_claim(self):
        r, d = self.decision()
        prepared, _ = self.prepare(r, d)
        self.h.claim(prepared["id"])
        with self.assertRaises(rm.Invalid): self.h.claim(prepared["id"])

    def test_conflicting_files_remain_reserved(self):
        r, d = self.decision()
        prepared, _ = self.prepare(r, d)
        self.h.claim(prepared["id"])
        r2, d2 = self.decision()
        other, _ = self.prepare(r2, d2)
        with self.assertRaises(rm.Invalid): self.h.claim(other["id"])

    def test_wrong_task_rejected(self):
        r, d = self.decision()
        path = self.source(r)
        v = json.loads(path.read_text()); v["task_id"] = "other"; path.write_text(json.dumps(v))
        with self.assertRaises(rm.Invalid): self.h.prepare(d["id"], path)

    def test_schema_and_extra_fields_rejected(self):
        for change in ({"schema_version": True}, {"schema_version": 2}, {"full_transcript": "do not transmit"}):
            r, d = self.decision(); path = self.source(r)
            v = json.loads(path.read_text()); v.update(change); path.write_text(json.dumps(v))
            with self.subTest(change=change), self.assertRaises(rm.Invalid): self.h.prepare(d["id"], path)

    def test_private_input_required(self):
        r, d = self.decision()
        private = self.source(r)
        outside = self.root / "packet.json"; outside.write_bytes(private.read_bytes())
        with self.assertRaises(rm.Invalid): self.h.prepare(d["id"], outside)

    def test_non_delegation_assessment_cannot_claim(self):
        r, d = self.decision()
        for change in ({"benefit": "none"}, {"inputs_ready": False}, {"duplicate_work": True}):
            with self.subTest(change=change), self.assertRaises(rm.Invalid):
                self.prepare(r, d, intent=assessment(**change))

    def test_unavailable_model_route_cannot_prepare(self):
        self.runtime["models"].pop(rm.MODELS[2])
        r, d = self.decision(self.task(critical_flags=["security"]))
        with self.assertRaises(rm.Invalid): self.prepare(r, d)

    def test_ownership_mismatch_rejected(self):
        r, d = self.decision()
        with self.assertRaises(rm.Invalid): self.prepare(r, d, p=packet(ownership=["other.py"]))

    def test_readonly_and_write_permissions_cannot_conflict(self):
        r, d = self.decision()
        with self.assertRaises(rm.Invalid): self.prepare(r, d, p=packet(read_only=True))

    def test_missing_acceptance_stop_or_input_rejected(self):
        r, d = self.decision()
        for key in ("acceptance", "stop_conditions", "inputs", "constraints"):
            with self.subTest(key=key), self.assertRaises(rm.Invalid): self.prepare(r, d, p=packet(**{key: []}))

    def test_inaccessible_inputs_rejected(self):
        r, d = self.decision()
        with self.assertRaises(rm.Invalid): self.prepare(r, d, p=packet(access_confirmed=False))

    def test_assumptions_are_labeled(self):
        r, d = self.decision()
        p = packet(facts=[{"statement": "The issue may be in the adapter.", "source": "app.py", "status": "hypothesis"}])
        prepared, _ = self.prepare(r, d, p=p)
        self.assertIn("[hypothesis]", prepared["message"])

    def test_oversized_context_rejected_not_silently_truncated(self):
        r, d = self.decision()
        with self.assertRaises(rm.Invalid):
            self.prepare(r, d, p=packet(constraints=[str(n) + "x" * 1590 for n in range(16)]))

    def test_resolve_historical_process_actions(self):
        r, d = self.decision(); prepared, _ = self.prepare(r, d)
        claim = self.h.claim(prepared["id"])
        self.complete(r, claim, "worker", status="fail", cause="spec_gap")
        r2, d2 = self.decision()
        with self.assertRaises(rm.Invalid): self.prepare(r2, d2)
        p = packet(resolved_actions={code: {"resolution": "Specify the expected output in acceptance.", "source": "checks.txt"}
                                     for code in r2["required_actions"]})
        prepared, _ = self.prepare(r2, d2, p=p)
        self.assertNotIn("rewrite_acceptance_criteria_before_dispatch", prepared["message"])

    def test_reuse_sends_delta_with_same_agent(self):
        worker, _ = self.worker()
        r, d = self.decision(copy.deepcopy(worker["task"]), self.context(
            candidate_agent_id="worker-" + worker["id"], agent_state="idle", context_state="usable",
            delta_ready=True, observed_model=worker["model"], observed_effort=worker["effort"], continuation_tool="fixture.followup"))
        self.assertEqual(d["mode"], "reuse")
        p = packet(facts=[], delta={"findings": ["Add the missing boundary check."], "changed_refs": ["app.py"]})
        prepared, _ = self.prepare(r, d, p=p)
        claim = self.h.claim(prepared["id"])
        self.assertIn("ASTRA HANDOFF DELTA", claim["message"])
        self.assertIn("Reread changed owned files", claim["message"])
        self.assertEqual(claim["candidate_agent_id"], "worker-" + worker["id"])
        self.complete(r, claim, claim["candidate_agent_id"], mode="reuse")

    def test_fresh_packet_rejects_delta_only_payload(self):
        r, d = self.decision()
        with self.assertRaises(rm.Invalid):
            self.prepare(r, d, p=packet(delta={"findings": ["fix"], "changed_refs": []}))

    def test_continuation_requires_real_delta(self):
        p = packet(delta={"findings": [], "changed_refs": []})
        with self.assertRaises(rm.Invalid): validate_packet(p, "reuse", "implementation", ["app.py"])
        with self.assertRaises(rm.Invalid): validate_packet(packet(), "reuse", "implementation", ["app.py"])

    def test_review_role_cannot_bypass_worker_policy(self):
        r, d = self.decision()
        with self.assertRaises(rm.Invalid): self.prepare(r, d, intent=assessment(purpose="final_review"))

    def test_review_requires_changes_and_verification_sources(self):
        p = packet(read_only=True, ownership=[])
        with self.assertRaises(rm.Invalid): validate_packet(p, "fresh", "review", [])

    def test_review_always_fresh_readonly(self):
        p = packet(read_only=True, ownership=[], review={"change_refs": ["app.py"], "verification_refs": ["checks.txt"]})
        with self.assertRaises(rm.Invalid): validate_packet(p, "reuse", "review", [])
        message = render("review", "fresh", "review", validate_packet(p, "fresh", "review", []))
        self.assertIn("ASTRA HANDOFF REVIEW", message)
        self.assertIn("not the implementer's claim", message)
        self.assertIn("VERDICT: ship | fix-first | rethink", message)

    def test_full_prepared_worker_to_fresh_review_gate(self):
        worker, _ = self.worker()
        review, _ = self.review(worker)
        self.assertEqual(self.h.gate(review["id"])["verdict"], "ship")

    def test_final_gate_rejects_changed_code(self):
        worker, _ = self.worker(); review, _ = self.review(worker)
        (self.root / "app.py").write_text("answer = 0\n")
        with self.assertRaises(rm.Invalid): self.h.gate(review["id"])

    def test_final_gate_rejects_changed_handoff_evidence(self):
        worker, path = self.worker(); review, _ = self.review(worker)
        path.write_text(path.read_text() + "\n")
        with self.assertRaises(rm.Invalid): self.h.gate(review["id"])

    def test_fix_first_is_not_acceptance(self):
        worker, _ = self.worker()
        review, _ = self.review(worker, status="fail", cause="verification_gap", verdict="fix-first")
        with self.assertRaises(rm.Invalid): self.h.gate(review["id"])

    def test_legacy_dispatch_cannot_claim_handoff_enabled_acceptance(self):
        r, d = self.decision()
        legacy = self.reuse.claim(d["id"])
        self.complete(r, {"claim_id": legacy["id"]}, "legacy-worker")
        review, _ = self.review(r)
        self.assertEqual(self.reuse.gate(review["id"])["verdict"], "ship")
        with self.assertRaises(rm.Invalid): self.h.gate(review["id"])

    def test_prepare_and_claim_cli_on_real_local_store(self):
        import time
        self.now = time.time()
        r, d = self.decision()
        path = self.source(r)
        command = [sys.executable, str(SCRIPTS / "handoff.py"), "--repo", str(self.root)]
        prepared = subprocess.run(command + ["prepare", "--decision", d["id"], "--input", str(path)],
                                  capture_output=True, text=True)
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        h = json.loads(prepared.stdout)
        claimed = subprocess.run(command + ["claim", "--handoff", h["id"]], capture_output=True, text=True)
        self.assertEqual(claimed.returncode, 0, claimed.stderr)
        self.assertEqual(json.loads(claimed.stdout)["message"], h["message"])
        self.assertEqual(len(self.reuse.pending()), 1)

    def test_cli_invalid_json_reports_failure(self):
        path = self.a.evidence_dir / "bad.json"; path.write_text('{"purpose": "work", "purpose": "final_review"}')
        result = subprocess.run([sys.executable, str(SCRIPTS / "handoff.py"), "assess", "--input", str(path)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate JSON key", result.stderr)


if __name__ == "__main__":
    unittest.main()
