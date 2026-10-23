import { expect, test } from '@playwright/test';
import { addEquipment, createEquipmentId, daysFromToday, reserve } from './support/booking.ts';

test('a user reserves equipment and overlapping dates are refused', async ({ page }) => {
  const day = daysFromToday;
  await page.goto('/');
  await addEquipment(page, 'Camera J02');
  await addEquipment(page, 'Tripod J02');

  await reserve(page, { equipment: 'Camera J02', start: day(10), end: day(12), reservedBy: 'Alex' });
  const reservations = page.getByRole('region', { name: 'Reservations' });
  await expect(reservations.getByRole('row', { name: `Camera J02 ${day(10)} ${day(12)} Alex Active` })).toBeVisible();

  await reserve(page, { equipment: 'Camera J02', start: day(12), end: day(14), reservedBy: 'Sam' });
  const form = page.getByRole('region', { name: 'New reservation' });
  await expect(form.getByRole('alert')).toHaveText(`Camera J02 is already reserved from ${day(10)} to ${day(12)}.`);
  await expect(form.getByLabel('Reserved by')).toHaveValue('Sam');
  await expect(form.getByLabel('Start date')).toHaveValue(day(12));

  await reserve(page, { equipment: 'Camera J02', start: day(13), end: day(13), reservedBy: 'Sam' });
  await reserve(page, { equipment: 'Tripod J02', start: day(10), end: day(12), reservedBy: 'Sam' });
  await expect(reservations.getByRole('row', { name: `Camera J02 ${day(13)} ${day(13)} Sam Active` })).toBeVisible();
  await expect(reservations.getByRole('row', { name: `Tripod J02 ${day(10)} ${day(12)} Sam Active` })).toBeVisible();

  await reserve(page, { equipment: 'Tripod J02', start: day(20), end: day(19), reservedBy: 'Sam' });
  await expect(form.getByRole('alert')).toHaveText('The end date cannot be before the start date.');
});

test('the server refuses past start dates and blank or too-long names', async ({ request }) => {
  const equipmentId = await createEquipmentId(request, 'Microphone J02');

  const past = await request.post('/reservations', {
    form: { equipmentId, startDate: daysFromToday(-1), endDate: daysFromToday(1), reservedBy: 'Alex' },
  });
  expect(past.status()).toBe(422);
  expect(await past.text()).toContain('The start date cannot be in the past.');

  const blank = await request.post('/reservations', {
    form: { equipmentId, startDate: daysFromToday(1), endDate: daysFromToday(1), reservedBy: '  ' },
  });
  expect(blank.status()).toBe(422);
  expect(await blank.text()).toContain('Enter who the reservation is for.');

  const tooLong = await request.post('/reservations', {
    form: { equipmentId, startDate: daysFromToday(1), endDate: daysFromToday(1), reservedBy: 'x'.repeat(101) },
  });
  expect(tooLong.status()).toBe(422);
  expect(await tooLong.text()).toContain('The reserved-by name can have at most 100 characters.');
});

test('simultaneous overlapping reservations save exactly one', async ({ request }) => {
  const equipmentId = await createEquipmentId(request, 'Laptop J02');

  const responses = await Promise.all(
    Array.from({ length: 10 }, (_, i) =>
      request.post('/reservations', {
        form: { equipmentId, startDate: daysFromToday(30), endDate: daysFromToday(31 + i), reservedBy: `User ${i}` },
        maxRedirects: 0,
      }),
    ),
  );

  const statuses = responses.map((response) => response.status());
  expect(statuses.filter((status) => status === 303)).toHaveLength(1);
  expect(statuses.filter((status) => status === 409)).toHaveLength(9);
});
