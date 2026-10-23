# Autonomy, questions and self-maintenance — v17

**Human owns product intent, agent owns engineering implementation and upkeep.**

## Continuation: one human choice

Before beginning implementation, ask the user **once** how tasks should proceed:

- `automatic`: after a task is complete and verified, inspect the next ready task and proceed. Never ask for routine technical approval.
- `after_each_task`: complete and verify a task, then ask **Continue with the next task?** and wait for the user answer. A rejected continuation keeps the project paused; a yes releases exactly that pause.

Call `python3 .agent/core/engine.py mode automatic` or `mode after_each_task` only in response to the human's choice. Changing the mode later also requires their explicit request. A pending after-task pause cannot be bypassed by switching modes. The file `.agent/core/operation.json` stores the choice and upgrades preserve it.

## Ask rather than invent

When an unknown may change product behavior, scope or user expectations, or the product documents contradict each other, ask a concise, specific question. Do not implement speculative behavior. Use:

```bash
python3 .agent/core/engine.py ask --question 'Can a borrower renew an overdue loan?' --why 'The current product spec has no renewal rule and both behaviors affect users.'
# Stop and show the question to the human. Resume only after an actual response.
python3 .agent/core/engine.py answer --answer 'No; overdue loans must be returned first.'
```

The `ask` command blocks starting, verification and completion until an answer is recorded. The Claude Stop hook lets the agent stop to ask. Product answers are appended to `.agent/decisions/clarifications.jsonl` for context; update product-workflow documents if they alter canonical requirements. Never invent an answer or treat the tool command as proof of user identity.

Research and resolve technical uncertainty, use reasonable reversible implementation defaults only where product behavior remains unchanged, and request authorization before high-impact irreversible action outside the authorized scope.

## Self-maintenance

After each task, the agent audits verification coverage, protects useful regression guards, checks whether new lessons are justified, repairs broken project tooling and documents engineering decisions. The machine gate checks the integrity of promoted guards and parity of installed skill copies before completion; the model performs investigation and repairs.

Useful learning requires confirmed root cause, the smallest preventive control, bad/good replay evidence, and a later-task observation. Reject redundant or harmful lessons. Do not add more tests or comments just to appear thorough. Shared/global stack changes should be evaluated on multiple projects and have rollback. No background maintenance runs while the agent is idle.

## Commands

```bash
python3 .agent/core/engine.py mode
python3 .agent/core/engine.py next
python3 .agent/core/engine.py maintenance
python3 .agent/core/engine.py continue --decision yes
python3 .agent/core/engine.py continue --decision no
python3 .agent/core/engine.py doctor
```

The CLI cannot authenticate the person who set the mode or answered a question. The agent adapter must relay the user's real message, and tests of actual Claude Code and Codex behavior remain necessary.
