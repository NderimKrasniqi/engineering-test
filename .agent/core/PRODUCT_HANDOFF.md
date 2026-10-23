# Product workflow handoff

Use the user's existing `product-workflow` skills and their source documents.

When `.workflow/tasks.json` contains a task object map, interpret it as the product plugin's metadata and read `docs/implementation-plan.md` for titles, acceptance criteria (`Done when:`), and checkbox status. The plan stays authoritative; `finish` signs off the checkbox after a verified task, rather than creating a competing backlog.

This adapter is tested against the documented layout demonstrated in Kitroom. Other plugin versions may vary and must be validated against the actual installed plugin validator. This release does not claim the Claude Code plugin ran.

A legacy tasks-list format is also supported for older projects. Do not convert one format into the other automatically. Codex can use the product artifacts; its ability to invoke Claude-only plugin commands is not assumed.
