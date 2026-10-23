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
