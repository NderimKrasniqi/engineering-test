import { DatabaseSync } from 'node:sqlite';
import { expect, test } from '@playwright/test';
import { addEquipment, createEquipmentId, daysFromToday as day, reserve } from './support/booking.ts';

test('a user cancels a reservation ending today and its dates can be reserved again', async ({ page }) => {
  await page.goto('/');
  await addEquipment(page, 'Drone J04');
  await reserve(page, { equipment: 'Drone J04', start: day(0), end: day(0), reservedBy: 'Alex' });

  const reservations = page.getByRole('region', { name: 'Reservations' });
  const alexRow = reservations.getByRole('row').filter({ hasText: 'Drone J04' }).filter({ hasText: 'Alex' });
  await alexRow.getByRole('button', { name: 'Cancel' }).click();
  await expect(alexRow).toContainText('Cancelled');
  await expect(alexRow.getByRole('button', { name: 'Cancel' })).toHaveCount(0);

  await reserve(page, { equipment: 'Drone J04', start: day(0), end: day(0), reservedBy: 'Sam' });
  await expect(reservations.getByRole('row', { name: `Drone J04 ${day(0)} ${day(0)} Sam Active` })).toBeVisible();
});

test('cancelled, ended and unknown reservations cannot be cancelled', async ({ page, request }) => {
  const equipmentId = await createEquipmentId(request, 'Lens J04');
  const db = new DatabaseSync(process.env.E2E_DB_PATH!);
  const ended = db
    .prepare('INSERT INTO reservation (equipment_id, start_date, end_date, reserved_by) VALUES (?, ?, ?, ?) RETURNING id')
    .get(Number(equipmentId), day(-5), day(-1), 'Past user') as { id: number };
  const cancelled = db
    .prepare("INSERT INTO reservation (equipment_id, start_date, end_date, reserved_by, status) VALUES (?, ?, ?, ?, 'cancelled') RETURNING id")
    .get(Number(equipmentId), day(5), day(6), 'Cancelled user') as { id: number };
  db.close();

  await page.goto('/');
  const endedRow = page.getByRole('row').filter({ hasText: 'Past user' });
  await expect(endedRow).toContainText('Active');
  await expect(endedRow.getByRole('button', { name: 'Cancel' })).toHaveCount(0);

  for (const id of [ended.id, cancelled.id]) {
    const response = await request.post(`/reservations/${id}/cancel`, { maxRedirects: 0 });
    expect(response.status()).toBe(409);
    expect(await response.text()).toContain('This reservation is already cancelled or has ended.');
  }

  const unknown = await request.post('/reservations/999999/cancel', { maxRedirects: 0 });
  expect(unknown.status()).toBe(404);
});
