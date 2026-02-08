#!/usr/bin/env python3
"""Run repository or path-wide code quality checks across supported languages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from review_core import (
    EXIT_INVALID_ARGS,
    EXIT_RUNTIME_ERROR,
    add_shared_cli_options,
    analyze_reviewed_files,
    build_review_result,
    collect_repo_files,
    expand_exclude_patterns,
    run_external_tools,
    to_reviewed_files,
    write_review_outputs,
)
from review_rules import parse_language_filter


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser for repository quality checker."""
    parser = argparse.ArgumentParser(
        description="Analyze code quality and security patterns in TypeScript/JavaScript/Python/Swift/Kotlin/Go."
    )
    parser.add_argument("target", help="Repository path or file to analyze")
    add_shared_cli_options(parser)
    return parser


def main() -> int:
    """Entrypoint for code quality checker."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        allowed_languages = parse_language_filter(args.languages)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID_ARGS

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print("Target path does not exist: {}".format(target_path), file=sys.stderr)
        return EXIT_INVALID_ARGS

    target_root = target_path if target_path.is_dir() else target_path.parent
    exclude_patterns = expand_exclude_patterns(args.exclude)

    try:
        supported_paths = collect_repo_files(target_path)
        reviewed_files = to_reviewed_files(supported_paths, target_root, change="existing")

        scanned_files, builtin_findings, scanned_languages, fs_tooling = analyze_reviewed_files(
            target_root=target_root,
            reviewed_files=reviewed_files,
            allowed_languages=allowed_languages,
            exclude_patterns=exclude_patterns,
            verbose=args.verbose,
        )

        external_tooling, external_findings = run_external_tools(
            target_root=target_root,
            languages=scanned_languages,
            verbose=args.verbose,
        )

        result = build_review_result(
            tool_name="code_quality_checker",
            target_path=target_path,
            mode="path",
            files=scanned_files,
            tooling=fs_tooling + external_tooling,
            findings=builtin_findings + external_findings,
            fail_on=args.fail_on,
            extra_target={"scanned_root": str(target_root)},
        )

        output_paths = write_review_outputs(
            result=result,
            output_dir=Path(args.output_dir),
            base_name="code_quality",
            output_format=args.format,
            markdown_title="Code Quality Checker Report",
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
