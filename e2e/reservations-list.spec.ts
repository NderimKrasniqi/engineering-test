import { expect, test } from '@playwright/test';
import { addEquipment, daysFromToday as day, reserve } from './support/booking.ts';

test('a user views reservations sorted by start date and filters by equipment', async ({ page }) => {
  await page.goto('/');
  await addEquipment(page, 'Speaker J03');
  await addEquipment(page, 'Screen J03');
  await addEquipment(page, 'Cable J03');
  await reserve(page, { equipment: 'Speaker J03', start: day(50), end: day(51), reservedBy: 'Late' });
  await reserve(page, { equipment: 'Screen J03', start: day(45), end: day(45), reservedBy: 'Other' });
  await reserve(page, { equipment: 'Speaker J03', start: day(40), end: day(41), reservedBy: 'Early' });

  const reservations = page.getByRole('region', { name: 'Reservations' });
  const rows = reservations.getByRole('row').filter({ hasText: 'J03' });
  await expect(rows).toHaveText([/Speaker J03.*Early/s, /Screen J03.*Other/s, /Speaker J03.*Late/s]);

  await reservations.getByLabel('Show equipment').selectOption({ label: 'Speaker J03' });
  await reservations.getByRole('button', { name: 'Filter' }).click();
  await expect(rows).toHaveText([/Speaker J03.*Early.*Active/s, /Speaker J03.*Late.*Active/s]);
  await expect(reservations.getByRole('row').filter({ hasText: 'Screen J03' })).toHaveCount(0);

  await reservations.getByLabel('Show equipment').selectOption({ label: 'Cable J03' });
  await reservations.getByRole('button', { name: 'Filter' }).click();
  await expect(reservations.getByText('No reservations for Cable J03.')).toBeVisible();

  await reservations.getByLabel('Show equipment').selectOption({ label: 'All equipment' });
  await reservations.getByRole('button', { name: 'Filter' }).click();
  await expect(rows).toHaveCount(3);
});
