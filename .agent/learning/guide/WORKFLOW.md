# Learning workflow — Stage 2

A failure signal is **not** a lesson. A diagnosis is **not** proof. A successful
regression replay is **not** proof that a later coding agent used the lesson.

## State transitions

`candidate → investigating → proposed → enforced → reuse observed`

A candidate may instead be `deferred` with a meaningful reason. Critical manual
incidents cannot be deferred with this tool. Cases are stored in
`.agent/learning/cases/` and guard replay evidence in `.agent/learning/proofs/`.
Both folders are versionable; workspace hashing excludes the metadata while
continuing to track the actual source code and guards.

## Trigger

`engine.py verify` records failed checks and automatically scans for **the same
check/output across at least two distinct workspace states and two runs**.
Repeated identical results against unchanged code do not trigger a candidate.
`verify --expected-red` marks a deliberate TDD red step and does not add learning
signals; it still fails verification. Tooling does not infer root causes.

For a confirmed high-impact defect, use `learning_engine.py incident ...` with
an existing evidence file. This creates a candidate, not a conclusion.

## Investigate / fix

1. `python3 .agent/core/learning_engine.py scan`
2. `python3 .agent/core/learning_engine.py status`
3. `python3 .agent/core/learning_engine.py triage L-... --decision investigate --reason "..."`
4. Reproduce and diagnose the root cause. Choose a *small* durable control:
   architecture, types, static-check, test, workflow, or instruction.
5. `python3 .agent/core/learning_engine.py propose L-... --cause "..." --layer test --guard-path tests/test_regression.py --argv-json '["python3","-m","unittest","tests.test_regression"]'`
6. Create two **isolated** checkout/fixture directories: one reproducing old bad
   behavior, the other with the corrected behavior. Both must contain the exact
   same guard file as the active repository.
7. `python3 .agent/core/learning_engine.py prove L-... --bad-root /tmp/checkout-bad --good-root /tmp/checkout-fixed`
8. Examine why the negative command failed. Do not accept an unrelated failure.
9. `python3 .agent/core/learning_engine.py promote L-...`
10. Rerun the project's main verification after changing source or tests.

Promoting requires a negative failure and positive pass with **the same guard**.
Changing the guard after proof invalidates that evidence.

## Later use

For a different future task, verify and finish it through `engine.py`. Then use:

`python3 .agent/core/learning_engine.py reuse L-... --task NEW-TASK --evidence .agent/runs/NEW-TASK/ACTUAL.json --notes "..."`

The command requires a completed registry task and a full, passing verification
run generated after the guard proof. It records **observation**, not causality.
We cannot infer that the agent selected or obeyed the lesson from this record.
A blinded same-task baseline evaluation in real Claude/Codex remains Stage 3.

## Keep learning safe

- Do not create lessons for expected red tests, single typos, or resolved transients.
- If a candidate is noise, defer it with a specific explanation; no silent discard.
- Do not automatically promote general/shared rules from a project incident.
- Prefer enforceable controls to long prompts; do not add redundant skills.
- Review fixtures/check commands before running them; these are local code execution.
- Guard replay checks exit codes and file identity; it cannot establish that the
  failure was semantically the intended one. Review the output separately.
- A local agent can edit files/evidence; this is not a tamper-proof security boundary.
- One agent per worktree. Use separate worktrees for parallel tasks.

## v20 guard activation and reuse

Before promotion, add the proven guard argv as exactly one low-risk project check in `.agent/core/checks.json`. This makes the guard execute on subsequent verification runs, not just in the old bug fixture. If it isn't registered, promotion is blocked. If the check or guard changes later, self-maintenance reports it as stale and task completion is blocked until the issue is investigated and re-proven. Keep the check relevant and fast; do not use large numbers of redundant tests.

The reuse checker accepts both the older list-style `.workflow/tasks.json` and the canonical product-workflow map backed by `docs/implementation-plan.md`. A reuse observation requires completed task status, the actual latest passing verification run, and proof that the promoted guard was executed. This is observed reuse, **not evidence of a causal improvement**; a fresh agent baseline comparison is still required for that claim.
