import { createApp } from './app.ts';
import { openDatabase } from './db.ts';

const port = Number(process.env.PORT ?? 3000);
const db = openDatabase(process.env.DB_PATH ?? 'data/booking.db');

createApp(db).listen(port, '127.0.0.1', (error) => {
  if (error) {
    console.error(`Equipment booking could not start on port ${port}: ${error.message}`);
    process.exit(1);
  }
  console.log(`Equipment booking is running at http://127.0.0.1:${port}`);
});
