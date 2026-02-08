#!/usr/bin/env python3
"""Shared runtime helpers for code-review scripts."""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from review_rules import (
    ExternalToolSpec,
    detect_language,
    get_external_tool_specs,
    parse_external_findings,
)
from review_types import Finding, ReviewResult, ReviewedFile, ToolRun

EXIT_OK = 0
EXIT_THRESHOLD_FAILED = 1
EXIT_INVALID_ARGS = 2
EXIT_RUNTIME_ERROR = 3

DEFAULT_EXCLUDE_GLOBS = [
    ".git/**",
    "node_modules/**",
    "vendor/**",
    "dist/**",
    "build/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    "*.min.js",
]


def utc_now_iso() -> str:
    """Return current timestamp in UTC ISO-8601."""
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def add_shared_cli_options(parser: argparse.ArgumentParser) -> None:
    """Attach common options expected across review scripts."""
    parser.add_argument(
        "--format",
        choices=("markdown", "json", "both"),
        default="both",
        help="Output format to emit (default: both)",
    )
    parser.add_argument(
        "--output-dir",
        default="code-review-out",
        help="Directory for report artifacts (default: ./code-review-out)",
    )
    parser.add_argument(
        "--fail-on",
        choices=("none", "low", "medium", "high", "critical"),
        default="high",
        help="Exit non-zero when findings at or above this severity exist.",
    )
    parser.add_argument(
        "--languages",
        default=None,
        help="Optional language filter list (e.g. ts,js,py,swift,kotlin,go)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude glob pattern (repeatable)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose diagnostic output",
    )


def to_reviewed_files(paths: Iterable[Path], root: Path, change: str = "existing") -> List[ReviewedFile]:
    """Convert filesystem paths to ReviewedFile records."""
    reviewed = []
    for path in paths:
        language = detect_language(str(path))
        if not language:
            continue
        rel_path = str(path.relative_to(root)).replace("\\", "/")
        reviewed.append(ReviewedFile(path=rel_path, language=language, change=change))
    return reviewed


def run_command(
    cmd: Sequence[str],
    cwd: Optional[Path] = None,
    timeout_seconds: int = 120,
) -> subprocess.CompletedProcess:
    """Run subprocess command with text output."""
    return subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def command_exists(name: str) -> bool:
    """Return True when command is available on PATH."""
    return shutil.which(name) is not None


def resolve_repo_root(target_path: Path) -> Optional[Path]:
    """Resolve git repo root for a path."""
    probe = run_command(["git", "-C", str(target_path), "rev-parse", "--show-toplevel"])
    if probe.returncode != 0:
        return None
    output = probe.stdout.strip()
    if not output:
        return None
    return Path(output)


def detect_default_branch_ref(repo_root: Path) -> str:
    """Best-effort default remote branch reference."""
    symbolic = run_command(["git", "-C", str(repo_root), "symbolic-ref", "refs/remotes/origin/HEAD"])
    if symbolic.returncode == 0:
        ref = symbolic.stdout.strip()
        if ref:
            return ref

    for candidate in ("origin/main", "origin/master", "main", "master"):
        probe = run_command(["git", "-C", str(repo_root), "rev-parse", "--verify", candidate])
        if probe.returncode == 0:
            return candidate

    return "HEAD~1"


def compute_default_base(repo_root: Path, head_ref: str) -> str:
    """Compute merge-base default for PR comparison."""
    default_ref = detect_default_branch_ref(repo_root)
    merge_base = run_command(
        ["git", "-C", str(repo_root), "merge-base", default_ref, head_ref],
    )
    if merge_base.returncode == 0:
        value = merge_base.stdout.strip()
        if value:
            return value
    return default_ref


def parse_name_status_line(line: str) -> Optional[Tuple[str, str]]:
    """Parse `git diff --name-status` output line."""
    line = line.rstrip("\n")
    if not line:
        return None

    parts = line.split("\t")
    status = parts[0]
    code = status[0]

    if code == "R" and len(parts) >= 3:
        path = parts[2]
    elif len(parts) >= 2:
        path = parts[1]
    else:
        return None

    change_map = {
        "A": "added",
        "M": "modified",
        "D": "deleted",
        "R": "renamed",
        "C": "copied",
        "T": "modified",
        "U": "modified",
    }
    change = change_map.get(code, "modified")
    return path.replace("\\", "/"), change


