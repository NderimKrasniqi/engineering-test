import type { APIRequestContext, Page } from '@playwright/test';

export function daysFromToday(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

export async function addEquipment(page: Page, name: string): Promise<void> {
  const equipment = page.getByRole('region', { name: 'Equipment' });
  await equipment.getByLabel('Name').fill(name);
  await equipment.getByRole('button', { name: 'Add equipment' }).click();
}

export async function reserve(
  page: Page,
  { equipment, start, end, reservedBy }: { equipment: string; start: string; end: string; reservedBy: string },
): Promise<void> {
  const form = page.getByRole('region', { name: 'New reservation' });
  await form.getByLabel('Equipment').selectOption({ label: equipment });
  await form.getByLabel('Start date').fill(start);
  await form.getByLabel('End date').fill(end);
  await form.getByLabel('Reserved by').fill(reservedBy);
  await form.getByRole('button', { name: 'Reserve' }).click();
}

export async function createEquipmentId(request: APIRequestContext, name: string): Promise<string> {
  await request.post('/equipment', { form: { name, description: '' } });
  const pageHtml = await (await request.get('/')).text();
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = pageHtml.match(new RegExp(`<option value="(\\d+)"[^>]*>${escapedName}</option>`));
  if (!match) throw new Error(`Equipment ${name} not found in the reservation form`);
  return match[1];
}
