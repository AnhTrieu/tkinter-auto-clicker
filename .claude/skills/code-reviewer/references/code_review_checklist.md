# Code Review Checklist

Use this checklist to drive high-signal pull request reviews.

## 1. Review Setup

- Confirm the PR goal, scope, and user impact.
- Identify high-risk files (auth, permissions, payment, data access, serialization, infra scripts).
- Verify base branch and release timeline constraints.
- Check if migration, rollout, or backward compatibility is involved.

## 2. Correctness Checklist

- Logic matches product requirements and acceptance criteria.
- Edge cases are handled (empty input, null/None, timeouts, retries, errors).
- Error handling preserves root cause and avoids silent failure.
- Behavior changes are covered with tests.
- API changes are documented and version-safe.

## 3. Security Checklist

- All external input paths are validated and sanitized.
- No command, SQL, or template injection sinks from untrusted input.
- No hardcoded secrets, credentials, or long-lived tokens.
- Authentication and authorization checks are explicit at boundaries.
- Sensitive data handling (PII, keys, tokens) is minimized and protected.
- Deserialization and parser usage is safe for untrusted data.
- Dependency vulnerabilities are acknowledged and triaged.

## 4. Maintainability Checklist

- Functions/classes have focused responsibilities.
- Names are clear and domain-meaningful.
- Large files/functions are justified or split.
- TODO/FIXME debt is tracked and bounded.
- Logging is structured and production-appropriate.
- Feature flags and config behavior are explicit.

## 5. Performance Checklist

- Complexity hotspots are identified.
- I/O operations are bounded and cancellable.
- Expensive operations are cached/batched where appropriate.
- N+1 and repeated work patterns are eliminated.
- Large allocations/objects are avoided on hot paths.

## 6. Testing Checklist

- Unit tests cover new logic and failure modes.
- Integration tests cover cross-component behavior.
- Regression tests exist for bug fixes.
- Flaky timing/network behavior is stabilized with deterministic test design.
- Test data and mocks reflect realistic usage.

## 7. Observability and Operations Checklist

- Error logs include actionable context.
- Metrics/traces exist for critical flows.
- Alerts are updated for new failure modes.
- Rollback path is documented for risky changes.
- Migration/deployment order is explicit.

## 8. Language-Specific Quick Checks

## TypeScript / JavaScript

- Avoid unsafe dynamic execution (`eval`, `new Function`).
- Prefer explicit runtime validation for API boundaries.
- Promise chains handle rejection paths.
- TypeScript: minimize `any`; use precise interfaces/generics.
- Frontend: avoid unsafe HTML insertion.

## Python

- Avoid broad `except Exception` and bare `except` without justification.
- Avoid `subprocess(..., shell=True)` with untrusted input.
- Avoid insecure temp APIs like `tempfile.mktemp`.
- Use safe loaders/parsers for untrusted data.

## Go

- Do not ignore returned errors.
- Avoid `panic` in non-test execution paths.
- Propagate request-scoped `context.Context`.
- Keep goroutines bounded and cancelable.

## Swift

- Minimize force unwrap (`!`) and forced try (`try!`).
- Avoid retain cycles in closures (`[weak self]` where needed).
- Handle async error paths explicitly.

## Kotlin

- Minimize `!!` non-null assertions.
- Avoid broad `catch (Exception)` when specific handling is possible.
- Prefer structured concurrency over `GlobalScope.launch`.

## 9. Final Reviewer Output Template

- Summary: what changed and top risks.
- Findings: ordered by severity with file/line references.
- Required fixes before merge.
- Optional improvements (non-blocking).
- Residual risk statement.