def collect_local_diff_files(
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    max_files: int,
) -> List[ReviewedFile]:
    """Collect changed files from local git diff."""
    diff = run_command(
        [
            "git",
            "-C",
            str(repo_root),
            "diff",
            "--name-status",
            "{}...{}".format(base_ref, head_ref),
        ]
    )
    if diff.returncode != 0:
        raise RuntimeError(diff.stderr.strip() or "Unable to read git diff")

    reviewed: List[ReviewedFile] = []
    for raw_line in diff.stdout.splitlines():
        parsed = parse_name_status_line(raw_line)
        if not parsed:
            continue
        path, change = parsed
        language = detect_language(path)
        if not language:
            continue
        reviewed.append(ReviewedFile(path=path, language=language, change=change))
        if len(reviewed) >= max_files:
            break
    return reviewed


def collect_repo_files(target_path: Path) -> List[Path]:
    """Collect all supported language files under target path."""
    if target_path.is_file():
        language = detect_language(str(target_path))
        return [target_path] if language else []

    files: List[Path] = []
    for candidate in target_path.rglob("*"):
        if not candidate.is_file():
            continue
        if detect_language(str(candidate)):
            files.append(candidate)
    return files


def expand_exclude_patterns(extra_patterns: Iterable[str]) -> List[str]:
    """Merge default and custom exclude patterns."""
    merged = list(DEFAULT_EXCLUDE_GLOBS)
    for item in extra_patterns:
        value = item.strip()
        if value:
            merged.append(value)
    deduped = []
    seen = set()
    for value in merged:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def path_matches_excludes(rel_path: str, exclude_patterns: Sequence[str]) -> bool:
    """Check if a relative path matches any exclusion pattern."""
    rel_path = rel_path.replace("\\", "/")
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        if pattern.endswith("/**") and rel_path.startswith(pattern[:-3]):
            return True
    return False


def read_text_file(path: Path) -> Optional[str]:
    """Read UTF-8 text content, returning None for binary/unreadable files."""
    try:
        data = path.read_bytes()
    except Exception:
        return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("latin-1")
        except Exception:
            return None


def analyze_reviewed_files(
    target_root: Path,
    reviewed_files: Sequence[ReviewedFile],
    allowed_languages: Optional[Set[str]],
    exclude_patterns: Sequence[str],
    verbose: bool = False,
) -> Tuple[List[ReviewedFile], List[Finding], Set[str], List[ToolRun]]:
    """Run built-in checks across selected files."""
    from review_rules import run_builtin_checks

    scanned_files: List[ReviewedFile] = []
    findings: List[Finding] = []
    tooling: List[ToolRun] = []
    languages: Set[str] = set()

    for reviewed_file in reviewed_files:
        if allowed_languages and reviewed_file.language not in allowed_languages:
            continue
        if path_matches_excludes(reviewed_file.path, exclude_patterns):
            continue

        abs_path = target_root / reviewed_file.path
        if reviewed_file.change == "deleted":
            continue
        if not abs_path.exists() or not abs_path.is_file():
            tooling.append(
                ToolRun(
                    tool="filesystem",
                    status="error",
                    notes="File not found during analysis: {}".format(reviewed_file.path),
                )
            )
            continue

        text = read_text_file(abs_path)
        if text is None:
            tooling.append(
                ToolRun(
                    tool="filesystem",
                    status="ok",
                    notes="Skipped non-text file: {}".format(reviewed_file.path),
                )
            )
            continue

        if verbose:
            print("[analyze] {} ({})".format(reviewed_file.path, reviewed_file.language))

        scanned_files.append(reviewed_file)
        languages.add(reviewed_file.language)
        findings.extend(run_builtin_checks(reviewed_file.path, reviewed_file.language, text))

    return scanned_files, findings, languages, tooling


def _format_tool_status(spec: ExternalToolSpec, returncode: int, finding_count: int, fallback: str) -> str:
    details = "rc={} findings={}".format(returncode, finding_count)
    if fallback:
        details = "{} ({})".format(details, fallback)
    return details


