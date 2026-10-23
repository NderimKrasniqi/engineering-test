import type { DatabaseSync } from 'node:sqlite';

export const limits = { name: 100, description: 500, reservedBy: 100 };

export type Equipment = { id: number; name: string; description: string };

export type Result = { ok: true } | { ok: false; error: string; conflict?: boolean };

export type EquipmentInput = { name: string; description: string };

function nameKey(name: string): string {
  return name.trim().toLowerCase();
}

export function listEquipment(db: DatabaseSync): Equipment[] {
  return db
    .prepare('SELECT id, name, description FROM equipment ORDER BY name COLLATE NOCASE')
    .all() as Equipment[];
}

export function addEquipment(db: DatabaseSync, input: EquipmentInput): Result {
  const name = input.name.trim();
  const description = input.description.trim();

  if (!name) return { ok: false, error: 'Enter a name for the equipment.' };
  if (name.length > limits.name) return { ok: false, error: `The name can have at most ${limits.name} characters.` };
  if (description.length > limits.description) {
    return { ok: false, error: `The description can have at most ${limits.description} characters.` };
  }

  const { changes } = db
    .prepare('INSERT INTO equipment (name, name_key, description) VALUES (?, ?, ?) ON CONFLICT (name_key) DO NOTHING')
    .run(name, nameKey(name), description);

  if (!changes) return { ok: false, error: `Equipment named "${name}" already exists.` };
  return { ok: true };
}

export type ReservationStatus = 'active' | 'cancelled';

export type Reservation = {
  id: number;
  equipmentId: number;
  equipmentName: string;
  startDate: string;
  endDate: string;
  reservedBy: string;
  status: ReservationStatus;
};

export type ReservationInput = { equipmentId: string; startDate: string; endDate: string; reservedBy: string };

export function localDate(now: Date = new Date()): string {
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

function isCalendarDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().startsWith(value);
}

export function findEquipment(db: DatabaseSync, id: string): Equipment | undefined {
  if (!/^\d+$/.test(id)) return undefined;
  return db.prepare('SELECT id, name, description FROM equipment WHERE id = ?').get(Number(id)) as Equipment | undefined;
}

export function listReservations(db: DatabaseSync, equipmentId?: number): Reservation[] {
  return db
    .prepare(
      `SELECT r.id, r.equipment_id AS equipmentId, e.name AS equipmentName, r.start_date AS startDate,
              r.end_date AS endDate, r.reserved_by AS reservedBy, r.status
         FROM reservation r JOIN equipment e ON e.id = r.equipment_id
        WHERE ?1 IS NULL OR r.equipment_id = ?1
        ORDER BY r.start_date, r.end_date, r.id`,
    )
    .all(equipmentId ?? null) as Reservation[];
}

export function reserveEquipment(db: DatabaseSync, input: ReservationInput, today: string): Result {
  const equipment = findEquipment(db, input.equipmentId);
  const { startDate, endDate } = input;
  const reservedBy = input.reservedBy.trim();

  if (!equipment) return { ok: false, error: 'Choose the equipment to reserve.' };
  if (!isCalendarDate(startDate)) return { ok: false, error: 'Enter a valid start date.' };
  if (!isCalendarDate(endDate)) return { ok: false, error: 'Enter a valid end date.' };
  if (endDate < startDate) return { ok: false, error: 'The end date cannot be before the start date.' };
  if (startDate < today) return { ok: false, error: 'The start date cannot be in the past.' };
  if (!reservedBy) return { ok: false, error: 'Enter who the reservation is for.' };
  if (reservedBy.length > limits.reservedBy) {
    return { ok: false, error: `The reserved-by name can have at most ${limits.reservedBy} characters.` };
  }

  db.exec('BEGIN IMMEDIATE');
  try {
    const conflict = db
      .prepare(
        `SELECT start_date AS startDate, end_date AS endDate FROM reservation
          WHERE equipment_id = ? AND status = 'active' AND start_date <= ? AND end_date >= ?
          ORDER BY start_date LIMIT 1`,
      )
      .get(equipment.id, endDate, startDate) as { startDate: string; endDate: string } | undefined;

    if (conflict) {
      db.exec('ROLLBACK');
      return {
        ok: false,
        conflict: true,
        error: `${equipment.name} is already reserved from ${conflict.startDate} to ${conflict.endDate}.`,
      };
    }

    db.prepare('INSERT INTO reservation (equipment_id, start_date, end_date, reserved_by) VALUES (?, ?, ?, ?)')
      .run(equipment.id, startDate, endDate, reservedBy);
    db.exec('COMMIT');
    return { ok: true };
  } catch (error) {
    if (db.isTransaction) db.exec('ROLLBACK');
    throw error;
  }
}

export function isCancellable(reservation: Reservation, today: string): boolean {
  return reservation.status === 'active' && reservation.endDate >= today;
}

export function cancelReservation(db: DatabaseSync, id: string, today: string): Result {
  if (!/^\d+$/.test(id)) return { ok: false, error: 'This reservation does not exist.' };

  const { changes } = db
    .prepare("UPDATE reservation SET status = 'cancelled' WHERE id = ? AND status = 'active' AND end_date >= ?")
    .run(Number(id), today);
  if (changes) return { ok: true };

  const exists = db.prepare('SELECT 1 FROM reservation WHERE id = ?').get(Number(id));
  if (!exists) return { ok: false, error: 'This reservation does not exist.' };
  return { ok: false, conflict: true, error: 'This reservation is already cancelled or has ended.' };
}
