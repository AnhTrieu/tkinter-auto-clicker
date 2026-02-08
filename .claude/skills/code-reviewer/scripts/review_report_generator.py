#!/usr/bin/env python3
"""Aggregate analyzer outputs into a comprehensive review report."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from review_core import (
    EXIT_INVALID_ARGS,
    EXIT_RUNTIME_ERROR,
    add_shared_cli_options,
    build_review_result,
    expand_exclude_patterns,
    path_matches_excludes,
)
from review_rules import parse_language_filter
from review_types import Finding, ReviewResult, ReviewedFile, ToolRun

CATEGORIES = ["correctness", "security", "maintainability", "performance", "style"]
SEVERITY_ORDER = ["critical", "high", "medium", "low"]


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser for report generator."""
    parser = argparse.ArgumentParser(description="Aggregate code review analyzer outputs.")
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input JSON reports from pr_analyzer.py and/or code_quality_checker.py",
    )
    add_shared_cli_options(parser)
    return parser


def _load_input(path: Path) -> ReviewResult:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Input payload must be a JSON object: {}".format(path))
    return ReviewResult.from_dict(payload)


def _filter_items(
    files: Iterable[ReviewedFile],
    findings: Iterable[Finding],
    allowed_languages: Optional[Set[str]],
    excludes: List[str],
) -> Tuple[List[ReviewedFile], List[Finding]]:
    filtered_files: List[ReviewedFile] = []
    filtered_findings: List[Finding] = []

    for item in files:
        if allowed_languages and item.language not in allowed_languages:
            continue
        if path_matches_excludes(item.path, excludes):
            continue
        filtered_files.append(item)

    for finding in findings:
        normalized = finding.normalized()
        if allowed_languages and normalized.language not in allowed_languages and normalized.language != "generic":
            continue
        if path_matches_excludes(normalized.path, excludes):
            continue
        filtered_findings.append(normalized)

    return filtered_files, filtered_findings


def _build_checklist_matrix(files: Iterable[ReviewedFile], findings: Iterable[Finding]) -> Dict[str, Dict[str, Dict[str, object]]]:
    matrix: Dict[str, Dict[str, Dict[str, object]]] = {}
    languages = sorted({file.language for file in files if file.language != "generic"})
    if not languages:
        languages = sorted({finding.language for finding in findings if finding.language != "generic"})

    by_language_category: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for finding in findings:
        language = finding.language if finding.language != "generic" else "generic"
        category = finding.category
        by_language_category[language][category] += 1

    for language in languages:
        matrix[language] = {}
        for category in CATEGORIES:
            count = by_language_category[language].get(category, 0)
            matrix[language][category] = {
                "status": "pass" if count == 0 else "attention",
                "findings": count,
            }

    return matrix


def _build_antipattern_index(findings: Iterable[Finding]) -> List[Dict[str, object]]:
    grouped: Dict[str, Dict[str, object]] = {}
    for finding in findings:
        key = finding.id
        bucket = grouped.setdefault(
            key,
            {
                "id": finding.id,
                "title": finding.title,
                "severity": finding.severity,
                "count": 0,
                "paths": set(),
                "recommendation": finding.recommendation,
            },
        )
        bucket["count"] = int(bucket["count"]) + 1
        path_entry = "{}:{}".format(finding.path, finding.line)
        cast_paths = bucket["paths"]
        if isinstance(cast_paths, set):
            cast_paths.add(path_entry)

    index = []
    for item in grouped.values():
        paths = sorted(list(item["paths"]))
        index.append(
            {
                "id": item["id"],
                "title": item["title"],
                "severity": item["severity"],
                "count": item["count"],
                "paths": paths[:10],
                "recommendation": item["recommendation"],
            }
        )

    def sort_key(entry: Dict[str, object]) -> Tuple[int, int, str]:
        severity_rank = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 3,
        }.get(str(entry.get("severity", "low")), 4)
        return (severity_rank, -int(entry.get("count", 0)), str(entry.get("id", "")))

    return sorted(index, key=sort_key)


def _build_by_file(findings: Iterable[Finding]) -> List[Dict[str, object]]:
    by_file: Dict[str, Dict[str, object]] = {}
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}

    for finding in findings:
        bucket = by_file.setdefault(
            finding.path,
            {
                "path": finding.path,
                "count": 0,
                "highest_severity": "low",
            },
        )
        bucket["count"] = int(bucket["count"]) + 1
        current = str(bucket["highest_severity"])
        if severity_rank.get(finding.severity, 1) > severity_rank.get(current, 1):
            bucket["highest_severity"] = finding.severity

    return sorted(by_file.values(), key=lambda item: (-int(item["count"]), str(item["path"])))


