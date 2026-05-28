import useYugoStore from '@/lib/state/yugo-store';
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
      headers: { 'Content-Type': 'application/json' },
      ...options,
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

export async function cmdVel(linear: number, angular: number): Promise<void> {
  await bridgeFetch('/cmd_vel', {
    body: JSON.stringify({ linear, angular }),
  });
}

export async function stop(): Promise<void> {
  await bridgeFetch('/stop', { body: '{}' });
}

export async function trick(
  name: 'Hello' | 'WiggleHips' | 'Stretch' | 'FingerHeart'
): Promise<void> {
  await bridgeFetch('/trick', { body: JSON.stringify({ name }) });
}

export async function setMode(mode: YugoMode): Promise<void> {
  await bridgeFetch('/mode', { body: JSON.stringify({ mode }) });
}

export async function agentSay(text: string): Promise<{ reply: string }> {
  const result = await bridgeFetch('/agent/say', {
    body: JSON.stringify({ text }),
  });
  if (result && typeof result === 'object') {
    const r = result as Record<string, unknown>;
    if (typeof r.reply === 'string') return { reply: r.reply };
  }
  return { reply: '' };
}

export async function sendSensor(data: {
  mag: number;
  accel: [number, number, number];
  light: number;
}): Promise<void> {
  await bridgeFetch('/sensor', { body: JSON.stringify(data) });
}

export async function playAudio(url: string): Promise<void> {
  await bridgeFetch('/audio/play', { body: JSON.stringify({ url }) });
}

export async function dance(bpm: number, style: string): Promise<void> {
  await bridgeFetch('/dance', { body: JSON.stringify({ bpm, style }) });
}

export async function breathe(
  phase: 'inhale' | 'exhale',
  duration: number
): Promise<void> {
  await bridgeFetch('/breathe', { body: JSON.stringify({ phase, duration }) });
}
