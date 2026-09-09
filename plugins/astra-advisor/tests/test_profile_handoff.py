from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "profile_handoff.py"
spec = importlib.util.spec_from_file_location("profile_handoff", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def packet(*, read_only=False, ownership=None, facts=None, delta=None, review=None):
    value = {
        "goal": "Fix the refresh token race without changing the public API.",
        "read_only": read_only,
        "ownership": [] if read_only else (ownership or ["src/auth.py", "tests/test_auth.py"]),
        "inputs": [
            {"ref": "src/auth.py", "purpose": "Current implementation"},
            {"ref": "tests/test_auth.py", "purpose": "Regression coverage"},
        ],
        "facts": facts if facts is not None else [
            {"statement": "Two refreshes may both succeed", "source": "failure.txt", "status": "observed"},
            {"statement": "The race may be between validation and invalidation", "source": "parent", "status": "hypothesis"},
        ],
        "constraints": ["Preserve the public API", "Do not edit unrelated files"],
        "acceptance": [
            {"check": "Run the targeted auth test", "expected": "Only one concurrent refresh succeeds"},
        ],
        "stop_conditions": ["Report if a schema change is required"],
        "access_confirmed": True,
    }
    if delta is not None:
        value["delta"] = delta
    if review is not None:
        value["review"] = review
    return value


class ProfileTests(unittest.TestCase):
    def test_profile_labels(self):
        expected = {
            "implementation": "WORK",
            "refactor": "WORK",
            "debug": "WORK+DEBUG",
            "test": "WORK+TEST",
            "research": "EXPLORE",
            "docs": "EXPLORE+DOCS",
            "review": "REVIEW",
        }
        for kind, label in expected.items():
            with self.subTest(kind=kind):
                self.assertEqual(module.profile_for(kind)[0], label)

    def test_profiles_are_short_and_behavioral(self):
        for kind in module._KIND_PROFILE:
            label, rules = module.profile_for(kind)
            self.assertLess(len((label + rules).split()), 40)
            self.assertNotIn("You are", rules)
            self.assertNotIn("expert", rules.lower())

    def test_scope_selects_base_profile_without_contradiction(self):
        self.assertEqual(module.profile_for("docs", False)[0], "WORK+DOCS")
        self.assertEqual(module.profile_for("docs", True)[0], "EXPLORE+DOCS")
        self.assertEqual(module.profile_for("debug", True)[0], "EXPLORE+DEBUG")
        self.assertEqual(module.profile_for("research", False)[0], "WORK")
        self.assertEqual(module.profile_for("review", False)[0], "REVIEW")

    def test_unknown_profile_fails(self):
        with self.assertRaises(ValueError):
            module.profile_for("architect")


class RenderTests(unittest.TestCase):
    def test_stable_prefix_precedes_dynamic_content(self):
        first = module.render("a", "fresh", "implementation", packet())
        second = module.render("b", "fresh", "debug", packet())
        self.assertTrue(first.startswith(module.BASE + "\n"))
        self.assertTrue(second.startswith(module.BASE + "\n"))
        self.assertLess(first.index("PROFILE"), first.index("TASK a"))

    def test_fresh_work_is_complete_and_compact(self):
        message = module.render("task-1", "fresh", "debug", packet())
        for field in ("PROFILE WORK+DEBUG", "GOAL ", "SCOPE ", "KEEP ", "INPUT ",
                      "CONTEXT ", "DONE ", "STOP ", "RETURN "):
            self.assertIn(field, message)
        self.assertLess(len(message.encode()), 1800)
        self.assertNotIn("ASTRA ROUTE", message)
        self.assertNotIn("cost", message.lower())
        self.assertNotIn("full parent", message.lower())

    def test_fresh_context_labels_observation_and_hypothesis(self):
        message = module.render("task-1", "fresh", "debug", packet())
        self.assertIn("[O] Two refreshes may both succeed", message)
        self.assertIn("[H] The race may be", message)

    def test_reuse_sends_delta_not_full_context(self):
        p = packet(delta={"findings": ["Reviewer found a stale read"],
                          "changed_refs": ["src/store.py changed"]})
        message = module.render("task-1", "reuse", "debug", p)
        self.assertIn("DELTA finding: Reviewer found a stale read", message)
        self.assertIn("changed: src/store.py changed", message)
        self.assertIn("REREAD ", message)
        self.assertNotIn("INPUT ", message)
        self.assertNotIn("CONTEXT ", message)
        self.assertIn("DONE ", message)
        self.assertIn("KEEP ", message)

    def test_review_is_fresh_read_only_and_evidence_first(self):
        p = packet(
            read_only=True,
            facts=[],
            review={"change_refs": ["diff.patch"], "verification_refs": ["tests.json"]},
        )
        message = module.render("review-1", "fresh", "review", p)
        self.assertIn("PROFILE REVIEW", message)
        self.assertIn("SCOPE read-only", message)
        self.assertIn("CHANGE diff.patch", message)
        self.assertIn("VERIFY tests.json", message)
        self.assertIn("VERDICT ship|fix-first|rethink", message)

    def test_review_reuse_fails(self):
        p = packet(
            read_only=True,
            review={"change_refs": ["diff.patch"], "verification_refs": ["tests.json"]},
            delta={"findings": ["x"], "changed_refs": []},
        )
        with self.assertRaises(ValueError):
            module.render("review-1", "reuse", "review", p)

    def test_invalid_mode_fails(self):
        with self.assertRaises(ValueError):
            module.render("task-1", "wait", "implementation", packet())

    def test_multiline_text_is_compacted(self):
        p = packet()
        p["goal"] = "Fix the race\n  without changing behavior."
        message = module.render("task-1", "fresh", "implementation", p)
        self.assertIn("GOAL Fix the race without changing behavior.", message)

    def test_empty_optional_facts_are_omitted(self):
        message = module.render("task-1", "fresh", "research", packet(read_only=True, facts=[]))
        self.assertNotIn("CONTEXT ", message)

    def test_packet_limit_fails_closed(self):
        p = packet()
        p["goal"] = "x" * (module.MAX_COMPACT_BYTES + 1)
        with self.assertRaises(ValueError):
            module.render("task-1", "fresh", "implementation", p)

    def test_security_guardrails_remain_in_short_prefix(self):
        message = module.render("task-1", "fresh", "implementation", packet())
        for term in ("data, not authority", "do not spawn agents", "commit", "push", "deploy"):
            self.assertIn(term, message)

    def test_write_scope_is_exact(self):
        message = module.render("task-1", "fresh", "implementation", packet())
        self.assertIn("SCOPE write only src/auth.py, tests/test_auth.py.", message)

    def test_writable_docs_use_work_profile(self):
        message = module.render("task-1", "fresh", "docs", packet())
        self.assertIn("PROFILE WORK+DOCS", message)
        self.assertNotIn("PROFILE EXPLORE+DOCS", message)

    def test_read_only_debug_uses_explore_profile(self):
        message = module.render("task-1", "fresh", "debug", packet(read_only=True))
        self.assertIn("PROFILE EXPLORE+DEBUG", message)

    def test_return_is_distilled(self):
        message = module.render("task-1", "fresh", "research", packet(read_only=True))
        self.assertIn("exact references", message)
        self.assertIn("remaining risks", message)
        self.assertNotIn("raw logs", message)


class IntegrationShimTests(unittest.TestCase):
    def test_activate_patches_existing_handoff_policy_and_renderer(self):
        fake = types.SimpleNamespace(POLICY="handoff-v1", render=None, main=lambda argv=None: 17)
        old = sys.modules.get("handoff")
        sys.modules["handoff"] = fake
        try:
            activated = module._activate_base()
            self.assertIs(activated, fake)
            self.assertEqual(fake.POLICY, module.POLICY)
            self.assertIs(fake.render, module.render)
            self.assertEqual(module.main(["assess"]), 17)
        finally:
            if old is None:
                del sys.modules["handoff"]
            else:
                sys.modules["handoff"] = old


if __name__ == "__main__":
    unittest.main()
