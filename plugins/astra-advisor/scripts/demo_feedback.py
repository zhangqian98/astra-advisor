#!/usr/bin/env python3
"""Small end-to-end demonstration of the local feedback loop.

Creates a temporary Git repository, plans one bounded task, records a synthetic
capability failure, then shows that the next exactly matching task is routed more
conservatively. This is a mechanics demo, not a quality benchmark.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile

from routing_memory import Advisor, EFFORTS, MODELS


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        git(root, "init", "-q")
        git(root, "config", "user.name", "Synthetic demo")
        git(root, "config", "user.email", "demo@example.invalid")
        (root / "app.py").write_text("answer = 42\n", encoding="utf-8")
        git(root, "add", "app.py")
        git(root, "commit", "-qm", "fixture")

        with Advisor(root) as advisor:
            (advisor.evidence_dir / "runtime.json").write_text('{"demo":true}', encoding="utf-8")
            (advisor.evidence_dir / "failure.txt").write_text("synthetic capability failure\n", encoding="utf-8")
            runtime = {
                "epoch": "demo-runtime",
                "models": {m: list(EFFORTS) for m in MODELS},
                "controls": ["model", "reasoning_effort", "fork_turns:none"],
                "evidence": ["runtime.json"],
            }
            task = {
                "task_id": "demo-1",
                "kind": "implementation",
                "domain": "general",
                "risk": {"judgment": 0, "context": 0, "blast_radius": 0, "spec_gap": 0, "uncertainty": 0},
                "critical_flags": [],
                "bounded": True,
                "independent": True,
                "pattern": "demo-pattern",
                "scope": "demo-module",
            }
            first = advisor.plan(task, runtime)
            advisor.feedback({
                "event_id": "demo-event-1",
                "route_id": first["id"],
                "agent_id": "demo-agent",
                "status": "fail",
                "cause": "capability",
                "attribution_confirmed": True,
                "observed_model": first["model"],
                "observed_effort": first["effort"],
                "runtime_evidence": ["runtime.json"],
                "evidence": ["failure.txt"],
                "diagnostics": {"spec_reviewed": True, "context_sufficient": True, "environment_healthy": True},
            })
            second_task = dict(task, task_id="demo-2")
            second = advisor.plan(second_task, runtime)
            print(json.dumps({"first": first, "second": second, "report": advisor.report()}, indent=2))


if __name__ == "__main__":
    main()
