# Implementation Plan
**Status:** Approved

## Phase 1 — The app runs locally and is testable
- [x] TASK-01 Scaffold the server, database schema, page shell and E2E harness ✅
  Done when: `npm start` serves the booking page on 127.0.0.1, the schema is created in the configured database file, and `npm run typecheck` and a Playwright smoke test pass.

## Phase 2 — Core booking loop
- [x] TASK-02 Add equipment with unique names and refuse cross-site form posts ✅
  Done when: a user adds equipment and sees it listed; blank, too-long and duplicate (trimmed, case-insensitive) names are refused with a message (J-01, D-02); a POST from another origin is refused.
- [x] TASK-03 Reserve equipment for a date range with the no-overlap guard ✅
  Done when: a user reserves equipment and sees it in the reservation list as Active; invalid ranges, past starts, blank names and overlaps with active reservations are refused with a message and kept form values; simultaneous overlapping requests save exactly one (J-02, D-01, D-03, D-04, ADR-01).
- [x] TASK-04 Show all reservations sorted by start date with an equipment filter ✅
  Done when: the list shows active and cancelled reservations with equipment, dates, name and status sorted by start date, filters to one equipment and back, and shows empty states (J-03).
- [x] TASK-05 Cancel an active reservation that has not ended ✅
  Done when: cancel marks the reservation Cancelled, frees its dates for a new reservation, and is not offered or accepted for cancelled or ended reservations (J-04, D-06).

## Phase 3 — Release
- [x] TASK-06 Verify the full release against all journeys ✅
  Done when: typecheck and the E2E suite for J-01 to J-04 pass, and code and security review have no unresolved findings.
