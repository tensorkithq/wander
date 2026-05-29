// Routes every fetch() and WebSocket through the network debug logger by
// patching the globals once at app entry. Call installNetworkDebug() before
// any app code runs (see index.ts).
//
// expo/fetch is a separate implementation and is NOT covered here — that path
// (lib/api/api.ts) hooks the logger directly at its request() choke point.
//
// The inbound WS state stream (~12 Hz) is intentionally not logged: it is
// received, not sent, and would flood the console. WS lifecycle and outgoing
// send() are logged.

import { isNetworkDebug, logError, logRequest, logResponse, logWs, logWsSend } from './debug';

const INSTALLED = Symbol.for('yugo.netdebug.installed');

function methodOf(input: unknown, init?: RequestInit): string {
  if (init?.method) return init.method.toUpperCase();
  if (input && typeof input === 'object' && 'method' in input) {
    const m = (input as { method?: string }).method;
    if (m) return m.toUpperCase();
  }
  return 'GET';
}

function urlOf(input: unknown): string {
  if (typeof input === 'string') return input;
  if (input && typeof input === 'object' && 'url' in input) {
    return String((input as { url?: string }).url ?? input);
  }
  return String(input);
}

function patchFetch(g: Record<string, unknown>): void {
  const orig = g.fetch as typeof fetch | undefined;
  if (typeof orig !== 'function') return;

  const patched: typeof fetch = function (this: unknown, input: any, init?: any) {
    if (!isNetworkDebug()) return orig.call(this, input, init);
    const method = methodOf(input, init);
    const url = urlOf(input);
    const headers: HeadersInit | undefined =
      init?.headers ?? (input && typeof input === 'object' ? input.headers : undefined);
    const body: unknown =
      init?.body ?? (input && typeof input === 'object' ? input._bodyInit : undefined);
    const start = Date.now();
    logRequest(method, url, headers, body);
    return orig.call(this, input, init).then(
      (res) => {
        logResponse(method, url, res.status, Date.now() - start);
        return res;
      },
      (err) => {
        logError(method, url, err, Date.now() - start);
        throw err;
      },
    );
  };

  g.fetch = patched;
}

// Metro/Expo/Hermes dev sockets (HMR, inspector, log shipping). Instrumenting
// these would feed back on itself: a log emitted here is shipped to Metro over
// the /hot socket, which is another send(), which logs again → infinite loop.
const DEV_WS =
  /\/(hot|message|inspector|debugger-proxy|launch-js-devtools|symbolicate|events|logs)(\/|$|\?)/;

function isDevSocket(url: string): boolean {
  return typeof url === 'string' && DEV_WS.test(url);
}

function patchWebSocket(g: Record<string, unknown>): void {
  const OrigWS = g.WebSocket as (typeof WebSocket) | undefined;
  if (typeof OrigWS !== 'function') return;

  function PatchedWebSocket(url: string, protocols?: string | string[]) {
    const ws = new OrigWS!(url, protocols);
    if (isNetworkDebug() && !isDevSocket(url)) {
      try {
        ws.addEventListener?.('open', () => logWs('open', url));
        ws.addEventListener?.('close', (e: any) => logWs('close', url, e?.code));
        ws.addEventListener?.('error', (e: any) => logWs('error', url, e?.message ?? 'error'));
      } catch {
        // EventTarget API not available — lifecycle logging is best-effort.
      }
      const origSend = ws.send?.bind(ws);
      if (origSend) {
        ws.send = (data: any) => {
          logWsSend(url, data);
          return origSend(data);
        };
      }
    }
    return ws;
  }

  PatchedWebSocket.prototype = OrigWS.prototype;
  for (const k of ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED'] as const) {
    (PatchedWebSocket as unknown as Record<string, unknown>)[k] = (OrigWS as unknown as Record<string, unknown>)[k];
  }
  g.WebSocket = PatchedWebSocket as unknown as typeof WebSocket;
}

export function installNetworkDebug(): void {
  const g = globalThis as unknown as Record<string | symbol, unknown>;
  if (g[INSTALLED]) return;
  g[INSTALLED] = true;
  patchFetch(g as Record<string, unknown>);
  patchWebSocket(g as Record<string, unknown>);
}
