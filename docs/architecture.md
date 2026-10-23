# Architecture

## Technology Stack
- **Runtime** — Node.js 24, TypeScript run directly through Node type stripping (no build step).
- **Web** — Express 5, server-rendered HTML with plain forms and Post/Redirect/Get; no client JavaScript.
- **Storage** — SQLite file through the built-in `node:sqlite` module.
- **E2E tests** — Playwright with Chromium against the real server on a temporary database.

## System Architecture
- **Components** — `src/server.ts` starts the app; `src/app.ts` holds routes and request guards; `src/views.ts` renders HTML with the escaping `html` template in `src/html.ts`; `src/booking.ts` owns domain rules and persistence; `src/db.ts` opens the database and creates the schema.
- **Dependency direction** — server → app → (views, booking) → db. Views never touch the database; booking never knows about HTTP.
- **Authority** — the server is authoritative for every rule in `docs/domain.md` and for "today" (server local date). The browser only supplies input.
- **Data** — `equipment(id, name, name_key UNIQUE, description)`; `reservation(id, equipment_id, start_date, end_date, reserved_by, status, created_at)`. Dates are `YYYY-MM-DD` text, so text comparison is date comparison.
- **Key flows** — reserve: validate input → `BEGIN IMMEDIATE` → check overlap with active reservations of the equipment → insert → commit. Cancel: single conditional `UPDATE … WHERE status='active' AND end_date >= today`.
- **Security** — listen on `127.0.0.1` only; refuse requests whose Host is not `127.0.0.1` or `localhost` (DNS rebinding); escape all rendered values; parameterized SQL only; refuse cross-site POSTs (`Sec-Fetch-Site` or `Origin` must match the app); input length caps from `docs/specs.md`.
- **Configuration** — `PORT` (default 3000) and `DB_PATH` (default `data/booking.db`).

## Verification Gates
- `npm run typecheck` (tsc `--noEmit`).
- `npm run test:e2e` (Playwright journeys J-01 to J-04).

## Architecture Decisions
### ADR-01 — Enforce no-overlap inside a write transaction
- **Decision:** The overlap check and the insert run in one `BEGIN IMMEDIATE` SQLite transaction.
- **Why:** D-01 must hold for simultaneous requests; an immediate transaction takes the write lock before the check, so a second writer waits and then sees the first reservation.
- **Consequences:** One SQLite file is the only store; writes are serialized, which is fine for a local app.
- **Rejected alternatives:** Check outside a transaction — race; database trigger — harder to read and to map to a clear user message.

### ADR-02 — Server-rendered HTML instead of a single-page app
- **Decision:** Express renders one page with forms; every change is a POST followed by a redirect.
- **Why:** Four simple journeys do not need client state; fewer moving parts and no client build.
- **Consequences:** Each action reloads the page; richer interactions would need a later redesign.
- **Rejected alternatives:** React SPA with JSON API — more code and a second trust surface for no user benefit.
