import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

test('the server reports a busy port and exits with an error', async ({ baseURL }) => {
  const port = new URL(baseURL!).port;
  const server = spawn('node', ['src/server.ts'], {
    env: { ...process.env, PORT: port, DB_PATH: join(tmpdir(), `equipment-booking-busy-${Date.now()}.db`) },
  });

  let output = '';
  server.stdout.on('data', (chunk) => (output += chunk));
  server.stderr.on('data', (chunk) => (output += chunk));
  const exitCode = await new Promise<number | null>((resolve) => server.on('exit', resolve));

  expect(exitCode).toBe(1);
  expect(output).toContain(`Equipment booking could not start on port ${port}`);
  expect(output).not.toContain('is running');
});
