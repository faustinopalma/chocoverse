import { createHash } from 'node:crypto';
import { setTimeout } from 'node:timers/promises';
import { boundedText, object } from './mcp.js';

function canonical(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value !== null && typeof value === 'object') {
    const record = object(value);
    return '{' + Object.keys(record).sort().map(key => JSON.stringify(key) + ':' + canonical(record[key])).join(',') + '}';
  }
  return JSON.stringify(value);
}

export async function assertContract(workspace: string, item: string, expected: string, token: string,
  signal: AbortSignal = AbortSignal.timeout(45000), format?: 'TMSL'): Promise<void> {
  const base = 'https://api.fabric.microsoft.com/v1';
  const headers = { Authorization: `Bearer ${token}` };
  let response = await fetch(`${base}/workspaces/${workspace}/items/${item}/getDefinition${format ? '?format=' + format : ''}`,
    { method: 'POST', headers, signal, redirect: 'error' });
  while (response.status === 202) {
    const location = response.headers.get('location');
    const route = location ? new URL(location, base) : undefined;
    if (!route || !/^\/v1\/operations\/[0-9a-f-]{36}(?:\/result)?$/i.test(route.pathname) ||
      route.search || route.hash) {
      throw new Error('Unsupported definition polling location.');
    }
    // Fabric returns regional Location hosts; reuse the validated route on the public API.
    const polling = 'https://api.fabric.microsoft.com' + route.pathname;
    const retry = Number(response.headers.get('retry-after') ?? 2);
    if (!Number.isFinite(retry) || retry < 0 || retry > 20) throw new Error('Unsupported definition polling delay.');
    await response.body?.cancel();
    await setTimeout(retry * 1000, undefined, { signal });
    response = await fetch(polling, { headers, signal, redirect: 'error' });
    if (response.ok && response.status !== 202 && !route.pathname.endsWith('/result')) {
      const status = object(JSON.parse(await boundedText(response)));
      if (status.status === 'Succeeded') {
        response = await fetch(`${polling}/result`, { headers, signal, redirect: 'error' });
      } else if (status.status === 'Running' || status.status === 'NotStarted') {
        response = new Response(null, { status: 202, headers: { location: polling } });
      } else {
        throw new Error('Source definition operation failed.');
      }
    }
  }
  if (!response.ok) throw new Error(`Source verification failed (HTTP ${response.status}). Check app-owner permissions.`);
  const definition = object(object(JSON.parse(await boundedText(response, 8 * 1024 * 1024))).definition);
  if (!Array.isArray(definition.parts)) throw new Error('Source definition has no parts.');
  const parts: Record<string, unknown> = {};
  for (const entry of definition.parts) {
    const part = object(entry);
    if (typeof part.path !== 'string' || typeof part.payload !== 'string') throw new Error('Invalid source definition part.');
    if (part.path !== '.platform') {
      if (part.path in parts) throw new Error('Duplicate source definition part.');
      parts[part.path] = JSON.parse(Buffer.from(part.payload, 'base64').toString('utf8'));
    }
  }
  const actual = createHash('sha256').update(canonical(parts)).digest('hex');
  if (actual !== expected) throw new Error('Enterprise source changed. Reconcile and prepare the app before investigating.');
}
