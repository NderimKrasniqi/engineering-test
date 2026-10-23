import express, { type ErrorRequestHandler, type NextFunction, type Request, type Response } from 'express';
import type { DatabaseSync } from 'node:sqlite';
import { addEquipment, cancelReservation, findEquipment, listEquipment, listReservations, localDate, reserveEquipment } from './booking.ts';
import { bookingPage, emptyEquipmentForm, emptyReservationForm, type PageModel } from './views.ts';

const localHostnames = new Set(['127.0.0.1', 'localhost']);

function rejectForeignHost(req: Request, res: Response, next: NextFunction): void {
  if (localHostnames.has(req.hostname)) return next();
  res.status(403).type('text').send('Forbidden');
}

function rejectCrossSitePost(req: Request, res: Response, next: NextFunction): void {
  if (req.method !== 'POST') return next();
  const fetchSite = req.get('sec-fetch-site');
  const origin = req.get('origin');
  const sameOrigin = fetchSite
    ? fetchSite === 'same-origin'
    : !origin || origin === `${req.protocol}://${req.get('host')}`;
  if (sameOrigin) return next();
  res.status(403).type('text').send('Cross-site form submissions are not allowed.');
}

const handleError: ErrorRequestHandler = (error, _req, res, _next) => {
  const status = typeof error?.status === 'number' && error.status < 500 ? error.status : 500;
  if (status === 500) console.error(error);
  res.status(status).type('text').send(status === 500 ? 'Something went wrong.' : 'The request could not be processed.');
};

function field(body: unknown, key: string): string {
  const value = (body as Record<string, unknown> | undefined)?.[key];
  return typeof value === 'string' ? value : '';
}

export function createApp(db: DatabaseSync): express.Express {
  const app = express();
  app.disable('x-powered-by');
  app.use(rejectForeignHost);
  app.use(rejectCrossSitePost);
  app.use(express.urlencoded({ extended: false, limit: '10kb' }));

  function render(res: Response, status: number, model: Partial<PageModel> = {}): void {
    const page = bookingPage({
      today: localDate(),
      equipment: listEquipment(db),
      reservations: listReservations(db, model.filter?.id),
      equipmentForm: emptyEquipmentForm,
      reservationForm: emptyReservationForm,
      ...model,
    });
    res.status(status).type('html').send(page.value);
  }

  app.get('/', (req, res) => {
    const filter = typeof req.query.equipment === 'string' ? findEquipment(db, req.query.equipment) : undefined;
    render(res, 200, { filter });
  });

  app.post('/equipment', (req, res) => {
    const values = { name: field(req.body, 'name'), description: field(req.body, 'description') };
    const result = addEquipment(db, values);
    if (result.ok) return res.redirect(303, '/');
    render(res, 422, { equipmentForm: { values, error: result.error } });
  });

  app.post('/reservations', (req, res) => {
    const values = {
      equipmentId: field(req.body, 'equipmentId'),
      startDate: field(req.body, 'startDate'),
      endDate: field(req.body, 'endDate'),
      reservedBy: field(req.body, 'reservedBy'),
    };
    const result = reserveEquipment(db, values, localDate());
    if (result.ok) return res.redirect(303, '/');
    render(res, result.conflict ? 409 : 422, { reservationForm: { values, error: result.error } });
  });

  app.post('/reservations/:id/cancel', (req, res) => {
    const filter = findEquipment(db, field(req.body, 'filter'));
    const result = cancelReservation(db, req.params.id, localDate());
    if (result.ok) return res.redirect(303, filter ? `/?equipment=${filter.id}` : '/');
    render(res, result.conflict ? 409 : 404, { filter, reservationsError: result.error });
  });

  app.use(handleError);

  return app;
}
