#!/usr/bin/env python3
"""Unit tests for shared review modules."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import review_core
from review_rules import ExternalToolSpec, detect_language
from review_types import Finding, ReviewResult, ReviewedFile, ToolRun, severity_meets_threshold


class ReviewRuleUnitTests(unittest.TestCase):
    def test_detect_language_extensions(self) -> None:
        self.assertEqual(detect_language("example.ts"), "typescript")
        self.assertEqual(detect_language("example.js"), "javascript")
        self.assertEqual(detect_language("example.py"), "python")
        self.assertEqual(detect_language("example.go"), "go")
        self.assertEqual(detect_language("example.swift"), "swift")
        self.assertEqual(detect_language("example.kt"), "kotlin")
        self.assertIsNone(detect_language("README.md"))

    def test_severity_threshold_mapping(self) -> None:
        self.assertTrue(severity_meets_threshold("critical", "high"))
        self.assertTrue(severity_meets_threshold("high", "high"))
        self.assertFalse(severity_meets_threshold("medium", "high"))
        self.assertFalse(severity_meets_threshold("low", "none"))

    def test_finding_normalization_schema(self) -> None:
        finding = Finding(
            id="CR-TEST-001",
            title="Test",
            severity="MEDIUM",
            category="unknown",
            language="unknown",
            path="",
            line=0,
            confidence=2.0,
            source="",
            evidence="evidence",
            recommendation="fix",
        )
        payload = finding.to_dict()
        expected_keys = {
            "id",
            "title",
            "severity",
            "category",
            "language",
            "path",
            "line",
            "confidence",
            "source",
            "evidence",
            "recommendation",
        }
        self.assertEqual(set(payload.keys()), expected_keys)
        self.assertEqual(payload["severity"], "medium")
        self.assertEqual(payload["category"], "maintainability")
        self.assertEqual(payload["language"], "generic")
        self.assertEqual(payload["path"], ".")
        self.assertEqual(payload["line"], 1)

    def test_missing_tool_warning(self) -> None:
        original = review_core.get_external_tool_specs

        def fake_specs(_target, _languages):
            return [
                ExternalToolSpec(
                    tool="fake-lint",
                    command=["definitely-not-installed-tool", "--json"],
                    parser="fake",
                    cwd=None,
                )
            ]

        review_core.get_external_tool_specs = fake_specs
        try:
            tooling, findings = review_core.run_external_tools(Path.cwd(), {"python"}, verbose=False)
        finally:
            review_core.get_external_tool_specs = original

        self.assertEqual(findings, [])
        self.assertEqual(len(tooling), 1)
        self.assertEqual(tooling[0].tool, "fake-lint")
        self.assertEqual(tooling[0].status, "missing")

    def test_markdown_is_deterministic(self) -> None:
        result = ReviewResult(
            meta={"tool": "unit", "version": "1", "generated_at": "2025-01-01T00:00:00+00:00"},
            target={"path": ".", "mode": "test"},
            files=[
                ReviewedFile(path="b.py", language="python", change="modified"),
                ReviewedFile(path="a.py", language="python", change="modified"),
            ],
            tooling=[
                ToolRun(tool="zeta", status="ok", notes="z"),
                ToolRun(tool="alpha", status="ok", notes="a"),
            ],
            findings=[
                Finding(
                    id="LOW-1",
                    title="Low",
                    severity="low",
                    category="style",
                    language="python",
                    path="b.py",
                    line=2,
                    confidence=0.5,
                    source="builtin",
                    evidence="",
                    recommendation="",
                ),
                Finding(
                    id="HIGH-1",
                    title="High",
                    severity="high",
                    category="security",
                    language="python",
                    path="a.py",
                    line=1,
                    confidence=0.9,
                    source="builtin",
                    evidence="",
                    recommendation="",
                ),
            ],
        ).normalize("high")

        markdown = review_core.render_markdown(result, "Unit Report")
        first_high = markdown.find("HIGH-1")
        first_low = markdown.find("LOW-1")
        self.assertGreater(first_high, 0)
        self.assertGreater(first_low, 0)
        self.assertLess(first_high, first_low)

        parsed = json.loads(json.dumps(result.to_dict()))
        self.assertIn("summary", parsed)


if __name__ == "__main__":
    unittest.main()
