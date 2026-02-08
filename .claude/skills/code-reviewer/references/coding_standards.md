# Coding Standards

This document defines baseline coding standards used by the `code-reviewer` skill.

## 1. Universal Standards

- Prefer readable, explicit code over clever shortcuts.
- Keep functions focused and composable.
- Keep side effects near boundaries (I/O, network, DB, filesystem).
- Fail loudly for unexpected states; avoid silent degradation.
- Treat user-controlled input as untrusted.
- Use structured logging with consistent fields.
- Keep configuration explicit and environment-driven.

## 2. API and Interface Standards

- Make contracts explicit: input schema, output schema, error semantics.
- Preserve backward compatibility or version breaking changes deliberately.
- Validate boundary inputs early.
- Return typed/domain errors where practical.
- Document behavior that is non-obvious or security-sensitive.

## 3. Error Handling Standards

- Include enough context for debugging while avoiding sensitive leakage.
- Preserve root cause when wrapping errors.
- Do not swallow exceptions/errors without telemetry.
- Use retries only for transient failures with jitter/backoff.
- Add circuit breakers/timeouts for remote dependencies.

## 4. Testing Standards

- Unit tests for pure logic and edge cases.
- Integration tests for component boundaries and data flows.
- Regression tests for every production bug fix.
- Negative tests for invalid input and failure handling.
- Keep tests deterministic and isolated.

## 5. Security Standards

- Centralize authn/authz checks near privileged actions.
- Parameterize all queries and command executions.
- Do not commit credentials or long-lived secrets.
- Sanitize logs to avoid leaking sensitive values.
- Use safe defaults for serializers and parsers.
- Keep dependencies patched and vulnerabilities triaged.

## 6. Language Standards

## TypeScript

- Prefer strict type checking.
- Avoid `any`; use `unknown` + narrowing when needed.
- Use discriminated unions for variant payloads.
- Keep side effects out of utility functions.

## JavaScript

- Prefer immutable patterns where practical.
- Validate external JSON/API payloads.
- Do not use implicit coercion in critical logic.
- Handle promise rejection paths explicitly.

## Python

- Use explicit exception types.
- Use context managers for resources.
- Keep modules import-safe and side-effect-light.
- Use type hints for public interfaces.

## Go

- Check every error return.
- Keep interfaces small and behavior-driven.
- Propagate `context.Context` through call stacks.
- Keep goroutines bounded and cancelable.

## Swift

- Prefer safe optional handling over force unwrap.
- Keep UI and business logic separated.
- Use clear async/await error propagation.
- Avoid retain cycles in closure captures.

## Kotlin

- Prefer null-safe operators to `!!`.
- Use structured concurrency (`CoroutineScope`, `SupervisorJob`).
- Keep exception handling specific and intentional.
- Use sealed classes for domain state and outcomes.

## 7. Minimum Quality Gates

A change is merge-ready when:

- Critical/high findings are addressed or explicitly accepted.
- Required tests pass locally and in CI.
- New behavior is covered by tests.
- Security-sensitive paths are reviewed.
- Operational impact (migration, rollout, rollback) is documented.
