// Network debug logging. Prints every outgoing request the app makes.
//
// Toggle with EXPO_PUBLIC_DEBUG. Expo only inlines EXPO_PUBLIC_* env vars into
// the app bundle, so a bare DEBUG would be undefined in client code — the
// variable has to be EXPO_PUBLIC_DEBUG to reach the running app.
//
// Enabled by default. Disable with EXPO_PUBLIC_DEBUG=false (also 0 / off / no).

const OFF = new Set(['false', '0', 'off', 'no']);

const rawFlag = (process.env.EXPO_PUBLIC_DEBUG ?? process.env.DEBUG ?? '')
  .trim()
  .toLowerCase();

let enabled = !OFF.has(rawFlag);

export function isNetworkDebug(): boolean {
  return enabled;
}

// Runtime override, e.g. from an in-app dev toggle.
export function setNetworkDebug(on: boolean): void {
  enabled = on;
}

// Reentrancy guard: console output is itself shipped to Metro over a socket, so
// a log emitted while logging must not trigger another log (infinite loop).
let emitting = false;
function emit(...args: unknown[]): void {
  if (emitting) return;
  emitting = true;
  try {
    console.log(...args);
  } finally {
    emitting = false;
  }
}

const MAX_BODY = 2000;

// Headers that carry credentials — never print their values.
const SENSITIVE =
  /^(authorization|proxy-authorization|cookie|set-cookie|x-api-key|xi-api-key|api-key|apikey|x-auth-token|deepgram-key|openai-api-key)$/i;

function redactHeaders(headers: HeadersInit | undefined): Record<string, string> | undefined {
  if (!headers) return undefined;
  const out: Record<string, string> = {};
  const put = (k: string, v: string) => {
    out[k] = SENSITIVE.test(k) ? '[redacted]' : v;
  };
  if (typeof Headers !== 'undefined' && headers instanceof Headers) {
    headers.forEach((v, k) => put(k, v));
  } else if (Array.isArray(headers)) {
    for (const [k, v] of headers) put(k, String(v));
  } else {
    for (const [k, v] of Object.entries(headers)) put(k, String(v));
  }
  return out;
}

function truncate(s: string): string {
  return s.length > MAX_BODY ? `${s.slice(0, MAX_BODY)}… (+${s.length - MAX_BODY} chars)` : s;
}

// Render a request/WS payload for logging without consuming streams or
// dumping binary blobs.
export function previewBody(body: unknown): string | undefined {
  if (body == null) return undefined;
  if (typeof body === 'string') return truncate(body);
  if (typeof FormData !== 'undefined' && body instanceof FormData) return '[FormData]';
  if (typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams) {
    return truncate(body.toString());
  }
  if (typeof Blob !== 'undefined' && body instanceof Blob) return `[Blob ${body.size} bytes]`;
  if (body instanceof ArrayBuffer) return `[ArrayBuffer ${body.byteLength} bytes]`;
  if (ArrayBuffer.isView(body)) return `[binary ${(body as ArrayBufferView).byteLength} bytes]`;
  try {
    return truncate(JSON.stringify(body));
  } catch {
    return String(body);
  }
}

export function logRequest(
  method: string,
  url: string,
  headers?: HeadersInit,
  body?: unknown,
): void {
  if (!enabled) return;
  const meta: Record<string, unknown> = {};
  const h = redactHeaders(headers);
  const b = previewBody(body);
  if (h) meta.headers = h;
  if (b !== undefined) meta.body = b;
  if (Object.keys(meta).length) emit(`[net] → ${method} ${url}`, meta);
  else emit(`[net] → ${method} ${url}`);
}

export function logResponse(method: string, url: string, status: number, ms: number): void {
  if (!enabled) return;
  emit(`[net] ← ${status} ${method} ${url} (${ms}ms)`);
}

export function logError(method: string, url: string, err: unknown, ms: number): void {
  if (!enabled) return;
  emit(`[net] ✕ ${method} ${url} (${ms}ms)`, err);
}

export function logWs(event: string, url: string, detail?: unknown): void {
  if (!enabled) return;
  if (detail !== undefined) emit(`[net] ws ${event} ${url}`, detail);
  else emit(`[net] ws ${event} ${url}`);
}

export function logWsSend(url: string, data: unknown): void {
  if (!enabled) return;
  emit(`[net] ws → ${url}`, previewBody(data));
}
