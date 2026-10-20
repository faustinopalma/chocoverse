type JsonObject = { [key: string]: unknown };

export function object(value: unknown): JsonObject {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Invalid analytical service response.');
  }
  return value as JsonObject;
}

const MAX_BYTES = 262144;

export async function boundedText(response: Response, limit = MAX_BYTES): Promise<string> {
  if (!response.body) throw new Error('Analytical service returned no response body.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let bytes = 0;
  let text = '';
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) return text + decoder.decode();
      bytes += next.value.byteLength;
      if (bytes > limit) throw new Error('Analytical service response exceeds the safety limit.');
      text += decoder.decode(next.value, { stream: true });
    }
  } finally {
    await reader.cancel();
  }
}

export async function rpcBody(response: Response, id: number): Promise<JsonObject> {
  if (!response.ok) throw new Error(`Data Agent request failed (HTTP ${response.status}). Check app-owner source permissions.`);
  if (!response.body) throw new Error('Data Agent returned no response body.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const sse = response.headers.get('content-type')?.includes('text/event-stream');
  let buffer = '';
  let bytes = 0;
  const result = (payload: string): JsonObject | undefined => {
    const parsed = object(JSON.parse(payload));
    if (parsed.id !== id) return undefined;
    if (parsed.error) throw new Error('Data Agent returned a JSON-RPC error. Inspect source configuration and permissions.');
    return object(parsed.result);
  };
  try {
    while (true) {
      const next = await reader.read();
      if (!next.done) {
        bytes += next.value.byteLength;
        if (bytes > MAX_BYTES) throw new Error('Data Agent response exceeds the safety limit.');
        buffer += decoder.decode(next.value, { stream: true });
      } else {
        buffer += decoder.decode();
      }
      if (sse) {
        buffer = buffer.replace(/\r\n/g, '\n');
        let end: number;
        while ((end = buffer.indexOf('\n\n')) >= 0) {
          const frame = buffer.slice(0, end);
          buffer = buffer.slice(end + 2);
          const data = frame.split('\n').filter(line => line.startsWith('data:'))
            .map(line => line.slice(5).trimStart()).join('\n');
          if (data) {
            const found = result(data);
            if (found) return found;
          }
        }
      } else if (next.done) {
        const found = result(buffer);
        if (found) return found;
      }
      if (next.done) throw new Error('Data Agent response omitted the matching request ID.');
    }
  } finally {
    await reader.cancel();
  }
}

export async function askAgent(endpoint: string, token: string, question: string,
  signal: AbortSignal = AbortSignal.timeout(180000)): Promise<string> {
  let session: string | null = null;
  const post = async (body: JsonObject): Promise<Response> => fetch(endpoint, {
    method: 'POST', signal, redirect: 'error',
    headers: {
      Authorization: `Bearer ${token}`, Accept: 'application/json, text/event-stream',
      'Content-Type': 'application/json', 'MCP-Protocol-Version': '2025-03-26',
      ...(session ? { 'Mcp-Session-Id': session } : {}),
    },
    body: JSON.stringify(body),
  });
  let failed = false;
  try {
  const init = await post({
    jsonrpc: '2.0', id: 1, method: 'initialize',
    params: { protocolVersion: '2025-03-26', capabilities: {},
      clientInfo: { name: 'giandoria-decision-room', version: '1.0.0' } },
  });
  session = init.headers.get('mcp-session-id');
  await rpcBody(init, 1);
  const ack = await post({ jsonrpc: '2.0', method: 'notifications/initialized' });
  if (!ack.ok) throw new Error(`Data Agent initialization failed (HTTP ${ack.status}).`);
  await ack.body?.cancel();
  const listed = await rpcBody(await post({ jsonrpc: '2.0', id: 2, method: 'tools/list' }), 2);
  if (!Array.isArray(listed.tools) || listed.tools.length !== 1) {
    throw new Error('Data Agent must advertise exactly one analytical tool.');
  }
  const tool = object(listed.tools[0]);
  const schema = object(tool.inputSchema);
  const properties = object(schema.properties);
  const keys = Object.keys(properties).filter(key => object(properties[key]).type === 'string');
  if (typeof tool.name !== 'string' || keys.length !== 1 || Object.keys(properties).length !== 1) {
    throw new Error('Data Agent question contract is unsupported.');
  }
  const answered = await rpcBody(await post({
    jsonrpc: '2.0', id: 3, method: 'tools/call',
    params: { name: tool.name, arguments: { [keys[0]]: question } },
  }), 3);
  if (answered.isError || !Array.isArray(answered.content)) throw new Error('Data Agent could not answer the question.');
  const answer = answered.content.map(value => object(value)).filter(value => value.type === 'text')
    .map(value => value.text).filter((value): value is string => typeof value === 'string').join('\n');
  if (!answer.trim() || answer.length > 4000) throw new Error('Data Agent answer is empty or exceeds 4,000 characters. Ask a narrower question.');
  return answer;
  } catch (error) {
    failed = true;
    throw error;
  } finally {
    if (session) {
      try {
        const response = await fetch(endpoint, {
          method: 'DELETE', redirect: 'error', signal: AbortSignal.timeout(5000),
          headers: { Authorization: `Bearer ${token}`, 'Mcp-Session-Id': session,
            'MCP-Protocol-Version': '2025-03-26' },
        });
        await response.body?.cancel();
        if (response.status === 405) console.warn('Data Agent does not support explicit MCP session termination.');
        else if (!response.ok && response.status !== 404) throw new Error(`MCP cleanup failed (HTTP ${response.status}).`);
      } catch (error) {
        console.error('Data Agent session cleanup failed:', error instanceof Error ? error.message : 'Unknown cleanup failure.');
        if (!failed) throw new Error('Data Agent session cleanup failed. The investigation was not recorded.');
      }
    }
  }
}
