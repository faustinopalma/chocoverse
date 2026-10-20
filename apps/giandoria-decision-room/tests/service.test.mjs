import { afterEach, mock, test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { askAgent, boundedText, rpcBody } from '../packages/functions/dist/mcp.js';
import { assertContract } from '../packages/functions/dist/contract.js';

afterEach(() => mock.restoreAll());
const rpc = (id, result, headers = {}) => Response.json({ jsonrpc: '2.0', id, result }, { headers });

test('JSON and SSE match request IDs and stop without waiting for stream closure', async () => {
  assert.deepEqual(await rpcBody(rpc(3, { ok: true }), 3), { ok: true });
  let cancelled = false;
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(': ping\r\n\r\ndata: {"id":2,"result":{}}\r\n\r\ndata: {"id":3,"result":{"ok":true}}\r\n\r\n'));
    },
    cancel() { cancelled = true; },
  });
  assert.deepEqual(await rpcBody(new Response(stream, { headers: { 'content-type': 'text/event-stream' } }), 3), { ok: true });
  assert.equal(cancelled, true);
  await assert.rejects(rpcBody(rpc(2, {}), 3), /matching request ID/);
  await assert.rejects(rpcBody(Response.json({ id: 3, error: { code: -1 } }), 3), /JSON-RPC/);
  await assert.rejects(rpcBody(new Response('denied', { status: 403 }), 3), /HTTP 403/);
});

test('response limits count bytes, including multibyte UTF-8', async () => {
  assert.equal(await boundedText(new Response('abc'), 3), 'abc');
  await assert.rejects(boundedText(new Response('éé'), 3), /safety limit/);
  await assert.rejects(rpcBody(new Response('x'.repeat(262145)), 3), /safety limit/);
  await assert.rejects(boundedText(new Response(null)), /no response body/);
});

function agentResponses(answer = 'Facts, advice and limitations.') {
  return [
    rpc(1, { protocolVersion: '2025-03-26' }, { 'mcp-session-id': 'test-session' }),
    new Response(null, { status: 202 }),
    rpc(2, { tools: [{ name: 'ask', inputSchema: { properties: { query: { type: 'string' } } } }] }),
    rpc(3, { content: [{ type: 'text', text: answer }] }),
    new Response(null, { status: 204 }),
  ];
}

test('agent initializes once, invokes one discovered tool and terminates its session', async () => {
  const responses = agentResponses();
  const requests = [];
  mock.method(globalThis, 'fetch', async (_url, options) => {
    requests.push(options);
    assert.equal(options.redirect, 'error');
    return responses.shift();
  });
  assert.equal(await askAgent('https://api.fabric.microsoft.com/test', 'test-only-token', 'Why?'), 'Facts, advice and limitations.');
  assert.equal(requests.length, 5);
  assert.equal(requests[4].method, 'DELETE');
  assert.equal(requests[2].headers['Mcp-Session-Id'], 'test-session');
  assert.deepEqual(JSON.parse(requests[3].body).params, { name: 'ask', arguments: { query: 'Why?' } });
});

test('empty and oversized answers fail explicitly and still clean up', async () => {
  for (const answer of ['', 'x'.repeat(4001)]) {
    const responses = agentResponses(answer);
    const fetch = mock.method(globalThis, 'fetch', async () => responses.shift());
    await assert.rejects(askAgent('https://api.fabric.microsoft.com/test', 'test-only-token', 'Why?'), /empty or exceeds/);
    assert.equal(fetch.mock.calls.at(-1).arguments[1].method, 'DELETE');
    fetch.mock.restore();
  }
});

test('cleanup failure is surfaced, without hiding an earlier analytical failure', async () => {
  const log = mock.method(console, 'error', () => {});
  for (const answer of ['Useful answer.', '']) {
    const responses = agentResponses(answer);
    responses[4] = new Response(null, { status: 500 });
    const fetch = mock.method(globalThis, 'fetch', async () => responses.shift());
    await assert.rejects(askAgent('https://api.fabric.microsoft.com/test', 'test-only-token', 'Why?'),
      answer ? /session cleanup failed/ : /empty or exceeds/);
    fetch.mock.restore();
  }
  assert.equal(log.mock.callCount(), 2);
});

