#!/usr/bin/env python3
"""Analyze pull request changes with built-in and external quality checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from review_core import (
    EXIT_INVALID_ARGS,
    EXIT_RUNTIME_ERROR,
    add_shared_cli_options,
    analyze_reviewed_files,
    build_review_result,
    collect_github_pr_files,
    collect_local_diff_files,
    compute_default_base,
    expand_exclude_patterns,
    gh_authenticated,
    resolve_repo_root,
    run_external_tools,
    sanitize_reviewed_files,
    write_review_outputs,
)
from review_rules import parse_language_filter
from review_types import ReviewedFile, ToolRun


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser for PR analyzer."""
    parser = argparse.ArgumentParser(description="Analyze pull request changes for quality and security issues.")
    parser.add_argument("target", help="Path inside the git repository to analyze")
    parser.add_argument(
        "--mode",
        choices=("local", "github"),
        default="local",
        help="PR source mode (default: local)",
    )
    parser.add_argument("--base", default=None, help="Base git ref for local diff")
    parser.add_argument("--head", default="HEAD", help="Head git ref for local diff (default: HEAD)")
    parser.add_argument("--pr", default=None, help="PR number or URL for github mode")
    parser.add_argument(
        "--max-files",
        type=int,
        default=300,
        help="Maximum changed files to analyze (default: 300)",
    )
    add_shared_cli_options(parser)
    return parser


def _collect_files(
    repo_root: Path,
    mode: str,
    pr_value: Optional[str],
    base_ref: Optional[str],
    head_ref: str,
    max_files: int,
    verbose: bool,
) -> Dict[str, object]:
    """Collect changed files based on mode and fallback rules."""
    tooling: List[ToolRun] = []
    reviewed_files: List[ReviewedFile] = []
    mode_used = mode
    target_meta: Dict[str, str] = {}

    if mode == "github":
        if not pr_value:
            tooling.append(
                ToolRun(
                    tool="gh",
                    status="error",
                    notes="--mode github requested without --pr; falling back to local mode",
                )
            )
            mode_used = "local"
        elif not gh_authenticated(repo_root):
            tooling.append(
                ToolRun(
                    tool="gh",
                    status="error",
                    notes="gh authentication unavailable; falling back to local mode",
                )
            )
            mode_used = "local"
        else:
            try:
                gh_base, gh_head, gh_files, pr_url = collect_github_pr_files(repo_root, pr_value, max_files)
                reviewed_files = gh_files
                target_meta.update(
                    {
                        "base_ref": gh_base,
                        "head_ref": gh_head,
                        "pr": str(pr_value),
                        "pr_url": pr_url,
                    }
                )
                tooling.append(
                    ToolRun(
                        tool="gh",
                        status="ok",
                        notes="Fetched {} changed files from PR metadata".format(len(gh_files)),
                    )
                )
            except Exception as exc:
                tooling.append(
                    ToolRun(
                        tool="gh",
                        status="error",
                        notes="GitHub PR fetch failed: {}; falling back to local mode".format(exc),
                    )
                )
                mode_used = "local"

    if mode_used == "local":
        chosen_base = base_ref or compute_default_base(repo_root, head_ref)
        reviewed_files = collect_local_diff_files(repo_root, chosen_base, head_ref, max_files)
        target_meta.update(
            {
                "base_ref": chosen_base,
                "head_ref": head_ref,
            }
        )
        if verbose:
            print("[local] base={} head={} files={}".format(chosen_base, head_ref, len(reviewed_files)))

    return {
        "tooling": tooling,
        "files": reviewed_files,
        "mode": mode_used,
        "target_meta": target_meta,
    }


def main() -> int:
    """Entrypoint for PR analyzer."""
    parser = build_parser()
    args = parser.parse_args()

    if args.max_files <= 0:
        print("--max-files must be greater than zero", file=sys.stderr)
        return EXIT_INVALID_ARGS

    try:
        allowed_languages = parse_language_filter(args.languages)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID_ARGS

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print("Target path does not exist: {}".format(target_path), file=sys.stderr)
        return EXIT_INVALID_ARGS

    repo_anchor = target_path if target_path.is_dir() else target_path.parent
    repo_root = resolve_repo_root(repo_anchor)
    if repo_root is None:
        print("Target is not in a git repository: {}".format(target_path), file=sys.stderr)
        return EXIT_INVALID_ARGS

    exclude_patterns = expand_exclude_patterns(args.exclude)

    try:
        collected = _collect_files(
            repo_root=repo_root,
            mode=args.mode,
            pr_value=args.pr,
            base_ref=args.base,
            head_ref=args.head,
            max_files=args.max_files,
            verbose=args.verbose,
        )

        tooling = list(collected["tooling"])
        mode_used = str(collected["mode"])
        reviewed_files = list(collected["files"])
        target_meta = dict(collected["target_meta"])

        reviewed_files = sanitize_reviewed_files(reviewed_files, allowed_languages, exclude_patterns)

        scanned_files, builtin_findings, scanned_languages, fs_tooling = analyze_reviewed_files(
            target_root=repo_root,
            reviewed_files=reviewed_files,
            allowed_languages=allowed_languages,
            exclude_patterns=exclude_patterns,
            verbose=args.verbose,
        )

        tooling.extend(fs_tooling)

        external_tooling, external_findings = run_external_tools(
            target_root=repo_root,
            languages=scanned_languages,
            verbose=args.verbose,
        )
        tooling.extend(external_tooling)

        result = build_review_result(
            tool_name="pr_analyzer",
            target_path=repo_root,
            mode=mode_used,
            files=scanned_files,
            tooling=tooling,
            findings=builtin_findings + external_findings,
            fail_on=args.fail_on,
            extra_target=target_meta,
        )

        output_paths = write_review_outputs(
            result=result,
            output_dir=Path(args.output_dir),
            base_name="pr_analysis",
            output_format=args.format,
            markdown_title="PR Analyzer Report",
        )

        payload = result.to_dict()
        print(
            json.dumps(
                {
                    "summary": payload["summary"],
                    "outputs": {key: str(value) for key, value in output_paths.items()},
                },
                indent=2,
            )
        )
        return int(payload["summary"]["exit_code"])

    except RuntimeError as exc:
        print("Runtime error: {}".format(exc), file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    except Exception as exc:
        print("Unexpected error: {}".format(exc), file=sys.stderr)
        return EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
