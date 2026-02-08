# Common Anti-Patterns

High-signal anti-patterns to detect during code review, with remediation guidance.

## 1. Security Anti-Patterns

## Hardcoded Secrets

- Signals: passwords/tokens/API keys embedded in source.
- Risk: credential leakage, lateral movement.
- Fix: use environment variables or secret manager; rotate leaked values.

## String-Built SQL Queries

- Signals: SQL statement plus string concatenation/interpolation from input.
- Risk: SQL injection and data corruption.
- Fix: parameterized queries or ORM bind APIs.

## Command Construction from Input

- Signals: shell commands built with untrusted values.
- Risk: command injection and RCE.
- Fix: structured command args, strict allowlists, no shell expansion.

## Unsafe Deserialization

- Signals: generic object deserialization of untrusted data.
- Risk: code execution, privilege escalation.
- Fix: safe data formats, strict schemas, safe loaders.

## 2. Correctness Anti-Patterns

## Broad Exception Catch

- Signals: bare `except`, `catch (Exception)`, catch-all handlers.
- Risk: hidden defects, incorrect retries, silent failures.
- Fix: catch specific exceptions and preserve root-cause context.

## Ignored Error Returns

- Signals: dropped/ignored return errors (common in Go).
- Risk: inconsistent state and latent defects.
- Fix: always check and handle errors.

## Forced Unwrap / Null Assertion Abuse

- Signals: `!`, `try!`, `!!` patterns.
- Risk: runtime crashes and unstable behavior.
- Fix: explicit guards, optional binding, safe fallback paths.

## 3. Maintainability Anti-Patterns

## Large Functions and God Files

- Signals: very long functions or high file line counts.
- Risk: difficult review, fragile changes, poor reuse.
- Fix: split into focused units and extract cohesive modules.

## Deeply Nested Control Flow

- Signals: six-plus indentation levels or nested callbacks.
- Risk: hard reasoning and test coverage gaps.
- Fix: guard clauses, early returns, helper extraction.

## Residual Debug Logging

- Signals: ad hoc prints/logs in production paths.
- Risk: noisy logs, sensitive data exposure, overhead.
- Fix: structured logging with log levels and redaction.

## 4. Language-Specific Anti-Patterns

## TypeScript / JavaScript

- Excessive `any` usage.
- Unhandled promise rejections.
- Dynamic execution primitives (`eval`, `new Function`).

## Python

- `subprocess(..., shell=True)` from user input.
- `tempfile.mktemp` and unsafe temp handling.
- Unsafe parser/loader defaults.

## Go

- `panic` for routine error paths.
- Context loss across service layers.
- Shared mutable state without synchronization.

## Swift

- Closure retain cycles from strong `self` capture.
- Optional misuse leading to force unwrap chains.

## Kotlin

- Global coroutine scope in app/runtime logic.
- Null assertion (`!!`) in core paths.

## 5. False-Positive Guardrails

Before filing a blocking issue:

- Confirm if the pattern appears in tests/examples only.
- Check if tooling-generated code should be excluded.
- Verify that flagged secrets are not placeholders/mocks.
- Confirm whether strict behavior is intentionally documented.

## 6. Remediation Priority

Prioritize in this order:

1. Critical security and data-integrity risks.
2. High-severity correctness flaws.
3. Reliability and operational risks.
4. Maintainability improvements with clear payoff.
5. Style-only concerns.
