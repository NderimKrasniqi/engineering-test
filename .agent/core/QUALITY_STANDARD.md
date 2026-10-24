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

**Review freshness:** `quality_gate.py init` pins the current verified workspace, task,
check configuration and policy in the draft **before** a reviewer begins. For high-risk
tasks, send that snapshot to the native independent reviewer; require the reviewer to
report the same snapshot ID and a session ID if their runtime actually exposes one. If the reviewer requests code
changes (even small fixes), make them, rerun `engine.py verify`, create a NEW review
request and ask the independent reviewer to review the final change (a focused patch
re-review is enough). Never update an old review's run ID or hashes to make it pass.
`quality_gate.py submit` rejects an old review whose run ID was changed but whose workspace
hash still points to the old snapshot. It cannot detect a hand edit that rewrites both, so
never do this. See `docs/TRUST_MODEL.md` in the Engineering Stack repository.
When native Claude Code/Codex agents do **not** expose reliable session IDs, do not
invent them. Leave unavailable IDs as `null` and fill `reviewer_invocation` with the
actual runtime, tool call, completed status, and a concrete transcript/tool-handle
reference to the native reviewer invocation. Example (only if observed):

```json
{
  "reviewer_role": "engineering-reviewer",
  "review_method": "independent-agent-review",
  "reviewer_session_id": null,
  "implementer_session_id": null,
  "reviewer_invocation": {
    "runtime": "claude-code",
    "tool": "Agent",
    "invocation_reference": "Claude Code transcript: Agent Independent review of TASK-01 finished",
    "status": "completed",
    "session_ids_unavailable": true
  }
}
```

For Codex use `runtime: codex`, `tool: spawn_agent` and its actual observed
invocation reference. The gate still requires a named independent reviewer,
verified snapshot and quality evidence, and blocks missing or malformed
attestations. **An agent-authored invocation reference is not authenticated runtime
proof.** Report that limitation honestly. If distinct genuine session IDs exist,
use them instead of the fallback; do not invent IDs or claim cryptographic proof.

```bash
python3 .agent/core/quality_gate.py init
# Edit .agent/runs/<task>/quality-draft.json with real review findings and evidence.
python3 .agent/core/quality_gate.py submit .agent/runs/<task>/quality-draft.json
python3 .agent/core/engine.py gate
python3 .agent/core/engine.py finish
```

**Review requests (v0.21.0):** `init` creates a single-use review request with a unique
`review_request_id` in `.agent/runs/<task>/review-request.json` and in the draft. Pass that
ID and the snapshot ID to the reviewer. `submit` accepts only the current open request for
the latest verification run and then marks it consumed. A new `init` or a new `verify`
supersedes an open request. `gate` rejects a review that was written without `submit`,
edited after submission, or bound to an older request. Reviews and drafts from before
v0.21.0 (schema 1) must be reinitialized with `init`. Replacing the engineering core during
an upgrade changes the workspace: run `verify` again, then `init` and a new review. Request records are on an agent-writable filesystem: they catch mistakes and
shortcuts but are **not** authenticated and cannot stop deliberate forgery.

**Final verification (v0.21.0):** `finish` re-runs every required check of the task before
it marks the task done. It blocks on a nonzero exit, a timeout, an execution error or a
workspace change before or during the run. It never changes the accepted review or its
verification run. It writes one record per verification run,
`.agent/runs/<task>/final-verification/<run_id>.json`, with status `running` before any
check starts and `passed` or `failed` after. A `running`, `failed`, unreadable or invalid
record makes that verification run ineligible: `gate`, `finish`, `quality_gate.py init` and
`submit` reject it. To recover, fix the cause, run `verify` again, run `init`, obtain a new
review and `submit` it. The old review never applies to the new run, and the failed record
stays. A missing record means no attempt was made; deleting a record is tampering and is not
detected. Completion therefore takes about as long as one more verification, and a flaky
check can block completion; fix the check, because a retry on the same run is blocked.

**Assurance:** `gate`, `show` and `finish` print `Review assurance: declared`. All reviewer
evidence methods, for Claude Code and Codex, are self-declared. Open findings of any
severity are printed; open medium and low findings do not block completion.

Acceptable evidence: `check:<configured-check-id>` or `file:<project-relative-path>`. A file reference means the reviewer inspected it; it does **not** prove absence of defects.

`not_applicable` must explain why that dimension is outside this task's scope. For high-risk tasks security and reliability may not be skipped.

Do not log tests inside tracked files during verification; use `.agent/runs/` or an external temporary location. All review/evidence state lives under `.agent/runs/` so it does not invalidate the workspace snapshot.
