# Project Intelligence — evidence-based repository map

Engineering Stack knows the expected outputs of the user's `product-workflow` plugin, but **does not invent missing files** or treat a path name as proof of architecture.

## Sources

- Product-workflow output catalog from the documented `product-discovery`, `domain-modeling`, `journey-specification`, `solution-design`, `implementation-plan` skills.
- Actual project file inventory from Git tracked + unignored files (fallback to filesystem when not in Git).
- Stack control, quality, autonomy, and learning file locations.

## Agent instruction links

The installer and runtime maintenance append a small marked navigation section to `AGENTS.md` without removing the existing project guidance. `CLAUDE.md` imports `AGENTS.md` when not already linked. Existing instruction files are backed up on first installation; malformed managed sections block instead of overwriting. `doctor` refreshes the map and repairs missing links. These links make the project context discoverable to both Claude Code and Codex.

## Outputs

- `.agent/project-map.md`: short navigational map with **Present / Not present** labels for known outputs, discovered directories, and possible entry points.
- `.agent/project-index.json`: structured inventory of actually discovered files, hashes, categories, directories, known artifacts, and stack controls.

The map is generated; project decisions belong in product documents or explicit decision records. Product artifacts keep their original ownership. Neither map is a substitute for reading current code.

## Lifecycle

- Installer and `engine.py doctor` build the map on setup.
- `engine.py next`, `start`, `verify`, and `maintenance` refresh it when new files appear, move, disappear, or change.
- `engine.py gate` and `finish` **check freshness but never silently refresh**, because the verification evidence must stay tied to the exact state that was checked.
- Manual command: `python3 .agent/core/engine.py map`; standalone checker: `python3 .agent/core/project_intelligence.py --check`.

Secrets, local `.env` files, database files, logs, virtualenvs, caches, generated build output, symlinks, and runtime evidence, generated learning cases/proofs, and clarification logs are excluded from the index. No source code or configuration values are copied into the map; only file metadata and hashes are recorded. Project-specific `.gitignore` should exclude any additional private data.

## Limits

- Recognized outputs from the documented product workflow are **expected locations**, not guaranteed artifacts. Additional product-generated files are discovered by their actual paths; custom semantics should be documented in the project's own docs.
- A possible entry point found by name is only a candidate.
- A folder name does not prove a module's purpose.
- Hashing detects changes but cannot judge whether documentation or implementation is semantically correct.
- The generated map is updated during active engineering work. It is not maintained by a 24/7 background process.
