import type { Equipment, EquipmentInput, Reservation, ReservationInput } from './booking.ts';
import { isCancellable, limits } from './booking.ts';
import { html, SafeHtml } from './html.ts';

const styles = `
  :root { color-scheme: light dark; --border: #8884; --muted: #888; --danger: #c0392b; }
  * { box-sizing: border-box; }
  body { font-family: system-ui, sans-serif; margin: 0 auto; max-width: 960px; padding: 24px 16px; line-height: 1.4; }
  h1 { margin-top: 0; }
  section { border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 24px; }
  h2 { margin-top: 0; font-size: 1.2rem; }
  form.stack { display: grid; gap: 12px; max-width: 420px; }
  label { display: grid; gap: 4px; font-weight: 600; }
  input, select, textarea, button { font: inherit; padding: 6px 8px; }
  .table-wrap { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); }
  .error { color: var(--danger); font-weight: 600; }
  .empty { color: var(--muted); }
  .visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
  form.filter { display: flex; gap: 8px; align-items: end; flex-wrap: wrap; margin-bottom: 12px; }
`;

export type FormState<T> = { values: T; error?: string };

export type PageModel = {
  today: string;
  equipment: Equipment[];
  reservations: Reservation[];
  filter?: Equipment;
  reservationsError?: string;
  equipmentForm: FormState<EquipmentInput>;
  reservationForm: FormState<ReservationInput>;
};

export const emptyEquipmentForm: FormState<EquipmentInput> = { values: { name: '', description: '' } };

export const emptyReservationForm: FormState<ReservationInput> = {
  values: { equipmentId: '', startDate: '', endDate: '', reservedBy: '' },
};

const statusLabels: Record<Reservation['status'], string> = { active: 'Active', cancelled: 'Cancelled' };

function errorMessage(error: string | undefined): SafeHtml {
  return error ? html`<p class="error" role="alert">${error}</p>` : html``;
}

function equipmentSection({ equipment, equipmentForm }: PageModel): SafeHtml {
  const list = equipment.length
    ? html`<ul>${equipment.map(
        (item) => html`<li><strong>${item.name}</strong>${item.description ? html` — ${item.description}` : ''}</li>`,
      )}</ul>`
    : html`<p class="empty">No equipment yet. Add the first item below.</p>`;

  return html`<section aria-labelledby="equipment-heading">
    <h2 id="equipment-heading">Equipment</h2>
    ${list}
    <form class="stack" method="post" action="/equipment">
      ${errorMessage(equipmentForm.error)}
      <label>Name
        <input name="name" required maxlength="${limits.name}" value="${equipmentForm.values.name}">
      </label>
      <label>Description (optional)
        <textarea name="description" maxlength="${limits.description}" rows="2">${equipmentForm.values.description}</textarea>
      </label>
      <button type="submit">Add equipment</button>
    </form>
  </section>`;
}

function reservationFormSection({ today, equipment, reservationForm }: PageModel): SafeHtml {
  const { values, error } = reservationForm;
  const content = equipment.length
    ? html`<form class="stack" method="post" action="/reservations">
        ${errorMessage(error)}
        <label>Equipment
          <select name="equipmentId" required>
            <option value="">Choose equipment</option>
            ${equipment.map(
              (item) =>
                html`<option value="${item.id}" ${String(item.id) === values.equipmentId ? html`selected` : ''}>${item.name}</option>`,
            )}
          </select>
        </label>
        <label>Start date
          <input type="date" name="startDate" required min="${today}" value="${values.startDate}">
        </label>
        <label>End date
          <input type="date" name="endDate" required min="${today}" value="${values.endDate}">
        </label>
        <label>Reserved by
          <input name="reservedBy" required maxlength="${limits.reservedBy}" value="${values.reservedBy}">
        </label>
        <button type="submit">Reserve</button>
      </form>`
    : html`${errorMessage(error)}<p class="empty">Add equipment before you make a reservation.</p>`;

  return html`<section aria-labelledby="new-reservation-heading">
    <h2 id="new-reservation-heading">New reservation</h2>
    ${content}
  </section>`;
}

function reservationFilter({ equipment, filter }: PageModel): SafeHtml {
  if (!equipment.length) return html``;
  return html`<form method="get" action="/" class="filter">
    <label>Show equipment
      <select name="equipment">
        <option value="">All equipment</option>
        ${equipment.map(
          (item) => html`<option value="${item.id}" ${item.id === filter?.id ? html`selected` : ''}>${item.name}</option>`,
        )}
      </select>
    </label>
    <button type="submit">Filter</button>
  </form>`;
}

function reservationsSection(model: PageModel): SafeHtml {
  const { reservations, filter, today, reservationsError } = model;
  const rows = reservations.map(
    (r) => html`<tr>
      <td>${r.equipmentName}</td>
      <td>${r.startDate}</td>
      <td>${r.endDate}</td>
      <td>${r.reservedBy}</td>
      <td>${statusLabels[r.status]}</td>
      <td>${isCancellable(r, today)
        ? html`<form method="post" action="/reservations/${r.id}/cancel">
            ${filter ? html`<input type="hidden" name="filter" value="${filter.id}">` : ''}
            <button type="submit">Cancel</button>
          </form>`
        : ''}</td>
    </tr>`,
  );

  return html`<section aria-labelledby="reservations-heading">
    <h2 id="reservations-heading">Reservations</h2>
    ${errorMessage(reservationsError)}
    ${reservationFilter(model)}
    ${reservations.length
      ? html`<div class="table-wrap">
          <table>
            <thead><tr><th>Equipment</th><th>Start date</th><th>End date</th><th>Reserved by</th><th>Status</th><th><span class="visually-hidden">Actions</span></th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`
      : html`<p class="empty">${filter ? `No reservations for ${filter.name}.` : 'No reservations yet.'}</p>`}
  </section>`;
}

export function bookingPage(model: PageModel): SafeHtml {
  return html`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Equipment booking</title>
  <style>${new SafeHtml(styles)}</style>
</head>
<body>
  <h1>Equipment booking</h1>
  ${equipmentSection(model)}
  ${reservationFormSection(model)}
  ${reservationsSection(model)}
</body>
</html>`;
}
