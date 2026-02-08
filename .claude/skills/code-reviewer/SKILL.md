---
name: code-reviewer
description: >
  Comprehensive code review toolkit for TypeScript, JavaScript, Python, Swift, Kotlin, and Go.
  Performs automated code analysis, best practice checking, security scanning, and review
  checklist generation. Use this skill whenever reviewing pull requests, providing code feedback,
  identifying issues in code, ensuring code quality standards, or when someone pastes code and
  asks for review, feedback, improvements, or a "second pair of eyes." Also trigger when a user
  mentions code review, PR review, code quality, static analysis, security audit of code, or
  asks "what's wrong with this code" or "can you review this." Covers frontend (React, Next.js,
  React Native, Flutter), backend (Node.js, Express, GraphQL, REST), databases (PostgreSQL,
  Prisma, Supabase), and DevOps (Docker, Kubernetes, Terraform, GitHub Actions, CircleCI).
---

# Code Reviewer

Comprehensive code review toolkit with automated analysis, security scanning, and
actionable feedback generation for production codebases.

## When This Skill Activates

- User asks to review code, a PR, or a diff
- User pastes code and asks for feedback, improvements, or issue identification
- User asks about code quality, best practices, or security concerns in code
- User wants a code review checklist or report generated
- User asks "what's wrong with this code" or similar

## Review Workflow

Every code review follows this sequence. Adapt depth based on code size and context.

### Step 1: Triage and Scope

Determine what you're reviewing:
- **Single file/snippet**: Inline review, focus on correctness and style
- **Multiple files**: Check cross-file concerns (imports, shared state, API contracts)
- **Full PR/diff**: Run the PR analyzer script, assess change scope and risk

Identify the language(s) and framework(s) involved. Read the appropriate sections
from `references/coding_standards.md` for language-specific rules.

### Step 2: Automated Analysis

For code provided as files or in the working directory, run the analysis scripts:

```bash
# Analyze a PR diff (provide diff file or directory)
python scripts/pr_analyzer.py <path-to-code-or-diff> [--language <lang>] [--format markdown]

# Check code quality metrics
python scripts/code_quality_checker.py <path-to-code> [--verbose] [--language <lang>]

# Generate a structured review report
python scripts/review_report_generator.py <path-to-code> [--severity-threshold medium] [--format markdown]
```

For code provided inline in the conversation (pasted snippets), perform manual
analysis following the same checklist categories the scripts use.

### Step 3: Manual Review (Always Performed)

Even when scripts run, always perform human-quality manual analysis across these
dimensions, in this priority order:

1. **Correctness** - Does the code do what it claims? Logic errors, off-by-ones,
   null/undefined handling, race conditions, edge cases
2. **Security** - Injection risks, auth/authz gaps, secret exposure, unsafe
   deserialization, XSS/CSRF, path traversal. Read `references/common_antipatterns.md`
   section on security for language-specific vulnerabilities.
3. **Error Handling** - Uncaught exceptions, swallowed errors, missing validation,
   graceful degradation, error messages that leak internals
4. **Performance** - N+1 queries, unnecessary re-renders, missing indexes, unbounded
   loops, memory leaks, missing pagination
5. **Maintainability** - Naming clarity, function size, coupling, code duplication,
   abstraction level consistency
6. **Testing** - Test coverage gaps, missing edge case tests, test isolation, mock
   appropriateness, assertion quality
7. **API Design** - Contract clarity, backwards compatibility, error response format,
   versioning, documentation

### Step 4: Generate Findings

Structure findings using severity levels:

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Security vulnerability, data loss risk, crash in production | Must fix before merge |
| **HIGH** | Bug, significant perf issue, broken error handling | Should fix before merge |
| **MEDIUM** | Code smell, maintainability concern, missing tests | Fix soon, can merge with ticket |
| **LOW** | Style nit, naming suggestion, minor optimization | Optional, author's discretion |
| **INFO** | Positive feedback, learning opportunity, FYI | No action needed |

Each finding must include:
- File and line reference (when available)
- Clear description of the issue
- Why it matters (impact)
- Suggested fix (concrete code when possible)

### Step 5: Deliver the Review

Format the review report as follows:

```markdown
## Code Review Summary

**Scope**: [what was reviewed]
**Language(s)**: [detected languages]
**Risk Level**: [Low / Medium / High / Critical]
**Overall Assessment**: [Ship it / Ship with fixes / Needs work / Block]

### Critical & High Findings
[findings with suggested fixes]

### Medium Findings
[findings with context]

### Low & Info
[grouped nits and positive feedback]

### Recommendations
[architectural suggestions, follow-up items]
```

## Language-Specific Guidance

Read the appropriate reference file based on the language(s) detected:

- For **language-specific coding standards**: Read `references/coding_standards.md`
  and navigate to the relevant language section (TypeScript, JavaScript, Python,
  Go, Swift, Kotlin)
- For **review checklists by category**: Read `references/code_review_checklist.md`
  for structured checklists covering correctness, security, performance, etc.
- For **anti-pattern identification**: Read `references/common_antipatterns.md`
  for catalogued anti-patterns with examples and fixes per language

## Framework-Specific Concerns

When reviewing framework code, pay extra attention to:

**React / Next.js**: Hook rules, dependency arrays, key props, SSR hydration
mismatches, unnecessary re-renders, proper use of server/client components

**Node.js / Express**: Middleware ordering, async error handling, unhandled promise
rejections, stream backpressure, connection pool exhaustion

**GraphQL**: N+1 resolver queries, schema design, input validation, depth limiting,
query complexity analysis

**Database (Prisma/PostgreSQL)**: Missing indexes, N+1 queries via includes,
transaction usage, migration safety, connection pooling

**Mobile (Swift/Kotlin/Flutter)**: Memory leaks, main thread blocking, lifecycle
management, permission handling, deep link security

**DevOps (Docker/K8s/Terraform)**: Base image security, secret management, resource
limits, health checks, state drift, IAM least privilege

## Security Review Depth

For any code handling authentication, authorization, user input, file operations,
or network requests, perform an enhanced security review:

1. Check OWASP Top 10 applicability
2. Verify input validation at trust boundaries
3. Check for hardcoded secrets or credentials
4. Verify proper use of crypto primitives (no custom crypto)
5. Check dependency versions for known CVEs (when package files are available)
6. Verify CSP headers, CORS configuration, cookie flags for web code

Read `references/common_antipatterns.md` security section for language-specific
vulnerability patterns.

## Review Tone

Be direct and constructive. Lead with what the code does well before diving into
issues. Frame suggestions as improvements rather than criticism. Provide concrete
fix suggestions rather than vague complaints. Use inline code examples for fixes.
Distinguish between objective issues (bugs, security) and subjective preferences
(naming, style) clearly.
