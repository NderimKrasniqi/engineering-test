# Software Engineering Quality Standard — v16

**Human owns WHAT. Agent owns HOW and engineering quality.**

This policy is a durable standard, not a mandate to add layers, libraries or complexity.

## Enduring engineering practices

- **Correctness:** explicit invariants, stable behavior, meaningful errors, safe partial failure, data integrity and compatibility.
- **Readability:** intent-revealing names, clear control flow, no clever shortcuts, avoid routine comments; write a short comment only when the reason is not clear from the code itself.
- **Maintainability:** cohesive modules, loose coupling, explicit boundaries, few high-value, behavior-focused tests, minimal duplication, reversible changes.
- **Simplicity:** KISS and YAGNI. Apply SOLID/DRY with judgment; premature abstraction and microservices are not quality.
- **Security:** trust boundaries, validated inputs, authorization, parameterized queries, least privilege, safe secrets and dependencies. Do not rely only on scanners.
- **Reliability:** bounded retries/timeouts, idempotency where needed, concurrency safety, migration and rollback plans when relevant.
- **Scalability:** consider expected users, data size, load, growth, bottlenecks, indexing, memory, and operational cost. Prefer a modular monolith until distribution is justified; measure before optimizing.
- **Observability:** errors that can be diagnosed, useful logs and metrics when appropriate, without leaking secrets.
- **Operations:** reproducible builds, project conventions, safe deployment and rollback, backwards-compatible evolution.

## Verification and review

The quality gate has **two separate sources**:

1. **Executed checks** recorded by the verification engine. Use `e2e` for a real user journey through the application boundary (browser, HTTP, CLI, or library public API); use `edge` only for a targeted high-risk invariant. Other categories are `static`, `security`, `build`, `performance`, `test` (legacy), and `other`. Configure real commands, not placeholders. Required categories depend on task risk (`quality.json`).
2. **Agent review** of the actual diff. The reviewer assesses readability, maintainability, security, reliability, scalability and compatibility. Each judgment has concrete rationale and links to passed checks or source files. The gate validates completeness, freshness and references, **not the truth** of subjective judgments.

For high-risk changes, security and reliability must be assessed, and a security check must execute. A critical invariant such as concurrency or money safety may need one focused `edge` test even when the end-to-end journey passes. An independent human or external CI/security review can be required by organizational policy. Do not claim this local review is an independent security audit.

**The agent should fix findings independently within product permissions.** Do not change product outcomes or take irreversible actions without authorization. If full verification is blocked, report limits rather than marking work done.

The agent must not make up scalability numbers, performance benchmarks, reviews, or check results. Load tests, concurrency tests and threat models are required only when the risk and application justify them.

## Lean tests and clean code

- **Default:** one meaningful end-to-end test per important user journey. Run through the actual product boundary and assert the outcome the user sees. Prefer checking the full flow over testing each function and implementation detail.
- **Add a focused edge/invariant test only when justified:** e.g. data loss, retries and idempotency, money, authorization, concurrency, time boundaries, or a regression the end-to-end flow cannot reliably exercise.
- **Do not write tests just to boost a coverage number.** Avoid duplicate assertions, excessive fixtures, large mock networks, test-only abstractions, snapshots of incidental markup, and one test per helper method.
- **For changes with no user-visible behavior**, such as documentation, use a relevant narrow check instead of inventing a user journey. Configure the project quality policy accordingly and record why the exception applies.
- **Comments:** prefer clear names and simple code. Add a short comment only for a non-obvious reason, invariant, security boundary, or surprising constraint. Avoid narrating the code, redundant docstrings and verbose comments.
- **Review the diff:** remove unnecessary tests and comments before completion. Do not delete a focused regression guard that protects a proven important failure.
- **No universal test count or coverage target.** The test set is judged by risk and behavior, not size. An `e2e` label must reflect a real user-level flow; do not relabel a low-level unit check to pass the gate.

## Review workflow

After implementation and `engine.py verify`:

```bash
python3 .agent/core/quality_gate.py init
# Edit .agent/runs/<task>/quality-draft.json with real review findings and evidence.
python3 .agent/core/quality_gate.py submit .agent/runs/<task>/quality-draft.json
python3 .agent/core/engine.py gate
python3 .agent/core/engine.py finish
```

Acceptable evidence: `check:<configured-check-id>` or `file:<project-relative-path>`. A file reference means the reviewer inspected it; it does **not** prove absence of defects.

`not_applicable` must explain why that dimension is outside this task's scope. For high-risk tasks security and reliability may not be skipped.

Do not log tests inside tracked files during verification; use `.agent/runs/` or an external temporary location. All review/evidence state lives under `.agent/runs/` so it does not invalidate the workspace snapshot.
