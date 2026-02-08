#!/usr/bin/env python3
"""Integration tests for analyzer/report CLI workflows."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PR_ANALYZER = ROOT / "pr_analyzer.py"
QUALITY_CHECKER = ROOT / "code_quality_checker.py"
REPORT_GENERATOR = ROOT / "review_report_generator.py"


def run_script(script: Path, args, cwd: Path):
    return subprocess.run(
        [sys.executable, str(script)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(path), check=True)


def git_commit_all(path: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=str(path), check=True, capture_output=True)


class IntegrationFlowTests(unittest.TestCase):
    def test_local_pr_analysis_and_security_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            init_git_repo(repo)

            (repo / "safe.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
            git_commit_all(repo, "base")

            (repo / "safe.py").write_text(
                "import subprocess\n\ndef run(cmd):\n    subprocess.run(cmd, shell=True)\n",
                encoding="utf-8",
            )
            git_commit_all(repo, "head")

            result = run_script(
                PR_ANALYZER,
                [
                    str(repo),
                    "--mode",
                    "local",
                    "--base",
                    "HEAD~1",
                    "--head",
                    "HEAD",
                    "--output-dir",
                    "out",
                    "--format",
                    "both",
                ],
                cwd=repo,
            )

            self.assertIn(result.returncode, {0, 1})
            output_json = repo / "out" / "pr_analysis.json"
            self.assertTrue(output_json.exists())

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            finding_ids = {item["id"] for item in payload["findings"]}
            self.assertIn("CR-PY-002", finding_ids)

    def test_github_mode_fallback_when_auth_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            init_git_repo(repo)
            (repo / "a.py").write_text("def x():\n    return 1\n", encoding="utf-8")
            git_commit_all(repo, "base")
            (repo / "a.py").write_text("def x():\n    print('debug')\n    return 1\n", encoding="utf-8")
            git_commit_all(repo, "head")

            result = run_script(
                PR_ANALYZER,
                [
                    str(repo),
                    "--mode",
                    "github",
                    "--pr",
                    "1",
                    "--base",
                    "HEAD~1",
                    "--head",
                    "HEAD",
                    "--output-dir",
                    "out",
                    "--format",
                    "json",
                    "--fail-on",
                    "none",
                ],
                cwd=repo,
            )

            self.assertEqual(result.returncode, 0)
            payload = json.loads((repo / "out" / "pr_analysis.json").read_text(encoding="utf-8"))
            gh_entries = [item for item in payload["tooling"] if item["tool"] == "gh"]
            self.assertTrue(gh_entries)
            self.assertEqual(payload["target"]["mode"], "local")

    def test_code_quality_and_report_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            init_git_repo(repo)

            (repo / "main.py").write_text(
                "import os\nPASSWORD = 'secret123456'\n\ndef run(user):\n    os.system('echo ' + user)\n",
                encoding="utf-8",
            )
            git_commit_all(repo, "init")

            quality_run = run_script(
                QUALITY_CHECKER,
                [str(repo), "--output-dir", "out", "--format", "json", "--fail-on", "none"],
                cwd=repo,
            )
            self.assertEqual(quality_run.returncode, 0)

            quality_json = repo / "out" / "code_quality.json"
            self.assertTrue(quality_json.exists())
            quality_payload = json.loads(quality_json.read_text(encoding="utf-8"))
            ids = {item["id"] for item in quality_payload["findings"]}
            self.assertIn("CR-SEC-001", ids)
            self.assertIn("CR-SEC-002", ids)

            pr_copy = repo / "out" / "pr_analysis.json"
            pr_copy.write_text(quality_json.read_text(encoding="utf-8"), encoding="utf-8")

            report_run = run_script(
                REPORT_GENERATOR,
                [
                    "--inputs",
                    str(quality_json),
                    str(pr_copy),
                    "--output-dir",
                    "out",
                    "--format",
                    "both",
                    "--fail-on",
                    "none",
                ],
                cwd=repo,
            )
            self.assertEqual(report_run.returncode, 0)

            report_json = repo / "out" / "review_report.json"
            report_md = repo / "out" / "review_report.md"
            self.assertTrue(report_json.exists())
            self.assertTrue(report_md.exists())

            report_payload = json.loads(report_json.read_text(encoding="utf-8"))
            self.assertEqual(len(report_payload["inputs"]), 2)
            self.assertGreaterEqual(len(report_payload["findings"]), 2)


if __name__ == "__main__":
    unittest.main()