def run_external_tools(
    target_root: Path,
    languages: Set[str],
    verbose: bool = False,
) -> Tuple[List[ToolRun], List[Finding]]:
    """Run optional external tool adapters and parse findings."""
    tooling: List[ToolRun] = []
    findings: List[Finding] = []

    if not languages:
        return tooling, findings

    specs = get_external_tool_specs(target_root, languages)
    for spec in specs:
        cmd = list(spec.command)
        fallback = ""

        if not command_exists(cmd[0]):
            if spec.tool == "eslint" and command_exists("npx"):
                cmd = ["npx", "eslint"] + cmd[1:]
                fallback = "used npx fallback"
            else:
                tooling.append(
                    ToolRun(
                        tool=spec.tool,
                        status="missing",
                        notes="Command '{}' not found on PATH".format(spec.command[0]),
                    )
                )
                continue

        if verbose:
            print("[tool] {}".format(" ".join(cmd)))

        try:
            completed = run_command(cmd, cwd=spec.cwd, timeout_seconds=150)
        except subprocess.TimeoutExpired:
            tooling.append(
                ToolRun(
                    tool=spec.tool,
                    status="error",
                    notes="Timed out after 150s",
                )
            )
            continue
        except Exception as exc:
            tooling.append(ToolRun(tool=spec.tool, status="error", notes=str(exc)))
            continue

        parsed_findings = parse_external_findings(spec.parser, completed.stdout, completed.stderr, target_root)
        findings.extend(parsed_findings)

        acceptable = completed.returncode in {0, 1}
        status = "ok" if acceptable else "error"
        notes = _format_tool_status(spec, completed.returncode, len(parsed_findings), fallback)

        if completed.stderr.strip() and status == "error":
            notes = "{} stderr={}".format(notes, completed.stderr.strip()[:300])

        tooling.append(ToolRun(tool=spec.tool, status=status, notes=notes))

    return tooling, findings


def gh_authenticated(cwd: Path) -> bool:
    """Return True when gh auth status is healthy."""
    if not command_exists("gh"):
        return False
    result = run_command(["gh", "auth", "status"], cwd=cwd)
    return result.returncode == 0


def parse_pr_number(value: str) -> str:
    """Extract PR number from plain value or URL."""
    value = value.strip()
    if value.isdigit():
        return value
    # Typical URLs: .../pull/123
    segments = [segment for segment in value.split("/") if segment]
    for index, segment in enumerate(segments):
        if segment == "pull" and index + 1 < len(segments) and segments[index + 1].isdigit():
            return segments[index + 1]
    return value


