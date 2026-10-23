import { expect, test } from '@playwright/test';

test('a user adds equipment and a duplicate name is refused', async ({ page }) => {
  await page.goto('/');
  const equipment = page.getByRole('region', { name: 'Equipment' });

  await equipment.getByLabel('Name').fill('  Projector J01  ');
  await equipment.getByLabel('Description (optional)').fill('Epson, meeting room A');
  await equipment.getByRole('button', { name: 'Add equipment' }).click();
  await expect(equipment.getByRole('listitem').filter({ hasText: 'Projector J01' })).toContainText('Epson, meeting room A');

  await equipment.getByLabel('Name').fill('projector j01');
  await equipment.getByRole('button', { name: 'Add equipment' }).click();
  await expect(equipment.getByRole('alert')).toHaveText('Equipment named "projector j01" already exists.');
  await expect(equipment.getByLabel('Name')).toHaveValue('projector j01');
  await expect(equipment.getByRole('listitem').filter({ hasText: /projector j01/i })).toHaveCount(1);
});

test('the server refuses invalid names, cross-site posts and foreign hosts', async ({ request }) => {
  const blank = await request.post('/equipment', { form: { name: '   ', description: '' } });
  expect(blank.status()).toBe(422);
  expect(await blank.text()).toContain('Enter a name for the equipment.');

  const tooLong = await request.post('/equipment', { form: { name: 'x'.repeat(101), description: '' } });
  expect(tooLong.status()).toBe(422);
  expect(await tooLong.text()).toContain('The name can have at most 100 characters.');

  const crossSite = await request.post('/equipment', {
    form: { name: 'Cross-site camera', description: '' },
    headers: { Origin: 'https://attacker.example', 'Sec-Fetch-Site': 'cross-site' },
  });
  expect(crossSite.status()).toBe(403);

  const page = await request.get('/');
  expect(await page.text()).not.toContain('Cross-site camera');

  const foreignHost = await request.get('/', { headers: { Host: 'attacker.example' } });
  expect(foreignHost.status()).toBe(403);
});
