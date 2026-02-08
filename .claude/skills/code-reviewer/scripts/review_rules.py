#!/usr/bin/env python3
"""Language rules, built-in checks, and external tool adapters."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from review_types import Finding

LANGUAGE_BY_EXTENSION: Dict[str, str] = {
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".py": "python",
    ".pyi": "python",
    ".go": "go",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
}

LANGUAGE_ALIASES: Dict[str, str] = {
    "ts": "typescript",
    "typescript": "typescript",
    "js": "javascript",
    "javascript": "javascript",
    "py": "python",
    "python": "python",
    "go": "go",
    "swift": "swift",
    "kt": "kotlin",
    "kotlin": "kotlin",
}

SUPPORTED_LANGUAGES: Tuple[str, ...] = (
    "typescript",
    "javascript",
    "python",
    "swift",
    "kotlin",
    "go",
)

MAX_FINDINGS_PER_RULE = 25
MAX_TODO_FINDINGS = 40

TODO_PATTERN = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b", re.IGNORECASE)
SECRET_PATTERN = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|token|access[_-]?key)\b\s*[:=]\s*[\"'][^\"']{8,}[\"']"
)
SQL_CONCAT_PATTERN = re.compile(
    r"(?i)(SELECT|INSERT|UPDATE|DELETE)[^\n\r]{0,120}[\"'][^\n\r]{0,120}\s*\+"
)


@dataclass(frozen=True)
class ExternalToolSpec:
    """External tool execution spec."""

    tool: str
    command: List[str]
    parser: str
    cwd: Optional[Path] = None


def detect_language(path: str) -> Optional[str]:
    """Detect supported language for a file path."""
    return LANGUAGE_BY_EXTENSION.get(Path(path).suffix.lower())


def parse_language_filter(raw_value: Optional[str]) -> Optional[Set[str]]:
    """Parse comma-separated language aliases into canonical names."""
    if raw_value is None:
        return None
    raw_value = raw_value.strip()
    if not raw_value:
        return None

    selected: Set[str] = set()
    unknown: List[str] = []
    for token in raw_value.split(","):
        alias = token.strip().lower()
        if not alias:
            continue
        mapped = LANGUAGE_ALIASES.get(alias)
        if mapped is None:
            unknown.append(alias)
        else:
            selected.add(mapped)

    if unknown:
        supported = ", ".join(sorted(LANGUAGE_ALIASES.keys()))
        raise ValueError(
            "Unsupported language filter(s): {}. Supported values: {}".format(
                ", ".join(sorted(unknown)), supported
            )
        )

    return selected or None


def filter_languages(languages: Iterable[str], allowed: Optional[Set[str]]) -> Set[str]:
    """Apply optional language filter."""
    values = set(languages)
    if allowed is None:
        return values
    return {language for language in values if language in allowed}


def _line_finding(
    findings: List[Finding],
    finding_id: str,
    title: str,
    severity: str,
    category: str,
    language: str,
    path: str,
    line: int,
    evidence: str,
    recommendation: str,
    source: str = "builtin",
    confidence: float = 0.75,
) -> None:
    findings.append(
        Finding(
            id=finding_id,
            title=title,
            severity=severity,
            category=category,
            language=language,
            path=path,
            line=line,
            confidence=confidence,
            source=source,
            evidence=evidence,
            recommendation=recommendation,
        )
    )


def _count_indent_depth(line: str) -> int:
    prefix = len(line) - len(line.lstrip(" \t"))
    if prefix <= 0:
        return 0
    chunk = line[:prefix]
    spaces = chunk.count(" ")
    tabs = chunk.count("\t")
    return tabs + (spaces // 4)


def _find_large_python_functions(lines: Sequence[str], threshold: int = 120) -> List[Tuple[int, int]]:
    blocks: List[Tuple[int, int]] = []
    index = 0
    total = len(lines)
    while index < total:
        line = lines[index]
        if re.match(r"^\s*def\s+\w+\s*\(", line):
            start = index
            start_indent = _count_indent_depth(line)
            end = start
            probe = start + 1
            while probe < total:
                candidate = lines[probe]
                if not candidate.strip():
                    probe += 1
                    continue
                indent = _count_indent_depth(candidate)
                if indent <= start_indent and not candidate.lstrip().startswith("#"):
                    break
                end = probe
                probe += 1
            if end - start + 1 > threshold:
                blocks.append((start + 1, end + 1))
            index = probe
            continue
        index += 1
    return blocks


def _find_large_brace_functions(
    lines: Sequence[str], declaration_pattern: re.Pattern, threshold: int = 120
) -> List[Tuple[int, int]]:
    blocks: List[Tuple[int, int]] = []
    total = len(lines)
    for index, line in enumerate(lines):
        if not declaration_pattern.search(line):
            continue
        balance = line.count("{") - line.count("}")
        start = index
        end = index
        probe = index + 1
        # Advance until we see body start.
        while probe < total and balance <= 0:
            candidate = lines[probe]
            balance += candidate.count("{") - candidate.count("}")
            end = probe
            probe += 1
        while probe < total and balance > 0:
            candidate = lines[probe]
            balance += candidate.count("{") - candidate.count("}")
            end = probe
            probe += 1
        if end - start + 1 > threshold:
            blocks.append((start + 1, end + 1))
    return blocks


def _run_generic_checks(path: str, language: str, text: str) -> List[Finding]:
    findings: List[Finding] = []
    lines = text.splitlines()

    if len(lines) > 1500:
        _line_finding(
            findings,
            "CR-GEN-001",
            "Oversized file",
            "medium",
            "maintainability",
            "generic",
            path,
            1,
            "File has {} lines; large files are harder to review and maintain.".format(len(lines)),
            "Split this file into smaller modules with focused responsibilities.",
            confidence=0.9,
        )

    todo_count = 0
    for line_number, line in enumerate(lines, start=1):
        if todo_count >= MAX_TODO_FINDINGS:
            break
        match = TODO_PATTERN.search(line)
        if not match:
            continue
        todo_count += 1
        _line_finding(
            findings,
            "CR-GEN-002",
            "Outstanding TODO/FIXME marker",
            "low",
            "maintainability",
            "generic",
            path,
            line_number,
            line.strip(),
            "Resolve or track this debt in an issue before merging.",
            confidence=0.6,
        )

    deep_hits = 0
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        if _count_indent_depth(line) >= 6:
            deep_hits += 1
            _line_finding(
                findings,
                "CR-GEN-003",
                "Deep nesting detected",
                "low",
                "maintainability",
                "generic",
                path,
                line_number,
                line.rstrip(),
                "Refactor nested logic into helper functions or early returns.",
                confidence=0.55,
            )
            if deep_hits >= MAX_FINDINGS_PER_RULE:
                break

    debug_patterns = {
        "python": re.compile(r"\bprint\s*\("),
        "javascript": re.compile(r"\bconsole\.(log|debug|info)\s*\("),
        "typescript": re.compile(r"\bconsole\.(log|debug|info)\s*\("),
        "go": re.compile(r"\bfmt\.(Print|Printf|Println)\s*\("),
        "swift": re.compile(r"\bprint\s*\("),
        "kotlin": re.compile(r"\bprintln\s*\("),
    }
    debug_pattern = debug_patterns.get(language)
    if debug_pattern:
        debug_hits = 0
        for line_number, line in enumerate(lines, start=1):
            if debug_hits >= MAX_FINDINGS_PER_RULE:
                break
            if debug_pattern.search(line):
                debug_hits += 1
                _line_finding(
                    findings,
                    "CR-GEN-004",
                    "Debug logging left in code",
                    "low",
                    "style",
                    language,
                    path,
                    line_number,
                    line.strip(),
                    "Remove debug logging or guard it behind structured log levels.",
                    confidence=0.7,
                )

    if language == "python":
        blocks = _find_large_python_functions(lines)
    elif language in {"javascript", "typescript"}:
        blocks = _find_large_brace_functions(
            lines,
            re.compile(r"^\s*((async\s+)?function\s+\w+|\w+\s*[:=]\s*(async\s*)?\([^\)]*\)\s*=>)")
        )
    elif language == "go":
        blocks = _find_large_brace_functions(lines, re.compile(r"^\s*func\s+"))
    elif language == "swift":
        blocks = _find_large_brace_functions(lines, re.compile(r"^\s*func\s+"))
    elif language == "kotlin":
        blocks = _find_large_brace_functions(lines, re.compile(r"^\s*fun\s+"))
    else:
        blocks = []

    for start, end in blocks[:MAX_FINDINGS_PER_RULE]:
        _line_finding(
            findings,
            "CR-GEN-005",
            "Oversized function",
            "medium",
            "maintainability",
            language if language in SUPPORTED_LANGUAGES else "generic",
            path,
            start,
            "Function spans {} lines ({}-{}).".format(end - start + 1, start, end),
            "Break this function into smaller units with focused behavior.",
            confidence=0.8,
        )

    return findings


def _run_python_checks(path: str, text: str) -> List[Finding]:
    findings: List[Finding] = []
    lines = text.splitlines()

    for line_number, line in enumerate(lines, start=1):
        if re.search(r"^\s*except\s*(Exception)?\s*:", line):
            _line_finding(
                findings,
                "CR-PY-001",
                "Broad exception handling",
                "medium",
                "correctness",
                "python",
                path,
                line_number,
                line.strip(),
                "Catch specific exception types and preserve unexpected failures.",
                confidence=0.85,
            )

        if re.search(r"subprocess\.(Popen|run|call|check_output|check_call)\([^\n]*shell\s*=\s*True", line):
            _line_finding(
                findings,
                "CR-PY-002",
                "subprocess with shell=True",
                "high",
                "security",
                "python",
                path,
                line_number,
                line.strip(),
                "Use argument lists with shell=False and validate user input.",
                confidence=0.95,
            )

        if "tempfile.mktemp(" in line:
            _line_finding(
                findings,
                "CR-PY-003",
                "Insecure temporary file creation",
                "high",
                "security",
                "python",
                path,
                line_number,
                line.strip(),
                "Use tempfile.NamedTemporaryFile or mkstemp for secure temp files.",
                confidence=0.95,
            )

    return findings


def _run_js_ts_checks(path: str, language: str, text: str) -> List[Finding]:
    findings: List[Finding] = []
    lines = text.splitlines()

    any_count = 0
    for line in lines:
        any_count += len(re.findall(r":\s*any\b|\bas\s+any\b|<any>", line))
    if language == "typescript" and any_count >= 4:
        _line_finding(
            findings,
            "CR-TS-001",
            "Frequent use of any",
            "low",
            "maintainability",
            "typescript",
            path,
            1,
            "Detected {} any annotations or casts.".format(any_count),
            "Replace any with concrete or generic types where feasible.",
            confidence=0.75,
        )

    promise_then = 0
    promise_catch = 0
    for line_number, line in enumerate(lines, start=1):
        if re.search(r"\beval\s*\(", line) or re.search(r"new\s+Function\s*\(", line):
            _line_finding(
                findings,
                "CR-JS-001",
                "Dynamic code execution",
                "high",
                "security",
                language,
                path,
                line_number,
                line.strip(),
                "Avoid eval/new Function; use safer parsing and explicit dispatch.",
                confidence=0.95,
            )

        if ".then(" in line:
            promise_then += 1
        if ".catch(" in line:
            promise_catch += 1

    if promise_then > 0 and promise_catch == 0:
        _line_finding(
            findings,
            "CR-JS-002",
            "Promise chain without catch",
            "medium",
            "correctness",
            language,
            path,
            1,
            "Found promise chains with .then(...) but no .catch(...).",
            "Handle promise rejections with catch or async/await try/catch.",
            confidence=0.65,
        )

    return findings


def _run_go_checks(path: str, text: str) -> List[Finding]:
    findings: List[Finding] = []
    lines = text.splitlines()

    for line_number, line in enumerate(lines, start=1):
        if re.search(r"^\s*_\s*,\s*err\s*:=", line):
            _line_finding(
                findings,
                "CR-GO-001",
                "Potential ignored return value",
                "medium",
                "correctness",
                "go",
                path,
                line_number,
                line.strip(),
                "Capture and validate all returned values before continuing.",
                confidence=0.7,
            )

        if re.search(r"\bpanic\s*\(", line):
            _line_finding(
                findings,
                "CR-GO-002",
                "panic used in non-test code",
                "medium",
                "maintainability",
                "go",
                path,
                line_number,
                line.strip(),
                "Prefer returning errors and handling them at boundaries.",
                confidence=0.75,
            )

        if "context.Background()" in line:
            _line_finding(
                findings,
                "CR-GO-003",
                "Potential context propagation gap",
                "low",
                "correctness",
                "go",
                path,
                line_number,
                line.strip(),
                "Prefer passing request-scoped context through call chains.",
                confidence=0.6,
            )

    return findings


def _run_swift_checks(path: str, text: str) -> List[Finding]:
    findings: List[Finding] = []
    lines = text.splitlines()

    force_unwrap_count = 0
    for line_number, line in enumerate(lines, start=1):
        sanitized = line.replace("!=", " ").replace("==", " ")
        force_unwrap_count += len(re.findall(r"\b\w+!", sanitized))

        if re.search(r"\[\s*self\s*\]", line):
            _line_finding(
                findings,
                "CR-SW-002",
                "Strong self capture in closure",
                "medium",
                "correctness",
                "swift",
                path,
                line_number,
                line.strip(),
                "Use [weak self] or [unowned self] where retain cycles are possible.",
                confidence=0.7,
            )

        if "try!" in line:
            _line_finding(
                findings,
                "CR-SW-003",
                "Forced try detected",
                "high",
                "correctness",
                "swift",
                path,
                line_number,
                line.strip(),
                "Replace try! with do/catch or proper error propagation.",
                confidence=0.85,
            )

    if force_unwrap_count >= 3:
        _line_finding(
            findings,
            "CR-SW-001",
            "Frequent force unwrap usage",
            "medium",
            "correctness",
            "swift",
            path,
            1,
            "Detected {} potential force unwraps.".format(force_unwrap_count),
            "Reduce force unwraps using optional binding and guard statements.",
            confidence=0.75,
        )

    return findings


def _run_kotlin_checks(path: str, text: str) -> List[Finding]:
    findings: List[Finding] = []
    lines = text.splitlines()

    nn_count = text.count("!!")
    if nn_count >= 3:
        _line_finding(
            findings,
            "CR-KT-001",
            "Frequent non-null assertion usage",
            "medium",
            "correctness",
            "kotlin",
            path,
            1,
            "Detected {} occurrences of !!.".format(nn_count),
            "Prefer null-safe operators and explicit validation.",
            confidence=0.75,
        )

    for line_number, line in enumerate(lines, start=1):
        if re.search(r"catch\s*\(\s*\w+\s*:\s*Exception\s*\)", line):
            _line_finding(
                findings,
                "CR-KT-002",
                "Broad exception catch",
                "medium",
                "correctness",
                "kotlin",
                path,
                line_number,
                line.strip(),
                "Catch specific exception types whenever possible.",
                confidence=0.8,
            )

        if "GlobalScope.launch" in line:
            _line_finding(
                findings,
                "CR-KT-003",
                "Global coroutine scope usage",
                "high",
                "maintainability",
                "kotlin",
                path,
                line_number,
                line.strip(),
                "Prefer structured concurrency with lifecycle-aware scopes.",
                confidence=0.85,
            )

    return findings


def _run_security_signatures(path: str, language: str, text: str) -> List[Finding]:
    findings: List[Finding] = []
    lines = text.splitlines()

    for line_number, line in enumerate(lines, start=1):
        clean = line.strip()
        if not clean:
            continue

        if re.search(r"\bos\.system\s*\(", line) or re.search(
            r"Runtime\.getRuntime\s*\(\)\.exec\s*\(", line
        ):
            _line_finding(
                findings,
                "CR-SEC-001",
                "Potential command injection sink",
                "high",
                "security",
                language,
                path,
                line_number,
                clean,
                "Avoid shell command construction from untrusted input.",
                confidence=0.9,
            )

        if SECRET_PATTERN.search(line):
            lowered = line.lower()
            if "example" not in lowered and "changeme" not in lowered and "your_" not in lowered:
                _line_finding(
                    findings,
                    "CR-SEC-002",
                    "Possible hardcoded secret",
                    "high",
                    "security",
                    language,
                    path,
                    line_number,
                    clean,
                    "Load secrets from environment or secret management systems.",
                    confidence=0.8,
                )

        if SQL_CONCAT_PATTERN.search(line):
            _line_finding(
                findings,
                "CR-SEC-003",
                "SQL query built by string concatenation",
                "high",
                "security",
                language,
                path,
                line_number,
                clean,
                "Use parameterized queries or safe ORM query builders.",
                confidence=0.85,
            )

        if re.search(r"\bpickle\.loads\s*\(", line) or re.search(
            r"\byaml\.load\s*\(", line
        ) or "ObjectInputStream" in line:
            _line_finding(
                findings,
                "CR-SEC-004",
                "Unsafe deserialization pattern",
                "critical",
                "security",
                language,
                path,
                line_number,
                clean,
                "Use safe parsing APIs and validate untrusted payloads.",
                confidence=0.95,
            )

    return findings


def run_builtin_checks(path: str, language: str, text: str) -> List[Finding]:
    """Run built-in static checks for a single file."""
    findings = []
    findings.extend(_run_generic_checks(path, language, text))
    findings.extend(_run_security_signatures(path, language, text))

    if language == "python":
        findings.extend(_run_python_checks(path, text))
    elif language in {"javascript", "typescript"}:
        findings.extend(_run_js_ts_checks(path, language, text))
    elif language == "go":
        findings.extend(_run_go_checks(path, text))
    elif language == "swift":
        findings.extend(_run_swift_checks(path, text))
    elif language == "kotlin":
        findings.extend(_run_kotlin_checks(path, text))

    return findings


def _eslint_config_exists(target_path: Path) -> bool:
    candidates = [
        "eslint.config.js",
        "eslint.config.mjs",
        "eslint.config.cjs",
        ".eslintrc",
        ".eslintrc.js",
        ".eslintrc.cjs",
        ".eslintrc.json",
        ".eslintrc.yml",
        ".eslintrc.yaml",
        "package.json",
    ]
    for candidate in candidates:
        path = target_path / candidate
        if not path.exists():
            continue
        if candidate == "package.json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(payload, dict) and "eslintConfig" in payload:
                return True
            continue
        return True
    return False


def _python_manifest_exists(target_path: Path) -> bool:
    for name in ("requirements.txt", "requirements-dev.txt", "pyproject.toml", "Pipfile", "setup.py"):
        if (target_path / name).exists():
            return True
    return False


def _go_module_exists(target_path: Path) -> bool:
    return (target_path / "go.mod").exists()


def _kotlin_build_exists(target_path: Path) -> bool:
    return (target_path / "build.gradle.kts").exists() or (target_path / "build.gradle").exists()


def get_external_tool_specs(target_path: Path, languages: Set[str]) -> List[ExternalToolSpec]:
    """Return external tool specs that should be attempted."""
    specs: List[ExternalToolSpec] = []

    if "python" in languages:
        specs.append(
            ExternalToolSpec(
                tool="bandit",
                command=["bandit", "-q", "-r", str(target_path), "-f", "json"],
                parser="bandit",
                cwd=target_path,
            )
        )
        if _python_manifest_exists(target_path):
            specs.append(
                ExternalToolSpec(
                    tool="pip-audit",
                    command=["pip-audit", "-f", "json"],
                    parser="pip-audit",
                    cwd=target_path,
                )
            )

    if "javascript" in languages or "typescript" in languages:
        if _eslint_config_exists(target_path):
            specs.append(
                ExternalToolSpec(
                    tool="eslint",
                    command=["eslint", str(target_path), "-f", "json"],
                    parser="eslint",
                    cwd=target_path,
                )
            )

    if "go" in languages:
        if _go_module_exists(target_path):
            specs.append(
                ExternalToolSpec(
                    tool="golangci-lint",
                    command=["golangci-lint", "run", "--out-format", "json"],
                    parser="golangci-lint",
                    cwd=target_path,
                )
            )
            specs.append(
                ExternalToolSpec(
                    tool="govulncheck",
                    command=["govulncheck", "-json", "./..."],
                    parser="govulncheck",
                    cwd=target_path,
                )
            )

    if "swift" in languages:
        specs.append(
            ExternalToolSpec(
                tool="swiftlint",
                command=["swiftlint", "lint", "--reporter", "json"],
                parser="swiftlint",
                cwd=target_path,
            )
        )

    if "kotlin" in languages and _kotlin_build_exists(target_path):
        specs.append(
            ExternalToolSpec(
                tool="detekt",
                command=["detekt", "--report", "json:/dev/stdout"],
                parser="detekt",
                cwd=target_path,
            )
        )

    if languages:
        specs.append(
            ExternalToolSpec(
                tool="semgrep",
                command=["semgrep", "--json", "--quiet", "--config", "auto", str(target_path)],
                parser="semgrep",
                cwd=target_path,
            )
        )

    return specs


def _severity_from_external(tool: str, value: str) -> str:
    normalized = (value or "").strip().lower()
    mapping = {
        "error": "high",
        "warning": "medium",
        "warn": "medium",
        "info": "low",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "critical": "critical",
    }
    if tool == "bandit":
        bandit_map = {
            "high": "high",
            "medium": "medium",
            "low": "low",
        }
        return bandit_map.get(normalized, "medium")
    return mapping.get(normalized, "medium")


def _normalize_path(raw_path: str, target_root: Path) -> str:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (target_root / candidate).resolve()
    try:
        return str(candidate.relative_to(target_root.resolve())).replace("\\", "/")
    except Exception:
        return str(candidate).replace("\\", "/")


def _parse_json_or_empty(stdout: str):
    try:
        return json.loads(stdout)
    except Exception:
        return None


def parse_external_findings(
    parser: str, stdout: str, stderr: str, target_root: Path
) -> List[Finding]:
    """Parse tool output into normalized findings."""
    del stderr
    findings: List[Finding] = []

    if parser == "bandit":
        payload = _parse_json_or_empty(stdout)
        if not isinstance(payload, dict):
            return findings
        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue
            rule_id = item.get("test_id", "B000")
            path = _normalize_path(str(item.get("filename", ".")), target_root)
            line_number = int(item.get("line_number", 1) or 1)
            _line_finding(
                findings,
                "EXT-BANDIT-{}".format(rule_id),
                str(item.get("issue_text", "Bandit finding")),
                _severity_from_external("bandit", str(item.get("issue_severity", "medium"))),
                "security",
                detect_language(path) or "generic",
                path,
                line_number,
                str(item.get("code", "")).strip()[:500],
                "Address the security issue highlighted by bandit.",
                source="external:bandit",
                confidence=0.85,
            )
        return findings

    if parser == "pip-audit":
        payload = _parse_json_or_empty(stdout)
        if not isinstance(payload, dict):
            return findings
        for dep in payload.get("dependencies", []):
            if not isinstance(dep, dict):
                continue
            for vuln in dep.get("vulns", []):
                if not isinstance(vuln, dict):
                    continue
                vuln_id = str(vuln.get("id", "UNKNOWN"))
                _line_finding(
                    findings,
                    "EXT-PIPAUDIT-{}".format(vuln_id),
                    "Dependency vulnerability",
                    "high",
                    "security",
                    "python",
                    "requirements",
                    1,
                    "{} {} affected by {}".format(dep.get("name", "dependency"), dep.get("version", ""), vuln_id),
                    "Upgrade dependency to a fixed version reported by pip-audit.",
                    source="external:pip-audit",
                    confidence=0.9,
                )
        return findings

    if parser == "semgrep":
        payload = _parse_json_or_empty(stdout)
        if not isinstance(payload, dict):
            return findings
        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue
            extra = item.get("extra", {}) if isinstance(item.get("extra"), dict) else {}
            start = item.get("start", {}) if isinstance(item.get("start"), dict) else {}
            path = _normalize_path(str(item.get("path", ".")), target_root)
            _line_finding(
                findings,
                "EXT-SEMGREP-{}".format(item.get("check_id", "RULE")),
                str(extra.get("message", "Semgrep finding")),
                _severity_from_external("semgrep", str(extra.get("severity", "warning"))),
                "security",
                detect_language(path) or "generic",
                path,
                int(start.get("line", 1) or 1),
                str(extra.get("metadata", {}))[:500],
                "Apply the recommended remediation for this semgrep rule.",
                source="external:semgrep",
                confidence=0.8,
            )
        return findings

    if parser == "eslint":
        payload = _parse_json_or_empty(stdout)
        if not isinstance(payload, list):
            return findings
        for file_report in payload:
            if not isinstance(file_report, dict):
                continue
            file_path = _normalize_path(str(file_report.get("filePath", ".")), target_root)
            language = detect_language(file_path) or "generic"
            for message in file_report.get("messages", []):
                if not isinstance(message, dict):
                    continue
                rule = message.get("ruleId") or "eslint"
                severity = "high" if int(message.get("severity", 1)) >= 2 else "medium"
                _line_finding(
                    findings,
                    "EXT-ESLINT-{}".format(rule),
                    str(message.get("message", "ESLint finding")),
                    severity,
                    "maintainability",
                    language,
                    file_path,
                    int(message.get("line", 1) or 1),
                    str(message.get("message", "")),
                    "Fix this lint issue or update lint rules with documented justification.",
                    source="external:eslint",
                    confidence=0.7,
                )
        return findings

    if parser == "golangci-lint":
        payload = _parse_json_or_empty(stdout)
        if not isinstance(payload, dict):
            return findings
        for issue in payload.get("Issues", []):
            if not isinstance(issue, dict):
                continue
            pos = issue.get("Pos", {}) if isinstance(issue.get("Pos"), dict) else {}
            file_path = _normalize_path(str(pos.get("Filename", ".")), target_root)
            _line_finding(
                findings,
                "EXT-GOLANGCI-{}".format(issue.get("FromLinter", "lint")),
                str(issue.get("Text", "Go lint finding")),
                "medium",
                "maintainability",
                "go",
                file_path,
                int(pos.get("Line", 1) or 1),
                str(issue.get("Text", "")),
                "Address linter-reported issue and keep linter enabled in CI.",
                source="external:golangci-lint",
                confidence=0.75,
            )
        return findings

    if parser == "govulncheck":
        for raw_line in stdout.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                event = json.loads(raw_line)
            except Exception:
                continue
            finding = event.get("finding") or event.get("Finding")
            if not isinstance(finding, dict):
                continue
            osv = finding.get("osv", "UNKNOWN")
            _line_finding(
                findings,
                "EXT-GOVULNCHECK-{}".format(osv),
                "Go vulnerability reported",
                "high",
                "security",
                "go",
                "go.mod",
                1,
                str(finding)[:500],
                "Upgrade affected modules and verify transitive dependencies.",
                source="external:govulncheck",
                confidence=0.9,
            )
        return findings

    if parser == "swiftlint":
        payload = _parse_json_or_empty(stdout)
        if not isinstance(payload, list):
            return findings
        for item in payload:
            if not isinstance(item, dict):
                continue
            file_path = _normalize_path(str(item.get("file", ".")), target_root)
            severity = _severity_from_external("swiftlint", str(item.get("severity", "warning")))
            _line_finding(
                findings,
                "EXT-SWIFTLINT-{}".format(item.get("rule_id", "rule")),
                str(item.get("reason", "SwiftLint finding")),
                severity,
                "maintainability",
                "swift",
                file_path,
                int(item.get("line", 1) or 1),
                str(item.get("reason", "")),
                "Resolve lint issue or document an explicit exception.",
                source="external:swiftlint",
                confidence=0.7,
            )
        return findings

    if parser == "detekt":
        payload = _parse_json_or_empty(stdout)
        if not isinstance(payload, dict):
            return findings
        findings_map = payload.get("findings")
        if not isinstance(findings_map, dict):
            return findings
        for file_path, issue_list in findings_map.items():
            if not isinstance(issue_list, list):
                continue
            normalized_path = _normalize_path(str(file_path), target_root)
            for issue in issue_list:
                if not isinstance(issue, dict):
                    continue
                _line_finding(
                    findings,
                    "EXT-DETEKT-{}".format(issue.get("id", "rule")),
                    str(issue.get("message", "Detekt finding")),
                    "medium",
                    "maintainability",
                    "kotlin",
                    normalized_path,
                    int(issue.get("line", 1) or 1),
                    str(issue.get("message", "")),
                    "Address detekt findings or suppress with justification.",
                    source="external:detekt",
                    confidence=0.7,
                )
        return findings

    return findings