def collect_github_pr_files(repo_root: Path, pr_value: str, max_files: int) -> Tuple[str, str, List[ReviewedFile], str]:
    """Collect changed files from GitHub PR metadata."""
    pr_number = parse_pr_number(pr_value)
    result = run_command(
        [
            "gh",
            "pr",
            "view",
            pr_number,
            "--json",
            "baseRefName,headRefName,files,number,url",
        ],
        cwd=repo_root,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Unable to fetch PR metadata")

    payload = json.loads(result.stdout)
    base_ref = str(payload.get("baseRefName") or "origin/main")
    head_ref = str(payload.get("headRefName") or "HEAD")
    pr_url = str(payload.get("url") or "")

    reviewed: List[ReviewedFile] = []
    for file_entry in payload.get("files", []):
        if not isinstance(file_entry, dict):
            continue
        path = str(file_entry.get("path", ""))
        language = detect_language(path)
        if not language:
            continue
        reviewed.append(ReviewedFile(path=path, language=language, change="modified"))
        if len(reviewed) >= max_files:
            break

    return base_ref, head_ref, reviewed, pr_url


def build_review_result(
    tool_name: str,
    target_path: Path,
    mode: str,
    files: List[ReviewedFile],
    tooling: List[ToolRun],
    findings: List[Finding],
    fail_on: str,
    extra_target: Optional[Dict[str, str]] = None,
) -> ReviewResult:
    """Build canonical review result with summary and deterministic ordering."""
    target_payload: Dict[str, str] = {
        "path": str(target_path),
        "mode": mode,
    }
    if extra_target:
        target_payload.update(extra_target)

    result = ReviewResult(
        meta={
            "tool": tool_name,
            "version": "1.0.0",
            "generated_at": utc_now_iso(),
        },
        target=target_payload,
        files=files,
        tooling=tooling,
        findings=findings,
    )
    result.normalize(fail_on)
    return result


def render_markdown(result: ReviewResult, title: str) -> str:
    """Render deterministic markdown from review result."""
    payload = result.to_dict()
    summary = payload["summary"]
    counts = summary["counts"]

    lines: List[str] = []
    lines.append("# {}".format(title))
    lines.append("")
    lines.append("Generated: `{}`".format(payload["meta"].get("generated_at", "")))
    lines.append("Tool: `{}`".format(payload["meta"].get("tool", "")))
    lines.append("Target: `{}` (mode: `{}`)".format(payload["target"].get("path", ""), payload["target"].get("mode", "")))
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("- Threshold: `{}`".format(summary.get("threshold", "high")))
    lines.append("- Failed: `{}`".format(summary.get("failed", False)))
    lines.append("- Exit code: `{}`".format(summary.get("exit_code", 0)))
    lines.append("- Critical: `{}`".format(counts.get("critical", 0)))
    lines.append("- High: `{}`".format(counts.get("high", 0)))
    lines.append("- Medium: `{}`".format(counts.get("medium", 0)))
    lines.append("- Low: `{}`".format(counts.get("low", 0)))

    lines.append("")
    lines.append("## Tooling")
    lines.append("")
    lines.append("| Tool | Status | Notes |")
    lines.append("| --- | --- | --- |")
    if payload["tooling"]:
        for tool_run in payload["tooling"]:
            lines.append(
                "| {} | {} | {} |".format(
                    tool_run["tool"],
                    tool_run["status"],
                    tool_run["notes"].replace("|", "\\|"),
                )
            )
    else:
        lines.append("| n/a | ok | No external tooling executed |")

    lines.append("")
    lines.append("## Findings")
    lines.append("")

    grouped: Dict[str, List[Dict[str, object]]] = {
        "critical": [],
        "high": [],
        "medium": [],
        "low": [],
    }
    for finding in payload["findings"]:
        grouped[str(finding["severity"])].append(finding)

    for severity in ("critical", "high", "medium", "low"):
        severity_items = grouped[severity]
        lines.append("### {} ({})".format(severity.capitalize(), len(severity_items)))
        lines.append("")
        if not severity_items:
            lines.append("No findings.")
            lines.append("")
            continue

        lines.append("| ID | Category | Language | Location | Title | Recommendation |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for finding in severity_items:
            location = "{}:{}".format(finding["path"], finding["line"])
            lines.append(
                "| {} | {} | {} | {} | {} | {} |".format(
                    finding["id"],
                    finding["category"],
                    finding["language"],
                    location,
                    str(finding["title"]).replace("|", "\\|"),
                    str(finding["recommendation"]).replace("|", "\\|"),
                )
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_review_outputs(
    result: ReviewResult,
    output_dir: Path,
    base_name: str,
    output_format: str,
    markdown_title: str,
) -> Dict[str, Path]:
    """Write review output files and return generated paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: Dict[str, Path] = {}

    if output_format in {"json", "both"}:
        json_path = output_dir / "{}.json".format(base_name)
        json_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        generated["json"] = json_path

    if output_format in {"markdown", "both"}:
        markdown_path = output_dir / "{}.md".format(base_name)
        markdown_path.write_text(render_markdown(result, markdown_title), encoding="utf-8")
        generated["markdown"] = markdown_path

    return generated


def files_from_payload(payload: Dict[str, object]) -> List[ReviewedFile]:
    """Parse reviewed files from result payload."""
    files_payload = payload.get("files", [])
    if not isinstance(files_payload, list):
        return []
    reviewed = []
    for item in files_payload:
        if not isinstance(item, dict):
            continue
        reviewed.append(
            ReviewedFile(
                path=str(item.get("path", "")),
                language=str(item.get("language", "generic")),
                change=str(item.get("change", "modified")),
            )
        )
    return reviewed


def parse_languages_from_files(files: Iterable[ReviewedFile]) -> Set[str]:
    """Return language set from reviewed files."""
    return {item.language for item in files if item.language}


def sanitize_reviewed_files(
    reviewed_files: Sequence[ReviewedFile],
    allowed_languages: Optional[Set[str]],
    exclude_patterns: Sequence[str],
) -> List[ReviewedFile]:
    """Filter reviewed files by language and exclude rules."""
    sanitized: List[ReviewedFile] = []
    for reviewed_file in reviewed_files:
        if allowed_languages and reviewed_file.language not in allowed_languages:
            continue
        if path_matches_excludes(reviewed_file.path, exclude_patterns):
            continue
        sanitized.append(reviewed_file)
    return sanitized
