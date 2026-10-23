# Equipment booking

A small local web app to add equipment, reserve it for whole days, view reservations and cancel them. The same equipment never has overlapping active reservations.

## Run

Requires Node.js 24 or later.

```bash
npm install
npm start
```

Open http://127.0.0.1:3000. Data is stored in `data/booking.db`. Set `PORT` or `DB_PATH` to change them.

## Verify

```bash
npm run typecheck
npx playwright install chromium   # first time only
npm run test:e2e
```

## Documentation

- `docs/product.md`: product scope and journeys
- `docs/domain.md`: domain rules
- `docs/specs.md`: expected behavior
- `docs/architecture.md`: technical design
- `docs/implementation-plan.md`: build plan and progress
