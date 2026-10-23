<!-- ENGINEERING-STACK:BEGIN -->
## Engineering Stack — Project Navigation and Execution

- The user and `product-workflow` documents own WHAT. The agent owns HOW: readable, maintainable, secure, and appropriately scalable code.
- Ask about material missing product decisions; never invent requirements. Make ordinary engineering decisions independently.
- Read `.agent/project-map.md` first to find approved product artifacts and actual project files.
- Use `.agent/project-index.json` for indexed paths; inspect real source before changes. Missing files are not assumed to exist.
- Respect the user-selected continuation mode in `.agent/core/operation.json`.
- Implement with few meaningful E2E user-flow tests, justified edge-case guards, and minimal comments.
- Run the Engineering Stack verification, quality gate, and learning maintenance before completing tasks.
- Delegate selectively through native subagents; main owns integration and completion. Read `.agent/core/DELEGATION.md` and respect `.agent/core/delegation.json`.
- Use `.agent/core/CONTRACT.md`, `AUTONOMY.md`, `QUALITY_STANDARD.md` and `PROJECT_INTELLIGENCE.md` when relevant.
<!-- ENGINEERING-STACK:END -->

## Planning workflow

This project is planned with the workflow skills: product-discovery → domain-modeling → journey-specification → solution-design → implementation-plan. The documents below are the source of truth. This file only points to them; it never duplicates their content.

### Documents

| Document | What it is | What's inside | Stable IDs | Owned by |
|---|---|---|---|---|
| `docs/product.md` | The product contract: why this exists and what it does | Problem & solution, principles, product journeys, material constraints, first release scope, deferred items | `J-xx` (`### J-01 — …`) | product-discovery |
| `docs/domain.md` | The business rules and vocabulary | Canonical terms, core invariants, state models (lifecycle tables), boundaries | `D-xx` (`- **D-01 — …**`) | domain-modeling |
| `docs/specs.md` | Observable behavior, one section per journey | Success paths, failure/edge cases, authorization, referenced rules, exclusions | `## J-xx` sections | journey-specification |
| `docs/architecture.md` | How the system is built, right now | Technology stack, system architecture, authority/trust boundaries, verification gates, decisions | `ADR-xx` (`### ADR-01 — …`) | solution-design |
| `docs/implementation-plan.md` | The build order | Phases; one line per task plus a `Done when:` acceptance line; `[x] … ✅` when complete | `TASK-xx` | implementation-plan |
| `.workflow/tasks.json` | Machine bookkeeping for the plan (never edit by hand into Markdown) | Per task: `deps`, `refs`, one `releaseGate`, temporary `gates` | `TASK-xx` keys | implementation-plan |
| `docs/engineering-principles.md` | How code is written, tested, and reviewed | Development, quality, testing, security, Definition of Ready/Done | — | the team |
| `tools/validate-workflow.py` | Structural checker for all of the above | Run `python3 tools/validate-workflow.py` after changing any document | — | — |

### Where to find what

| Question | Look in |
|---|---|
| Why are we building this? Who is it for? | `docs/product.md` → Problem & Solution |
| Is feature X in scope? | `docs/product.md` → First Useful Release / Deferred |
| What does term X mean exactly? | `docs/domain.md` → Canonical Language |
| What must always be true? | `docs/domain.md` → Core Invariants (`D-xx`) |
| What states can X be in, and what moves it between them? | `docs/domain.md` → State Models |
| What should happen when a user does X, including errors? | `docs/specs.md` → the `J-xx` section |
| What tech do we use, and which component is authoritative for what? | `docs/architecture.md` → Technology Stack / System Architecture |
| Why was technical decision X made? | `docs/architecture.md` → Architecture Decisions (`ADR-xx`) |
| What should I build next, and when is it done? | `docs/implementation-plan.md` → first unchecked task whose deps are all `[x] … ✅`; its `Done when:` line |
| What does task X depend on / which sources does it trace to? | `.workflow/tasks.json` → `deps` / `refs` |
| How should I test this? | `docs/engineering-principles.md` → Testing |

### Working rules

- Read narrowly: load the task line, its `Done when:`, and only the `J-xx` / `D-xx` / `ADR-xx` sections its `refs` name. Expand only for a concrete ambiguity.
- Never invent a product, domain, or design decision while coding. If one is missing, stop and resolve it in the owning document via its skill.
- When truth changes, update the one document that owns it (table above) and run the validator. Don't let docs, code, and tests tell different stories.
- Work on one task at a time; do not automatically start the next.
