# Multi-agent delegation — v19

Engineering Stack **owns the policy and evidence**; Claude Code and Codex **own agent execution**. There is no custom model loop. The main agent remains responsible for engineering decisions, integrating all work, quality review, verification, learning, task completion, and asking product questions.

## Default roles

- **Main**: Claude Opus (`medium`), or Codex GPT-6.1 Sol (`medium`) when available. Choose in the session UI or CLI; this package does not silently override your selected main model.
- **Explorer**: Haiku, or Codex Luna; read-only mapping and analysis.
- **Implementer**: Sonnet, or Codex Sol; one bounded change.
- **Reviewer**: Sonnet High, or Codex Sol High; inspect integrated code without editing.
- **Investigator**: Opus High, or Codex Sol High; high-risk investigation.

Use available model equivalents when a provider or plan does not offer a listed model. The roles and model defaults live in `.agent/core/delegation.json`. Regenerate the platform agents with `python3 .agent/core/delegation.py sync --replace` after an intentional role-policy change. Check integrity with `sync --check`.

## Route by value, not habit

- Small, low-risk edit: main agent directly.
- Normal feature: implementer if delegation adds value.
- Significant feature: implementer then independent reviewer.
- High-risk change: investigator when analysis is difficult; implementer and independent review when justified.
- Read-heavy exploration: explorer before implementation when useful.
- Do not spawn multiple writing agents into the same files. The initial cap is **two concurrent subagents**, no nested delegation; reviewers operate after implementation on integrated code.
- In Claude, a worktree may start from the default branch rather than the main session's HEAD. Confirm the base before delegating dependent edits or remove isolation for that task. Codex subagents inherit parent sandbox permissions; written "read-only" instructions alone do not impose tool-level read-only protection.

## Every delegation needs a contract

The main agent provides the goal, acceptance criteria, risk, relevant file references, allowed scope, base revision/dependencies, output format, and expected checks. Subagents report concise changed paths and evidence. The main agent verifies integrated code and updates task state; a subagent's green tests are not the final completion gate.

## Product, learning and continuation

Do not invent product behavior. Report material ambiguities to main, which asks the human and records the answer. Do not change the human-selected `automatic` or `after_each_task` mode. A subagent cannot approve itself or bypass `.agent/core/engine.py gate` / `finish`. Learning safeguards remain controlled by `.agent/core/learning_engine.py` and apply across sessions; optional model-local memory is not our source of truth.

## Runtime setup

- Claude: `.claude/agents/engineering-*.md`; merge `.claude/settings.delegation.example.json` into existing `.claude/settings.json` if you want enforced session limits. Run `claude --model opus --effort medium` on installations supporting these options. Use `claude plugin validate .claude/agents` to check the agent format when available.
- Codex: `.codex/agents/engineering-*.toml`; merge `[agents]` from `.codex/config.engineering.example.toml` into existing `.codex/config.toml` or your personal config, without erasing other settings. The examples are **not automatically active runtime configuration**. Select your available main model in Codex. Inspect spawned agents in `/subagents` where available.
- The installer keeps existing settings files untouched to avoid privilege changes or clobbering unrelated configuration. The doctor/check commands validate generated role files; runtime loading and chosen models must still be confirmed in real Claude/Codex sessions.

## Adoption experiment

Compare single-agent, one-worker, and worker-plus-review on the same tasks, with clean starts, identical requirements, E2E-first checks, security and quality outcomes, no excessive tests/comments, total cost, and human questions. Only increase agent count when repeatable evidence supports it.

## v20 high-risk completion safeguard

For a high-risk task, with `require_independent_review_for_high_risk: true`, the quality gate rejects `agent-self-review`. A separate `engineering-reviewer` agent must review the **integrated diff** after implementation. Record the result in `.agent/runs/<task>/quality-review.json` using `review_method: independent-agent-review`, `reviewer_role: engineering-reviewer`, and the distinct, actual implementer and reviewer session IDs. All quality dimensions, executed checks, and findings remain required.

The gate validates this attestation's structure and relationship to the verification run. **A JSON field is not authenticated reviewer identity**: a malicious or misconfigured agent can forge these fields. Do not claim cryptographically proven independence until the Claude/Codex runtime supplies a trusted reviewer event or receipt. The main thread still owns task completion and any unresolved product clarification.

`delegation.json` is the single policy source for small-task delegation and high-risk review. If you intentionally change it, regenerate definitions with `delegation.py sync --replace`, examine backups, and reverify affected tasks. The `maintenance` command restores missing generated definitions but never overwrites customized existing files without review.
