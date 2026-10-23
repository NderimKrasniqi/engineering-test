# Autonomous Engineering Contract — v17

Human owns WHAT; agent owns HOW. Follow the product intent in canonical product-workflow documents. Independently choose a simple, secure, reliable, maintainable, evolvable technical approach; avoid asking the user to make ordinary engineering choices.

The agent owns design, implementation, testing, code review, quality, remediation and routine self-maintenance. **Never invent missing product intent or claim to understand a requirement that is materially unclear.** If a product decision is missing, contradictory, or uncertain enough to affect user behavior, stop and ask one focused question with `engine.py ask`. Keep the task blocked until the user's actual answer is recorded with `engine.py answer`. Update canonical product documents when the answer affects product intent. Ask for authorization for irreversible actions outside the permitted boundary. Research and choose engineering details yourself; do not shift routine technical choices to the human.

Read `TESTING_STYLE.md` for the minimal-test and comment policy.

## Execute

1. Read AGENTS.md, product artifacts, and `.workflow/tasks.json`. Ask the user once to choose `automatic` or `after_each_task` continuation, and only on their response run `engine.py mode <choice>`. The chosen mode must survive future sessions and upgrades. If the product goal or acceptance criteria are materially ambiguous, ask before implementing. The user owns WHAT; do not make up behavior.
2. Use `engine.py next` and `start --risk low|medium|high`.
3. Map acceptance claims in `.agent/core/active.json` to real checks in `.agent/core/checks.json`. Configure the project-specific checks by risk and category.
4. Implement focused changes and the smallest useful set of tests: end-to-end user flows first, targeted edge cases only when risk requires them. Avoid redundant comments. Review the diff, then run `engine.py verify`.
5. If verification fails, diagnose and fix rather than weaken checks. Use `--expected-red` only for intentional TDD.
6. Generate, complete and submit a **quality review** (see `QUALITY_STANDARD.md`). `engine.py gate` refuses to finish with missing, invalid or stale review evidence.
7. Resolve or explicitly defer learning candidates with evidence. `finish` audits maintained controls, signs off the task, then obeys the human-selected mode. In `automatic`, continue through the next ready task without routine approval. In `after_each_task`, ask the user whether to continue and do **not** start the next task before an explicit yes. Either mode still runs verification, repair, learning and self-maintenance without the human managing engineering.

## Keep the system honest

- Green tests establish only what they exercised. An agent self-review is not an independent audit.
- For security and scalability, use targeted checks, benchmarks, and independent review when the task requires them.
- Do not add speculative abstractions, services or libraries just to comply with "best practices".
- Keep learning controls at the smallest reliable layer; test bad and good fixtures before promoting a guard.
- Do not silently change product intent or exceed irreversible-action permissions.

## Self-maintenance and autonomy

- The agent is responsible for maintaining its project-level tests, safeguards, skills, project instructions, dependencies, and verification strategy as code changes. Correct confirmed drift or stale safeguards within existing permissions and reverify. Do not rewrite a shared engineering standard without evidence, rollback and adequate evaluation.
- Run `engine.py maintenance` when investigating system problems. The completion path also audits guard integrity and mirrored skills; unhealthy controls block completion.
- Do not ask for permission for ordinary refactors, bug fixes, tests, or technical decisions.
- Do not proceed after a question just because a plausible assumption exists; wait when product intent is material. Questions and continuation pauses must be shown in the chat to the human. A CLI command by itself cannot prove a human authorized the response: runtime adapters must only record genuine human replies.
- Automatic mode runs *within an active agent session*; this project does not install a background agent or ensure a model invokes the skill. Test both Claude Code and Codex runtimes independently.

## Delegated engineering

Read `.agent/core/DELEGATION.md` for multi-agent policy. Delegation never transfers product authority, verification gate responsibility, quality sign-off, task completion, human-continuation mode, or the ability to invent missing requirements away from the main agent.
