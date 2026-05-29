import useYugoStore, { BRIDGE_HEADERS } from '@/lib/state/yugo-store';
import type { YugoMode } from '@/lib/state/yugo-store';

function getBridgeUrl(): string {
  return useYugoStore.getState().bridgeUrl;
}

async function bridgeFetch(
  path: string,
  options: RequestInit = {}
): Promise<unknown> {
  const base = getBridgeUrl();
  if (!base) {
    console.warn('[YugoAPI] No bridge URL set');
    return undefined;
  }
  try {
    const res = await fetch(`${base}${path}`, {
      method: 'POST',
      ...options,
      headers: { 'Content-Type': 'application/json', ...BRIDGE_HEADERS, ...options.headers },
    });
    if (res.status === 204) return undefined;
    const ct = res.headers.get('content-type') ?? '';
    if (ct.includes('application/json')) {
      return await res.json();
    }
    return undefined;
  } catch (e) {
    console.warn(`[YugoAPI] Request failed: ${path}`, e);
    return undefined;
  }
}

// --- Driving ---------------------------------------------------------------

export interface MoveResult {
  ok: boolean;
  action?: string;
  vx?: number;
  vy?: number;
  wz?: number;
  duration_s?: number;
  connected?: boolean;
}

// Clamp ranges (mirror server-side limits so the UI shows what the body will do).
const CLAMP = { vx: 0.6, vy: 0.6, wz: 1.2 } as const;
const clamp = (v: number, lim: number) => Math.max(-lim, Math.min(lim, v));

export async function cmdVel(vx: number, vy: number, wz: number): Promise<void> {
  await bridgeFetch('/cmd_vel', {
    body: JSON.stringify({
      vx: clamp(vx, CLAMP.vx),
      vy: clamp(vy, CLAMP.vy),
      wz: clamp(wz, CLAMP.wz),
    }),
  });
}

export async function stop(): Promise<void> {
  await bridgeFetch('/stop', { body: '{}' });
}

export async function sleep(): Promise<void> {
  await bridgeFetch('/sleep', { body: '{}' });
}

export type Nudge = 'up' | 'down' | 'left' | 'right';

export async function nudge(dir: Nudge): Promise<void> {
  await bridgeFetch(`/${dir}`, { body: '{}' });
}

// --- Tricks: dedicated, purpose-built routes ------------------------------

export async function sayHello(): Promise<void> {
  await bridgeFetch('/hello', { body: '{}' });
}

export async function sit(): Promise<void> {
  await bridgeFetch('/sit', { body: '{}' });
}

export async function stretch(): Promise<void> {
  await bridgeFetch('/stretch', { body: '{}' });
}

export async function heart(): Promise<void> {
  await bridgeFetch('/heart', { body: '{}' });
}

// --- Tricks: generic ------------------------------------------------------

export async function trick(name: string): Promise<void> {
  await bridgeFetch(`/trick/${encodeURIComponent(name)}`, { body: '{}' });
}

// --- Mode -----------------------------------------------------------------

export async function setMode(mode: YugoMode, target?: string): Promise<void> {
  const body: Record<string, string> = { mode };
  if (target && target.trim()) body.target = target.trim();
  await bridgeFetch('/mode', { body: JSON.stringify(body) });
}

// --- Voice ----------------------------------------------------------------

export async function agentSay(text: string): Promise<{ reply: string }> {
  const result = await bridgeFetch('/agent/say', {
    body: JSON.stringify({ text }),
  });
  if (result && typeof result === 'object') {
    const r = result as Record<string, unknown>;
    // Body returns { reply_text, behavior }; tolerate a bare { reply } too.
    if (typeof r.reply_text === 'string') return { reply: r.reply_text };
    if (typeof r.reply === 'string') return { reply: r.reply };
  }
  return { reply: '' };
}

// --- Sensors --------------------------------------------------------------

export interface SensorStreamPayload {
  magnetometer: { x: number; y: number; z: number };
  accel: { x: number; y: number; z: number };
  light?: number;
  gesture?: string;
}

export async function sensorStream(payload: SensorStreamPayload): Promise<void> {
  await bridgeFetch('/sensor', {
    body: JSON.stringify({
      source: 'phone-wand',
      magnetometer: payload.magnetometer,
      accel: payload.accel,
      light: payload.light ?? 0,
      gesture: payload.gesture,
      ts: Date.now() / 1000,
    }),
  });
}

export type SpellSample = [number, number, number, number]; // [t_ms, x, y, z]

export interface SpellCastPayload {
  sampleHz: number;
  magnetometer: SpellSample[];
  accel?: SpellSample[];
}

export interface SpellCastResult {
  ok: boolean;
  matched?: { bucket: number; move: string; api_id: number };
  fired?: boolean;
}

export async function sensorSpell(payload: SpellCastPayload): Promise<SpellCastResult> {
  const result = await bridgeFetch('/sensor/spell', {
    body: JSON.stringify({
      source: 'phone-wand',
      sample_hz: payload.sampleHz,
      magnetometer: payload.magnetometer,
      accel: payload.accel,
    }),
  });
  if (result && typeof result === 'object') {
    const r = result as Record<string, unknown>;
    const matched = r.matched && typeof r.matched === 'object'
      ? r.matched as { bucket: number; move: string; api_id: number }
      : undefined;
    return {
      ok: r.ok === true,
      matched,
      fired: r.fired === true,
    };
  }
  return { ok: false };
}