def _render_report_markdown(
    payload: Dict[str, object],
    checklist: Dict[str, Dict[str, Dict[str, object]]],
    antipattern_index: List[Dict[str, object]],
    by_file: List[Dict[str, object]],
) -> str:
    summary = payload["summary"]
    counts = summary["counts"]
    findings = payload["findings"]
    security_findings = payload["security_findings"]

    lines: List[str] = []
    lines.append("# Review Report")
    lines.append("")
    lines.append("Generated: `{}`".format(payload["meta"]["generated_at"]))
    lines.append("Inputs: `{}`".format(len(payload["inputs"])))
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append("- Threshold: `{}`".format(summary["threshold"]))
    lines.append("- Failed: `{}`".format(summary["failed"]))
    lines.append("- Exit code: `{}`".format(summary["exit_code"]))
    lines.append("- Critical: `{}`".format(counts["critical"]))
    lines.append("- High: `{}`".format(counts["high"]))
    lines.append("- Medium: `{}`".format(counts["medium"]))
    lines.append("- Low: `{}`".format(counts["low"]))
    lines.append("- Total findings: `{}`".format(len(findings)))

    lines.append("")
    lines.append("## Security Findings")
    lines.append("")
    if security_findings:
        lines.append("| Severity | ID | Location | Title | Recommendation |")
        lines.append("| --- | --- | --- | --- | --- |")
        for finding in security_findings:
            location = "{}:{}".format(finding["path"], finding["line"])
            lines.append(
                "| {} | {} | {} | {} | {} |".format(
                    finding["severity"],
                    finding["id"],
                    location,
                    str(finding["title"]).replace("|", "\\|"),
                    str(finding["recommendation"]).replace("|", "\\|"),
                )
            )
    else:
        lines.append("No security findings detected in input reports.")

    lines.append("")
    lines.append("## Findings by Severity")
    lines.append("")
    for severity in SEVERITY_ORDER:
        severity_findings = [item for item in findings if item["severity"] == severity]
        lines.append("### {} ({})".format(severity.capitalize(), len(severity_findings)))
        lines.append("")
        if not severity_findings:
            lines.append("No findings.")
            lines.append("")
            continue
        lines.append("| ID | Category | Language | Location | Title |")
        lines.append("| --- | --- | --- | --- | --- |")
        for finding in severity_findings:
            lines.append(
                "| {} | {} | {} | {}:{} | {} |".format(
                    finding["id"],
                    finding["category"],
                    finding["language"],
                    finding["path"],
                    finding["line"],
                    str(finding["title"]).replace("|", "\\|"),
                )
            )
        lines.append("")

    lines.append("## Best-Practice Checklist Matrix")
    lines.append("")
    if checklist:
        headers = ["Language"] + [category.capitalize() for category in CATEGORIES]
        lines.append("| {} |".format(" | ".join(headers)))
        lines.append("| {} |".format(" | ".join(["---"] * len(headers))))
        for language in sorted(checklist.keys()):
            row = [language]
            for category in CATEGORIES:
                info = checklist[language][category]
                if info["status"] == "pass":
                    row.append("Pass")
                else:
                    row.append("Attention ({})".format(info["findings"]))
            lines.append("| {} |".format(" | ".join(row)))
    else:
        lines.append("No language-specific files found to score.")

    lines.append("")
    lines.append("## Anti-Pattern Index")
    lines.append("")
    if antipattern_index:
        lines.append("| ID | Severity | Count | Title |")
        lines.append("| --- | --- | --- | --- |")
        for item in antipattern_index:
            lines.append(
                "| {} | {} | {} | {} |".format(
                    item["id"],
                    item["severity"],
                    item["count"],
                    str(item["title"]).replace("|", "\\|"),
                )
            )
    else:
        lines.append("No anti-patterns indexed.")

    lines.append("")
    lines.append("## Findings by File")
    lines.append("")
    if by_file:
        lines.append("| File | Findings | Highest Severity |")
        lines.append("| --- | --- | --- |")
        for item in by_file:
            lines.append(
                "| {} | {} | {} |".format(
                    item["path"],
                    item["count"],
                    item["highest_severity"],
                )
            )
    else:
        lines.append("No file-level findings to summarize.")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    """Entrypoint for review report generation."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        allowed_languages = parse_language_filter(args.languages)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID_ARGS

    excludes = expand_exclude_patterns(args.exclude)

    input_paths = [Path(item).resolve() for item in args.inputs]
    for path in input_paths:
        if not path.exists() or not path.is_file():
            print("Input report not found: {}".format(path), file=sys.stderr)
            return EXIT_INVALID_ARGS

    try:
        files: List[ReviewedFile] = []
        findings: List[Finding] = []
        tooling: List[ToolRun] = []

        for input_path in input_paths:
            loaded = _load_input(input_path)
            files.extend(loaded.files)
            findings.extend(loaded.findings)
            tooling.extend(loaded.tooling)

        files, findings = _filter_items(files, findings, allowed_languages, excludes)

        result = build_review_result(
            tool_name="review_report_generator",
            target_path=Path.cwd(),
            mode="aggregate",
            files=files,
            tooling=tooling,
            findings=findings,
            fail_on=args.fail_on,
            extra_target={"input_count": str(len(input_paths))},
        )

        payload = result.to_dict()
        security_findings = [item for item in payload["findings"] if item["category"] == "security"]
        checklist = _build_checklist_matrix(result.files, result.findings)
        antipattern_index = _build_antipattern_index(result.findings)
        by_file = _build_by_file(result.findings)

        report_payload = {
            "meta": payload["meta"],
            "inputs": [str(path) for path in input_paths],
            "target": payload["target"],
            "summary": payload["summary"],
            "findings": payload["findings"],
            "security_findings": security_findings,
            "checklist_matrix": checklist,
            "antipattern_index": antipattern_index,
            "by_file": by_file,
            "tooling": payload["tooling"],
            "files": payload["files"],
        }

        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        outputs = {}
        if args.format in {"json", "both"}:
            json_path = output_dir / "review_report.json"
            json_path.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")
            outputs["json"] = str(json_path)

        if args.format in {"markdown", "both"}:
            md_path = output_dir / "review_report.md"
            md_path.write_text(
                _render_report_markdown(report_payload, checklist, antipattern_index, by_file),
                encoding="utf-8",
            )
            outputs["markdown"] = str(md_path)

        print(json.dumps({"summary": payload["summary"], "outputs": outputs}, indent=2))
        return int(payload["summary"]["exit_code"])

    except Exception as exc:
        print("Unexpected error: {}".format(exc), file=sys.stderr)
        return EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
