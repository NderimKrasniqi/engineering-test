# Product
**Status:** Approved

## Problem & Solution
A person or small group shares physical equipment and needs to know who has which item on which days, without double bookings. A small local web app keeps the equipment list and the reservations, and refuses any reservation that would overlap an active reservation of the same item.

## Principles
- The same equipment never has overlapping active reservations.
- Keep the product small: one local app, no accounts, no roles.

## Product Journeys
### J-01 — Add equipment
A user adds a piece of equipment with a unique name and an optional description, and it becomes available to reserve.

### J-02 — Reserve equipment for a date range
A user reserves one piece of equipment for whole days under a "reserved by" name; the app refuses the reservation if the dates overlap an active reservation of that equipment.

### J-03 — View reservations
A user sees all reservations with equipment, dates, name and status, sorted by start date, and can filter by equipment.

### J-04 — Cancel a reservation
A user cancels an active reservation that has not ended; it stays visible as Cancelled and its dates become free.

## Material Constraints
- Runs locally and is used through a web browser.
- No login: everyone who opens the app can do every action.
- One equipment record is one physical item; there is no quantity or stock model.
- Reservations use whole days; start and end dates are both inclusive.
- A reservation cannot start before today; the end date is on or after the start date; there is no maximum length.

## First Useful Release
- J-01 to J-04 as described above.

## Deferred
- Accounts, roles and approvals.
- Editing reservations; editing or deleting equipment.
- Undoing a cancellation.
- Time-of-day slots and same-day handover.
- Notifications.

## Downstream Ownership
- Exact overlap and status rules: domain-modeling.
- Error messages, empty states and filter behavior: journey-specification.
- Technology, storage and protection against two simultaneous conflicting reservations: solution-design.
