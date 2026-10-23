import { DatabaseSync } from 'node:sqlite';
import { expect, test } from '@playwright/test';

test('the booking page loads and the database schema exists', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Equipment booking' })).toBeVisible();

  const db = new DatabaseSync(process.env.E2E_DB_PATH!, { readOnly: true });
  const tables = db.prepare("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").all();
  db.close();
  expect(tables.map((row) => row.name)).toEqual(['equipment', 'reservation']);
});
