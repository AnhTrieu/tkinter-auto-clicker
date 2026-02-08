#!/usr/bin/env python3
"""Shared types and serialization helpers for code-review scripts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

SEVERITY_ORDER: Dict[str, int] = {
    "none": -1,
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

VALID_SEVERITIES = ("low", "medium", "high", "critical")
VALID_CATEGORIES = ("correctness", "security", "maintainability", "performance", "style")
VALID_LANGUAGES = (
    "generic",
    "python",
    "javascript",
    "typescript",
    "swift",
    "kotlin",
    "go",
)


def normalize_severity(value: str) -> str:
    """Normalize unknown severities to low for stability."""
    lowered = (value or "").strip().lower()
    return lowered if lowered in SEVERITY_ORDER else "low"


def severity_meets_threshold(severity: str, threshold: str) -> bool:
    """Return True when severity breaches configured threshold."""
    s_rank = SEVERITY_ORDER.get(normalize_severity(severity), SEVERITY_ORDER["low"])
    t_rank = SEVERITY_ORDER.get((threshold or "").lower(), SEVERITY_ORDER["high"])
    if t_rank < 0:
        return False
    return s_rank >= t_rank


def severity_sort_key(severity: str) -> int:
    """Sort highest severity first."""
    return -SEVERITY_ORDER.get(normalize_severity(severity), SEVERITY_ORDER["low"])


@dataclass(frozen=True)
class Finding:
    """A normalized finding from builtin or external analyzers."""

    id: str
    title: str
    severity: str
    category: str
    language: str
    path: str
    line: int
    confidence: float
    source: str
    evidence: str
    recommendation: str

    def normalized(self) -> "Finding":
        """Return finding with normalized fields for deterministic output."""
        severity = normalize_severity(self.severity)
        category = self.category if self.category in VALID_CATEGORIES else "maintainability"
        language = self.language if self.language in VALID_LANGUAGES else "generic"
        line = self.line if isinstance(self.line, int) and self.line > 0 else 1
        confidence = float(self.confidence)
        if confidence < 0.0:
            confidence = 0.0
        if confidence > 1.0:
            confidence = 1.0
        return Finding(
            id=self.id.strip() or "CR-UNKNOWN",
            title=self.title.strip() or "Unspecified finding",
            severity=severity,
            category=category,
            language=language,
            path=self.path.strip() or ".",
            line=line,
            confidence=confidence,
            source=self.source.strip() or "builtin",
            evidence=self.evidence.strip(),
            recommendation=self.recommendation.strip(),
        )

    def dedupe_key(self) -> tuple:
        """Stable dedupe key across scanners."""
        normalized = self.normalized()
        return (
            normalized.id,
            normalized.path,
            normalized.line,
            normalized.source,
            normalized.title,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize finding to JSON-encodable dict."""
        normalized = self.normalized()
        return {
            "id": normalized.id,
            "title": normalized.title,
            "severity": normalized.severity,
            "category": normalized.category,
            "language": normalized.language,
            "path": normalized.path,
            "line": normalized.line,
            "confidence": round(normalized.confidence, 2),
            "source": normalized.source,
            "evidence": normalized.evidence,
            "recommendation": normalized.recommendation,
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "Finding":
        """Build Finding from JSON payload."""
        return Finding(
            id=str(payload.get("id", "CR-UNKNOWN")),
            title=str(payload.get("title", "Unspecified finding")),
            severity=str(payload.get("severity", "low")),
            category=str(payload.get("category", "maintainability")),
            language=str(payload.get("language", "generic")),
            path=str(payload.get("path", ".")),
            line=int(payload.get("line", 1) or 1),
            confidence=float(payload.get("confidence", 0.5) or 0.5),
            source=str(payload.get("source", "builtin")),
            evidence=str(payload.get("evidence", "")),
            recommendation=str(payload.get("recommendation", "")),
        )


@dataclass(frozen=True)
class ToolRun:
    """Execution status for external analysis tools."""

    tool: str
    status: str
    notes: str

    def to_dict(self) -> Dict[str, str]:
        status = self.status if self.status in {"ok", "missing", "error"} else "error"
        return {
            "tool": self.tool,
            "status": status,
            "notes": self.notes,
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "ToolRun":
        return ToolRun(
            tool=str(payload.get("tool", "unknown")),
            status=str(payload.get("status", "error")),
            notes=str(payload.get("notes", "")),
        )


@dataclass(frozen=True)
class ReviewedFile:
    """File selected for analysis."""

    path: str
    language: str
    change: str

    def to_dict(self) -> Dict[str, str]:
        language = self.language if self.language in VALID_LANGUAGES else "generic"
        return {
            "path": self.path,
            "language": language,
            "change": self.change,
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "ReviewedFile":
        return ReviewedFile(
            path=str(payload.get("path", "")),
            language=str(payload.get("language", "generic")),
            change=str(payload.get("change", "modified")),
        )


@dataclass(frozen=True)
class Summary:
    """Severity counts and threshold outcome."""

    counts: Dict[str, int]
    threshold: str
    failed: bool
    exit_code: int

    def to_dict(self) -> Dict[str, Any]:
        normalized_counts = {
            "critical": int(self.counts.get("critical", 0)),
            "high": int(self.counts.get("high", 0)),
            "medium": int(self.counts.get("medium", 0)),
            "low": int(self.counts.get("low", 0)),
        }
        return {
            "counts": normalized_counts,
            "threshold": self.threshold,
            "failed": bool(self.failed),
            "exit_code": int(self.exit_code),
        }

    @staticmethod
    def from_findings(findings: Iterable[Finding], threshold: str) -> "Summary":
        counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }
        failed = False
        for finding in findings:
            normalized = finding.normalized()
            counts[normalized.severity] = counts.get(normalized.severity, 0) + 1
            if severity_meets_threshold(normalized.severity, threshold):
                failed = True
        return Summary(
            counts=counts,
            threshold=threshold,
            failed=failed,
            exit_code=1 if failed else 0,
        )

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "Summary":
        return Summary(
            counts=dict(payload.get("counts", {})),
            threshold=str(payload.get("threshold", "high")),
            failed=bool(payload.get("failed", False)),
            exit_code=int(payload.get("exit_code", 0)),
        )


@dataclass
class ReviewResult:
    """Canonical review result document used by all scripts."""

    meta: Dict[str, Any]
    target: Dict[str, Any]
    files: List[ReviewedFile] = field(default_factory=list)
    tooling: List[ToolRun] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    summary: Optional[Summary] = None

    def normalize(self, threshold: str) -> "ReviewResult":
        """Normalize, sort, dedupe, and compute summary."""
        unique: Dict[tuple, Finding] = {}
        for finding in self.findings:
            normalized = finding.normalized()
            key = normalized.dedupe_key()
            if key not in unique:
                unique[key] = normalized

        sorted_findings = sorted(
            unique.values(),
            key=lambda item: (
                severity_sort_key(item.severity),
                item.path,
                item.line,
                item.id,
                item.title,
            ),
        )
        sorted_files = sorted(
            self.files,
            key=lambda item: (item.path, item.language, item.change),
        )
        sorted_tooling = sorted(self.tooling, key=lambda item: item.tool)

        self.files = sorted_files
        self.tooling = sorted_tooling
        self.findings = sorted_findings
        self.summary = Summary.from_findings(self.findings, threshold)
        return self

    def to_dict(self) -> Dict[str, Any]:
        if self.summary is None:
            self.summary = Summary.from_findings(self.findings, "high")
        return {
            "meta": dict(self.meta),
            "target": dict(self.target),
            "files": [item.to_dict() for item in self.files],
            "tooling": [item.to_dict() for item in self.tooling],
            "findings": [item.to_dict() for item in self.findings],
            "summary": self.summary.to_dict(),
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "ReviewResult":
        files = [ReviewedFile.from_dict(item) for item in payload.get("files", [])]
        tooling = [ToolRun.from_dict(item) for item in payload.get("tooling", [])]
        findings = [Finding.from_dict(item) for item in payload.get("findings", [])]
        summary_payload = payload.get("summary")
        summary = Summary.from_dict(summary_payload) if isinstance(summary_payload, dict) else None
        return ReviewResult(
            meta=dict(payload.get("meta", {})),
            target=dict(payload.get("target", {})),
            files=files,
            tooling=tooling,
            findings=findings,
            summary=summary,
        )
