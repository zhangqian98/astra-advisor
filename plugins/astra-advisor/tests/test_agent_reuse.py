"""Synthetic reuse/feedback invariants. No model calls or cost benchmark."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from agent_reuse import Reuse, DECISION_TTL, IDLE_TTL, ownership
from routing_memory import Advisor, Invalid, MODELS, EFFORTS, DIMENSIONS, DAY


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic test")
        self.git("config", "user.email", "test@example.invalid")
        (self.root / "app.py").write_text("answer = 42\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Synthetic fixture")
        self.now = 1_800_000_000.0
        self.a = Advisor(self.root, clock=lambda: self.now)
        self.r = Reuse(self.a)
        self.counter = 0
        (self.a.evidence_dir / "runtime.json").write_text('{"synthetic":true}')
        (self.a.evidence_dir / "checks.txt").write_text("SYNTHETIC checks, not real model output")
        self.runtime = {"epoch": "test-runtime", "models": {m: list(EFFORTS) for m in MODELS},
                        "controls": ["model", "reasoning_effort", "fork_turns:none"], "evidence": ["runtime.json"]}

    def tearDown(self):
        self.a.close()
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, check=True).stdout

    def route(self, task_id="task-one", **kw):
        task = {"task_id": task_id, "kind": "implementation", "domain": "general",
                "risk": dict.fromkeys(DIMENSIONS, 0), "critical_flags": [], "bounded": True, "independent": True}
        task.update(kw)
        return self.a.plan(task, self.runtime)

    def context(self, candidate=None, **kw):
        value = {"session_id": "parent-one", "ownership": ["app.py"], "continuation": "same_task",
                 "candidate_agent_id": candidate, "agent_state": "idle", "context_state": "usable",
                 "delta_ready": True, "observed_model": MODELS[0], "observed_effort": "medium",
                 "continuation_tool": "native.observed_followup", "evidence": ["runtime.json"]}
        value.update(kw)
        return value

    def feedback(self, route, agent="worker-one", status="pass", cause="none", **kw):
        self.counter += 1
        event = {"event_id": f"e{self.counter}", "route_id": route["id"], "agent_id": agent,
                 "status": status, "cause": cause, "attribution_confirmed": True,
                 "observed_model": route["model"], "observed_effort": route["effort"],
                 "runtime_evidence": ["runtime.json"], "evidence": ["checks.txt"]}
        if cause == "capability":
            event["diagnostics"] = dict.fromkeys(("spec_reviewed", "context_sufficient", "environment_healthy"), True)
        event.update(kw)
        return self.a.feedback(event)

    def run_worker(self, route=None, candidate=None, agent="worker-one", status="pass", cause="none", **finish_kw):
        route = route or self.route()
        d = self.r.plan(route["id"], self.context(candidate))
        claim = self.r.claim(d["id"])
        e = self.feedback(route, agent, status, cause)
        result = self.r.finish({"claim_id": claim["id"], "feedback_id": e["id"], "actual_mode": d["mode"],
                                "agent_state": "idle", "evidence": ["runtime.json"], **finish_kw})
        return route, d, e, result

    def test_first_attempt_is_fresh(self):
        self.assertEqual(self.run_worker()[1]["mode"], "fresh")

    def test_same_task_continues_same_worker(self):
        self.run_worker()
        d = self.r.plan(self.route()["id"], self.context("worker-one"))
        self.assertEqual((d["mode"], d["handoff"]), ("reuse", "bounded_delta_only"))

    def test_closed_worker_can_resume_only_with_live_tool(self):
        self.run_worker()
        d = self.r.plan(self.route()["id"], self.context("worker-one", agent_state="closed"))
        self.assertEqual(d["mode"], "reuse")
        d = self.r.plan(self.route()["id"], self.context("worker-one", continuation_tool=None))
        self.assertEqual(d["mode"], "fresh")

    def test_unknown_worker_not_reused(self):
        self.assertEqual(self.r.plan(self.route()["id"], self.context("invented"))["mode"], "fresh")

    def test_busy_worker_is_wait_not_duplicate_spawn(self):
        self.run_worker()
        d = self.r.plan(self.route()["id"], self.context("worker-one", agent_state="running"))
        self.assertEqual(d["mode"], "wait")
        with self.assertRaises(Invalid): self.r.claim(d["id"])

    def test_model_upgrade_beats_reuse(self):
        self.run_worker(status="fail", cause="capability")
        route = self.route()
        self.assertEqual(route["model"], MODELS[1])
        self.assertEqual(self.r.plan(route["id"], self.context("worker-one"))["mode"], "fresh")

    def test_same_model_different_effort_is_fresh(self):
        self.run_worker()
        d = self.r.plan(self.route()["id"], self.context("worker-one", observed_effort="high"))
        self.assertEqual(d["mode"], "fresh")

    def test_epoch_change_is_fresh(self):
        self.run_worker()
        self.runtime["epoch"] = "runtime-two"
        self.assertEqual(self.r.plan(self.route()["id"], self.context("worker-one"))["mode"], "fresh")

    def test_parent_session_change_is_fresh(self):
        self.run_worker()
        c = self.context("worker-one", session_id="parent-two")
        self.assertEqual(self.r.plan(self.route()["id"], c)["mode"], "fresh")

    def test_related_task_requires_explicit_opt_in(self):
        self.run_worker()
        route = self.route("task-two")
        self.assertEqual(self.r.plan(route["id"], self.context("worker-one"))["mode"], "fresh")
        self.assertEqual(self.r.plan(route["id"], self.context("worker-one", continuation="related_task"))["mode"], "reuse")

    def test_boundary_changes_are_fresh(self):
        self.run_worker()
        for change in ({"domain": "api"}, {"scope": "other"}, {"pattern": "other"}, {"kind": "debug"}):
            with self.subTest(change=change):
                self.assertEqual(self.r.plan(self.route(**change)["id"], self.context("worker-one"))["mode"], "fresh")

    def test_ownership_changes_are_fresh(self):
        self.run_worker()
        c = self.context("worker-one", ownership=["other.py"])
        self.assertEqual(self.r.plan(self.route()["id"], c)["mode"], "fresh")

    def test_untrusted_context_never_reused(self):
        self.run_worker()
        for state in ("stale", "suspect", "near_limit", "unknown"):
            with self.subTest(state=state):
                d = self.r.plan(self.route()["id"], self.context("worker-one", context_state=state))
                self.assertEqual(d["mode"], "fresh")

    def test_missing_delta_forces_fresh(self):
        self.run_worker()
        self.assertEqual(self.r.plan(self.route()["id"], self.context("worker-one", delta_ready=False))["mode"], "fresh")

    def test_context_pressure_forces_fresh(self):
        self.run_worker()
        c = self.context("worker-one", context_tokens=75, context_limit=100)
        self.assertEqual(self.r.plan(self.route()["id"], c)["mode"], "fresh")
        c["context_tokens"] = 74
        self.assertEqual(self.r.plan(self.route()["id"], c)["mode"], "reuse")

    def test_unknown_tokens_not_invented_as_zero(self):
        self.run_worker()
        c = self.context("worker-one", context_tokens=None, context_limit=None)
        self.assertEqual(self.r.plan(self.route()["id"], c)["mode"], "reuse")
        self.assertIsNone(self.r.report()["by_mode"]["fresh"]["metrics"]["input_tokens"]["observed_sum"])

    def test_old_worker_is_fresh(self):
        self.run_worker()
        self.now += IDLE_TTL + 1
        self.assertEqual(self.r.plan(self.route()["id"], self.context("worker-one"))["mode"], "fresh")

    def test_two_failed_attempts_force_fresh(self):
        self.run_worker(status="fail", cause="spec_gap")
        self.run_worker(candidate="worker-one", status="fail", cause="spec_gap")
        d = self.r.plan(self.route()["id"], self.context("worker-one"))
        self.assertEqual(d["reason"], "repeated_worker_failures")

    def test_continuation_budget(self):
        self.run_worker()
        for _ in range(4): self.run_worker(candidate="worker-one")
        d = self.r.plan(self.route()["id"], self.context("worker-one"))
        self.assertEqual(d["reason"], "continuation_budget_exhausted")

    def test_blocked_model_route_cannot_dispatch(self):
        route = self.route(bounded=False)
        d = self.r.plan(route["id"], self.context())
        self.assertEqual(d["mode"], "blocked")
        with self.assertRaises(Invalid): self.r.claim(d["id"])

    def test_expired_decision_rejected(self):
        d = self.r.plan(self.route()["id"], self.context())
        self.now += DECISION_TTL + 1
        with self.assertRaises(Invalid): self.r.claim(d["id"])

    def test_source_change_invalidates_claim(self):
        d = self.r.plan(self.route()["id"], self.context())
        (self.root / "app.py").write_text("changed = True")
        with self.assertRaises(Invalid): self.r.claim(d["id"])

    def test_evidence_change_invalidates_claim(self):
        d = self.r.plan(self.route()["id"], self.context())
        (self.a.evidence_dir / "runtime.json").write_text("changed")
        with self.assertRaises(Invalid): self.r.claim(d["id"])

    def test_claim_is_one_shot(self):
        d = self.r.plan(self.route()["id"], self.context())
        self.r.claim(d["id"])
        with self.assertRaises(Invalid): self.r.claim(d["id"])

    def test_completed_route_requires_new_attempt_id(self):
        route, _, _, _ = self.run_worker()
        with self.assertRaises(Invalid): self.r.plan(route["id"], self.context("worker-one"))

    def test_pending_claim_survives_timeout(self):
        d = self.r.plan(self.route()["id"], self.context())
        self.r.claim(d["id"])
        self.now += 2 * IDLE_TTL
        other = self.r.plan(self.route("other")["id"], self.context())
        with self.assertRaises(Invalid): self.r.claim(other["id"])

    def test_disjoint_writers_can_run_in_parallel(self):
        d = self.r.plan(self.route()["id"], self.context())
        self.r.claim(d["id"])
        d = self.r.plan(self.route("other")["id"], self.context(ownership=["other.py"]))
        self.r.claim(d["id"])
        self.assertEqual(len(self.r.pending()), 2)

    def test_concurrent_claims_have_one_winner(self):
        decisions = [self.r.plan(self.route(str(i))["id"], self.context())["id"] for i in range(2)]
        def claim(d):
            with Advisor(self.root, clock=lambda: self.now) as a:
                try:
                    Reuse(a).claim(d)
                    return True
                except Invalid:
                    return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(claim, decisions)), 1)

    def test_feedback_must_match_claim(self):
        d = self.r.plan(self.route()["id"], self.context())
        claim = self.r.claim(d["id"])
        e = self.feedback(self.route("other"))
        with self.assertRaises(Invalid):
            self.r.finish(dict(claim_id=claim["id"], feedback_id=e["id"], actual_mode="fresh", agent_state="idle", evidence=["runtime.json"]))

    def test_different_agent_not_claimed_as_reuse(self):
        self.run_worker()
        with self.assertRaises(Invalid): self.run_worker(candidate="worker-one", agent="wrong-worker")

    def test_running_worker_does_not_release_lock(self):
        with self.assertRaises(Invalid): self.run_worker(agent_state="running")
        self.assertEqual(len(self.r.pending()), 1)

    def test_unobserved_mode_not_eligible_for_reuse(self):
        self.run_worker(actual_mode="unobservable")
        self.assertEqual(self.r.plan(self.route()["id"], self.context("worker-one"))["mode"], "fresh")

    def test_usage_cache_subset_validation(self):
        usage = dict(call_id="call-one", input_tokens=100, cached_input_tokens=101, output_tokens=5, latency_ms=10)
        with self.assertRaises(Invalid): self.run_worker(usage=usage)

    def test_usage_call_deduplicated(self):
        usage = dict(call_id="call-one", input_tokens=100, cached_input_tokens=90, output_tokens=5, latency_ms=10)
        self.run_worker(usage=usage)
        with self.assertRaises(Invalid): self.run_worker(candidate="worker-one", usage=usage)

    def test_usage_receipt_counts_cache_as_subset(self):
        self.run_worker(usage=dict(call_id="c1", input_tokens=100, cached_input_tokens=90, output_tokens=5, latency_ms=None))
        m = self.r.report()["by_mode"]["fresh"]["metrics"]
        self.assertEqual(m["input_tokens"]["observed_sum"], 100)
        self.assertEqual(m["cached_input_tokens"]["observed_sum"], 90)
        self.assertIsNone(m["latency_ms"]["observed_sum"])

    def context_failure(self):
        self.run_worker()
        route, d, e, r = self.run_worker(candidate="worker-one", status="fail", cause="context_gap")
        lesson = self.r.lesson(e["id"], "stale_context", ["checks.txt"])
        return route, e, lesson

    def test_context_failure_teaches_next_route_to_start_fresh(self):
        _, e, lesson = self.context_failure()
        p = self.route()
        d = self.r.plan(p["id"], self.context("worker-one"))
        self.assertEqual(d["reason"], "history_context_failure_caution")
        self.assertIn(lesson["id"], d["source_lesson_ids"])
        self.assertEqual(p["model"], MODELS[0])  # context failure is not capability failure

    def test_late_failure_overrides_initial_success(self):
        self.run_worker()
        p, _, _, _ = self.run_worker(candidate="worker-one")
        e = self.feedback(p, status="fail", cause="context_gap")
        self.r.lesson(e["id"], "anchoring", ["checks.txt"])
        self.assertTrue(self.r.caution(self.route()))

    def test_voided_misattribution_removes_caution(self):
        _, e, _ = self.context_failure()
        self.a.void(e["id"], "misattribution", ["checks.txt"])
        self.assertFalse(self.r.caution(self.route()))

    def test_single_lesson_expires_after_seven_days(self):
        self.context_failure()
        self.now += 7 * DAY + 1
        self.assertFalse(self.r.caution(self.route()))

    def test_context_history_is_scoped_by_runtime_and_pattern(self):
        self.context_failure()
        self.assertFalse(self.r.caution(self.route(pattern="different")))
        self.runtime["epoch"] = "next-runtime"
        self.assertFalse(self.r.caution(self.route()))

    def test_stale_lesson_evidence_not_used_for_learning(self):
        self.context_failure()
        (self.a.evidence_dir / "checks.txt").write_text("changed")
        self.assertFalse(self.r.caution(self.route()))

    def test_capability_failure_not_relabelled_context(self):
        self.run_worker()
        _, _, e, _ = self.run_worker(candidate="worker-one", status="fail", cause="capability")
        with self.assertRaises(Invalid): self.r.lesson(e["id"], "anchoring", ["checks.txt"])

    def test_unknown_fields_and_nonbooleans_rejected(self):
        for kw in ({"prompt": "unsafe free text"}, {"delta_ready": 1}, {"context_tokens": True}):
            with self.subTest(kw=kw), self.assertRaises(Invalid):
                self.r.plan(self.route()["id"], self.context(**kw))

    def test_unsafe_owned_paths_rejected(self):
        for path in (".", "../outside", "/tmp/absolute", "C:\\temp", "src/*", ".git/config", "a//b", "a/./b"):
            with self.subTest(path=path), self.assertRaises(Invalid): ownership([path])

    def test_directory_cannot_be_an_exact_owned_file(self):
        (self.root / "src").mkdir()
        with self.assertRaises(Invalid): self.r.plan(self.route()["id"], self.context(ownership=["src"]))

    def review_route(self, p):
        v = self.a.verify([p["id"]], ["checks.txt"])
        return self.route("review-task", kind="review", review_of=[p["id"]], verification_id=v["id"])

    def test_reviewer_always_fresh(self):
        p, _, _, _ = self.run_worker()
        route = self.review_route(p)
        d = self.r.plan(route["id"], self.context("worker-one", ownership=[]))
        self.assertEqual(d["mode"], "fresh")
        self.assertEqual(route["model"], MODELS[1])

    def test_end_to_end_reuse_then_fresh_review_gate(self):
        self.run_worker()
        p, _, _, _ = self.run_worker(candidate="worker-one")
        route = self.review_route(p)
        d = self.r.plan(route["id"], self.context(ownership=[]))
        claim = self.r.claim(d["id"])
        e = self.feedback(route, agent="fresh-reviewer", verdict="ship", fresh_context=True, read_only=True)
        self.r.finish(dict(claim_id=claim["id"], feedback_id=e["id"], actual_mode="fresh", agent_state="idle", evidence=["runtime.json"]))
        self.assertEqual(self.r.gate(route["id"])["verdict"], "ship")
        (self.root / "app.py").write_text("source changed after review")
        with self.assertRaises(Invalid): self.r.gate(route["id"])

    def test_gate_rejects_missing_dispatch_receipt(self):
        p, _, _, _ = self.run_worker()
        route = self.review_route(p)
        self.feedback(route, agent="reviewer", verdict="ship", fresh_context=True, read_only=True)
        with self.assertRaises(Invalid): self.r.gate(route["id"])

    def test_state_is_inside_git_not_source_tree(self):
        self.run_worker()
        self.assertNotIn(b"astra-advisor", self.git("status", "--porcelain"))

    def test_feedback_after_routing_requires_model_replan(self):
        old, _, _, _ = self.run_worker()
        new = self.route()
        self.feedback(old, status="fail", cause="capability")
        with self.assertRaises(Invalid): self.r.plan(new["id"], self.context("worker-one"))

    def test_new_feedback_invalidates_existing_decision(self):
        old, _, _, _ = self.run_worker()
        d = self.r.plan(self.route()["id"], self.context("worker-one"))
        self.feedback(old, status="fail", cause="context_gap")
        with self.assertRaises(Invalid): self.r.claim(d["id"])

    def test_cancelled_dispatch_can_release_ownership_with_evidence(self):
        route = self.route()
        d = self.r.plan(route["id"], self.context())
        claim = self.r.claim(d["id"])
        e = self.feedback(route, status="cancelled", cause="unknown", observed_model=None, observed_effort=None)
        self.r.finish(dict(claim_id=claim["id"], feedback_id=e["id"], actual_mode="unobservable",
                           agent_state="not_started", evidence=["runtime.json"]))
        self.assertEqual(self.r.pending(), [])

    def test_repeated_finish_does_not_double_count_usage(self):
        _, _, e, result = self.run_worker()
        with self.assertRaises(Invalid):
            self.r.finish(dict(claim_id=result["claim_id"], feedback_id=e["id"], actual_mode="fresh",
                               agent_state="idle", evidence=["runtime.json"]))
        self.assertEqual(self.r.report()["by_mode"]["fresh"]["attempts"], 1)

    def test_cross_worktree_cannot_reuse_live_agent(self):
        self.run_worker()
        path = self.root / "other-worktree"
        self.git("worktree", "add", "-q", "-b", "synthetic-branch", str(path))
        with Advisor(path, clock=lambda: self.now) as a:
            task = copy.deepcopy(self.route()["task"])
            route = a.plan(task, self.runtime)
            self.assertEqual(Reuse(a).plan(route["id"], self.context("worker-one"))["mode"], "fresh")

    def test_context_lesson_is_idempotent(self):
        _, e, first = self.context_failure()
        second = self.r.lesson(e["id"], "stale_context", ["checks.txt"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.a.records("reuse_lesson")), 1)

    def test_context_history_expires_at_ninety_days(self):
        self.context_failure()
        self.now += 91 * DAY
        self.assertFalse(self.r.caution(self.route()))

    def test_failed_attempts_on_same_task_not_independent_samples(self):
        self.context_failure()
        self.now += 8 * DAY
        # One task is not repeated independent evidence after provisional caution expires.
        self.assertFalse(self.r.caution(self.route()))

    def test_independent_context_failures_persist_beyond_provisional_period(self):
        targets = []
        for i in range(3):
            task_id, agent = f"task-{i}", f"agent-{i}"
            self.run_worker(route=self.route(task_id), agent=agent)
            route, _, _, _ = self.run_worker(route=self.route(task_id), candidate=agent, agent=agent)
            targets.append((route, agent))
        # Discover failures later, after all three independent task attempts completed.
        for route, agent in targets:
            e = self.feedback(route, agent=agent, status="fail", cause="context_gap")
            self.r.lesson(e["id"], "anchoring", ["checks.txt"])
        self.now += 8 * DAY
        self.assertEqual(len(self.r.caution(self.route("next-task"))), 3)

    def test_claim_rejects_voided_outcome_changes(self):
        p, _, e, _ = self.run_worker()
        d = self.r.plan(self.route()["id"], self.context("worker-one"))
        self.a.void(e["id"], "operator_correction", ["checks.txt"])
        with self.assertRaises(Invalid): self.r.claim(d["id"])

    def test_cli_report_and_invalid_input_exit(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "agent_reuse.py"
        p = subprocess.run([sys.executable, str(script), "--repo", str(self.root), "report"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(json.loads(p.stdout)["policy"], "reuse-v1")
        p = subprocess.run([sys.executable, str(script), "--repo", str(self.root), "claim", "--decision", "absent"], capture_output=True)
        self.assertEqual(p.returncode, 2)


if __name__ == "__main__":
    unittest.main()