const parts = [{ path: 'model.bim', payloadType: 'InlineBase64',
  payload: Buffer.from('{"z":"cacao","a":1}').toString('base64') }];
const definition = () => Response.json({ definition: { parts: [...parts,
  { path: '.platform', payload: Buffer.from('{}').toString('base64') }] } });
const digest = createHash('sha256').update('{"model.bim":{"a":1,"z":"cacao"}}').digest('hex');

test('source guard canonicalizes key order, excludes platform metadata and rejects changes', async () => {
  mock.method(globalThis, 'fetch', async () => definition());
  await assertContract('workspace', 'model', digest, 'test-only-token');
  await assert.rejects(assertContract('workspace', 'model', 'changed', 'test-only-token'), /source changed/);
});

test('source guard polls the official operation and result route, rejecting unsafe destinations', async () => {
  const location = 'https://api.fabric.microsoft.com/v1/operations/11111111-1111-1111-1111-111111111111';
  const responses = [new Response(null, { status: 202, headers: { location, 'retry-after': '0' } }),
    Response.json({ status: 'Succeeded' }), definition()];
  const fetch = mock.method(globalThis, 'fetch', async () => responses.shift());
  await assertContract('workspace', 'model', digest, 'test-only-token');
  assert.equal(fetch.mock.calls.at(-1).arguments[0], location + '/result');
  fetch.mock.restore();
  for (const invalid of ['https://other.invalid/v1/operations/id', location + '/../../workspaces/other',
    location + '?redirect=other']) {
    const fetch = mock.method(globalThis, 'fetch', async () =>
      new Response(null, { status: 202, headers: { location: invalid } }));
    await assert.rejects(assertContract('workspace', 'model', digest, 'test-only-token'), /polling location/);
    assert.equal(fetch.mock.callCount(), 1);
    fetch.mock.restore();
  }
});

test('regional operation URLs are pinned back to the public API and model format is explicit', async () => {
  const regional = 'https://wabi-us-central-b-primary-redirect.analysis.windows.net/v1/operations/11111111-1111-1111-1111-111111111111';
  const responses = [new Response(null, { status: 202, headers: { location: regional, 'retry-after': '0' } }),
    Response.json({ status: 'Succeeded' }), definition()];
  const fetch = mock.method(globalThis, 'fetch', async () => responses.shift());
  await assertContract('workspace', 'model', digest, 'test-only-token', undefined, 'TMSL');
  assert.ok(fetch.mock.calls[0].arguments[0].endsWith('/getDefinition?format=TMSL'));
  assert.equal(new URL(fetch.mock.calls[1].arguments[0]).hostname, 'api.fabric.microsoft.com');
  assert.equal(new URL(fetch.mock.calls[2].arguments[0]).hostname, 'api.fabric.microsoft.com');
});

test('source guard detects duplicate parts, failed operations and aborts retry waits', async () => {
  let fetch = mock.method(globalThis, 'fetch', async () => Response.json({ definition: { parts: [...parts, ...parts] } }));
  await assert.rejects(assertContract('workspace', 'model', digest, 'test-only-token'), /Duplicate/);
  fetch.mock.restore();
  const location = 'https://api.fabric.microsoft.com/v1/operations/11111111-1111-1111-1111-111111111111';
  const responses = [new Response(null, { status: 202, headers: { location, 'retry-after': '0' } }),
    Response.json({ status: 'Failed' })];
  fetch = mock.method(globalThis, 'fetch', async () => responses.shift());
  await assert.rejects(assertContract('workspace', 'model', digest, 'test-only-token'), /operation failed/);
  fetch.mock.restore();
  mock.method(globalThis, 'fetch', async () => new Response(null, { status: 202, headers: { location, 'retry-after': '10' } }));
  await assert.rejects(assertContract('workspace', 'model', digest, 'test-only-token', AbortSignal.timeout(15)), /aborted/);
});
