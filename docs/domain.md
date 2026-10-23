# Domain

## Canonical Language
- **Equipment** — one physical item that can be reserved; it has a name and an optional description.
- **Reservation** — a booking of one equipment for a date range under a reserved-by name.
- **Date range** — whole calendar days from a start date to an end date, both inclusive.
- **Reserved by** — the free-text name of the person the reservation is for.
- **Active reservation** — a reservation in status Active; only active reservations block dates.
- **Cancelled reservation** — a reservation in status Cancelled; it stays visible and blocks nothing.
- **Ended** — a reservation whose end date is before today.
- **Overlap** — two date ranges share at least one day: each starts on or before the day the other ends.
- **Today** — the current calendar date where the app runs.

## Core Invariants
- **D-01 — No overlapping active reservations.** For any one equipment, no two active reservations overlap; this holds even when two reservations are made at the same time.
- **D-02 — Unique equipment name.** Each equipment has a non-blank name that no other equipment has, compared after trimming spaces and ignoring letter case.
- **D-03 — Valid date range.** Every reservation has an end date on or after its start date.
- **D-04 — No reservations in the past.** A reservation can only be made with a start date of today or later.
- **D-05 — Reservation identity is fixed.** A reservation always refers to the same equipment, date range and reserved-by name; it is never edited, only cancelled.
- **D-06 — Reservations are kept.** A reservation is never removed; cancellation changes its status only.

## State Models
### Reservation lifecycle
| From | Event / actor | Guard | To |
|---|---|---|---|
| — | Reserve / user | Equipment exists; reserved-by is not blank; D-03; D-04; no overlap with an active reservation of the same equipment (D-01) | Active |
| Active | Cancel / user | Reservation has not ended | Cancelled |

Terminal states: Cancelled. An Active reservation that has ended stays Active and can no longer be cancelled. Reversal: intentionally unsupported; a cancelled reservation cannot be reactivated, but the user can make a new reservation.

### Equipment lifecycle
| From | Event / actor | Guard | To |
|---|---|---|---|
| — | Add / user | D-02 | Exists |

Terminal states: none. Editing and deleting equipment are out of scope.
