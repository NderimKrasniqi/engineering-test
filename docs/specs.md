# Specs

## J-01 — Add equipment
- The user enters a name and an optional description and adds the equipment; it appears in the equipment list and can be chosen when reserving.
- Leading and trailing spaces in the name are removed before it is saved.
- A blank name is refused with a message; nothing is added.
- A name longer than 100 characters or a description longer than 500 characters is refused with a message.
- A name that matches existing equipment after trimming and ignoring case (`Projector` vs ` projector`) is refused with a message that the name is taken; nothing is added.
- With no equipment yet, the equipment list shows an empty state that invites the user to add one.
- **Rules:** `D-02`
- **Excluded:** editing, deleting or archiving equipment; quantities.

## J-02 — Reserve equipment for a date range
- The user chooses one equipment, a start date, an end date and a reserved-by name; the reservation is saved as Active and appears in the reservation list.
- A one-day reservation has the same start and end date.
- An end date before the start date is refused with a message.
- A start date before today is refused with a message.
- A blank reserved-by name, or one longer than 100 characters, is refused with a message.
- Dates that overlap an active reservation of the same equipment are refused with a message that names the conflicting dates; nothing is saved. Example: Active 10–12 blocks 12–14 and 8–10, but allows 13–15.
- Dates that only overlap a cancelled reservation are accepted.
- The same dates on different equipment are accepted.
- When two users submit overlapping reservations of the same equipment at the same time, exactly one is saved and the other is refused as an overlap.
- With no equipment yet, the user is told to add equipment first.
- After a refusal, the entered values stay in the form so the user can correct them.
- **Rules:** `D-01`, `D-03`, `D-04`, `D-05`
- **Excluded:** time-of-day slots; editing a reservation; reserving several equipment in one action.

## J-03 — View reservations
- The list shows every reservation, active and cancelled, with equipment name, start date, end date, reserved-by name and status, sorted by start date (earliest first).
- Cancelled reservations are clearly marked Cancelled.
- The user can filter the list to one equipment, and can return to all equipment.
- With no reservations, or none for the filtered equipment, the list shows an empty state.
- **Rules:** `D-06`
- **Excluded:** search, paging, calendar views, filters other than equipment.

## J-04 — Cancel a reservation
- The user cancels an Active reservation that has not ended; it stays in the list as Cancelled and its dates can be reserved again.
- Cancel is offered only for Active reservations that have not ended (end date today or later).
- A request to cancel a reservation that is already Cancelled or has ended is refused with a message and changes nothing.
- A request to cancel a reservation that does not exist is refused with a message.
- **Rules:** `D-01`, `D-06`; Reservation lifecycle in `docs/domain.md`.
- **Excluded:** undoing a cancellation; a cancellation reason.
