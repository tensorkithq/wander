import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';

export type YugoMood = 'calm' | 'nervous' | 'excited' | 'meditation' | 'idle';
export type YugoMode = 'creature' | 'wand' | 'personal' | 'find' | 'friend' | 'meditation';

export const MOOD_COLORS: Record<YugoMood, { color: string; pulseDuration: number }> = {
  calm: { color: '#F59E0B', pulseDuration: 4000 },
  nervous: { color: '#06B6D4', pulseDuration: 1500 },
  excited: { color: '#EC4899', pulseDuration: 800 },
  meditation: { color: '#6366F1', pulseDuration: 6000 },
  idle: { color: '#94A3B8', pulseDuration: 3000 },
};

// Default bridge URL — the current ngrok tunnel to the FastAPI body.
// Override in Settings; the entered value persists and wins over this default.
export const DEFAULT_BRIDGE_URL = 'https://willette-multicapitate-limnologically.ngrok-free.dev';

// Sent on every request to the bridge. ngrok-free serves an HTML interstitial
// to browser-like clients unless this header is present — without it, fetch and
// the WS handshake receive HTML instead of the real response.
export const BRIDGE_HEADERS: Record<string, string> = {
  'ngrok-skip-browser-warning': 'true',
};

interface YugoState {
  // Connection
  bridgeUrl: string;
  wsConnected: boolean;
  setBridgeUrl: (url: string) => void;

  // Yugo state (from WS)
  mood: YugoMood; // drives the local pulse table; '' label falls back to this
  moodColor: string; // hex from the body's mood frame; '' falls back to MOOD_COLORS
  moodLabel: string; // the body's actual mood word (e.g. "zen"), for display
  mode: YugoMode;
  battery: number;
  ledColor: string;
  personCount: number;
  fieldIntensity: number;
  isSpeaking: boolean;
  lastUtterance: string;

  // Settings
  wandInverted: boolean;
  toggleWandInverted: () => void;
  navInverted: boolean;
  toggleNavInverted: () => void;

  // Find-mode target
  findTarget: string;
  setFindTarget: (t: string) => void;

  // WS management
  wsInstance: WebSocket | null;
  wsRetryCount: number;
  connectWS: () => void;
  disconnectWS: () => void;

  // Actions
  setMood: (mood: YugoMood) => void;
  setMode: (mode: YugoMode) => void;
  setIsSpeaking: (speaking: boolean) => void;
  setLastUtterance: (utterance: string) => void;
  setFieldIntensity: (intensity: number) => void;
  updateFromWS: (data: unknown) => void;
}

let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

const useYugoStore = create<YugoState>()(
  persist(
    (set, get) => ({
      // Connection defaults
      bridgeUrl: DEFAULT_BRIDGE_URL,
      wsConnected: false,
      setBridgeUrl: (url: string) => {
        set({ bridgeUrl: url });
        // Reconnect with new URL
        const state = get();
        state.disconnectWS();
        if (url) {
          setTimeout(() => get().connectWS(), 300);
        }
      },

      // Yugo defaults
      mood: 'idle',
      moodColor: '',
      moodLabel: 'idle',
      mode: 'creature',
      battery: 100,
      ledColor: '#94A3B8',
      personCount: 0,
      fieldIntensity: 0,
      isSpeaking: false,
      lastUtterance: '',

      // Settings
      wandInverted: false,
      toggleWandInverted: () => set((s) => ({ wandInverted: !s.wandInverted })),
      navInverted: false,
      toggleNavInverted: () => set((s) => ({ navInverted: !s.navInverted })),

      // Find-mode target
      findTarget: '',
      setFindTarget: (findTarget: string) => set({ findTarget }),

      // WS management
      wsInstance: null,
      wsRetryCount: 0,

      connectWS: () => {
        const { bridgeUrl, wsInstance } = get();
        if (!bridgeUrl) return;
        if (wsInstance) {
          wsInstance.close();
        }
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
          reconnectTimer = null;
        }

        const wsUrl = `${bridgeUrl.replace(/^http/, 'ws')}/ws/state`;
        let ws: WebSocket;
        try {
          // RN's WebSocket accepts a 3rd options arg with headers (DOM lib doesn't
          // type it), needed to clear ngrok's interstitial on the upgrade handshake.
          const RNWebSocket = WebSocket as unknown as new (
            url: string,
            protocols?: string[] | null,
            options?: { headers?: Record<string, string> }
          ) => WebSocket;
          ws = new RNWebSocket(wsUrl, [], { headers: BRIDGE_HEADERS });
        } catch (e) {
          console.warn('[YugoWS] Failed to create WebSocket:', e);
          return;
        }

        ws.onopen = () => {
          console.log('[YugoWS] Connected');
          set({ wsConnected: true, wsRetryCount: 0 });
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data as string);
            get().updateFromWS(data);
          } catch (e) {
            console.warn('[YugoWS] Failed to parse message:', e);
          }
        };

        ws.onerror = (e) => {
          console.warn('[YugoWS] Error:', e);
        };

        ws.onclose = () => {
          console.log('[YugoWS] Disconnected');
          set({ wsConnected: false, wsInstance: null });
          const { wsRetryCount, bridgeUrl: currentUrl } = get();
          if (currentUrl && wsRetryCount < 10) {
            set({ wsRetryCount: wsRetryCount + 1 });
            reconnectTimer = setTimeout(() => {
              get().connectWS();
            }, 5000);
          }
        };

        set({ wsInstance: ws });
      },

      disconnectWS: () => {
        const { wsInstance } = get();
        if (reconnectTimer) {
          clearTimeout(reconnectTimer);
          reconnectTimer = null;
        }
        if (wsInstance) {
          wsInstance.onclose = null; // prevent auto-reconnect
          wsInstance.close();
        }
        set({ wsInstance: null, wsConnected: false, wsRetryCount: 0 });
      },

      setMood: (mood: YugoMood) => set({ mood }),
      setMode: (mode: YugoMode) => set({ mode }),
      setIsSpeaking: (isSpeaking: boolean) => set({ isSpeaking }),
      setLastUtterance: (lastUtterance: string) => set({ lastUtterance }),
      setFieldIntensity: (fieldIntensity: number) => set({ fieldIntensity }),

      updateFromWS: (data: unknown) => {
        if (!data || typeof data !== 'object') return;
        const d = data as Record<string, unknown>;
        const updates: Partial<YugoState> = {};
        // mood: the body sends an object {scalar, label, color}; tolerate a bare
        // string too. Use `color` for the orb tint, map `label` to a YugoMood.
        if (d.mood && typeof d.mood === 'object') {
          const m = d.mood as Record<string, unknown>;
          if (typeof m.color === 'string') updates.moodColor = m.color;
          if (typeof m.label === 'string') {
            updates.moodLabel = m.label;
            if (m.label in MOOD_COLORS) updates.mood = m.label as YugoMood;
          }
        } else if (typeof d.mood === 'string') {
          updates.moodLabel = d.mood;
          if (d.mood in MOOD_COLORS) updates.mood = d.mood as YugoMood;
        }
        if (typeof d.mode === 'string' && ['creature', 'wand', 'personal', 'find', 'friend', 'meditation'].includes(d.mode)) {
          updates.mode = d.mode as YugoMode;
        }
        // battery: the body reports a 0..1 fraction; the UI shows a percent.
        if (typeof d.battery === 'number') {
          updates.battery = d.battery <= 1 ? Math.round(d.battery * 100) : Math.round(d.battery);
        }
        if (typeof d.led_color === 'string') updates.ledColor = d.led_color;
        if (typeof d.ledColor === 'string') updates.ledColor = d.ledColor;
        if (typeof d.person_count === 'number') updates.personCount = d.person_count;
        if (typeof d.personCount === 'number') updates.personCount = d.personCount;
        if (typeof d.field_intensity === 'number') updates.fieldIntensity = d.field_intensity;
        if (typeof d.fieldIntensity === 'number') updates.fieldIntensity = d.fieldIntensity;
        if (typeof d.is_speaking === 'boolean') updates.isSpeaking = d.is_speaking;
        if (typeof d.isSpeaking === 'boolean') updates.isSpeaking = d.isSpeaking;
        if (typeof d.last_utterance === 'string') updates.lastUtterance = d.last_utterance;
        if (typeof d.lastUtterance === 'string') updates.lastUtterance = d.lastUtterance;
        set(updates);
      },
    }),
    {
      name: 'yugo-storage',
      storage: createJSONStorage(() => AsyncStorage),
      // bridgeUrl is hardcoded to DEFAULT_BRIDGE_URL: it is never persisted, and
      // any value saved by an earlier build is overridden on load. Change the
      // target by editing DEFAULT_BRIDGE_URL.
      merge: (persisted, current) =>
        ({ ...current, ...(persisted as object), bridgeUrl: DEFAULT_BRIDGE_URL }) as YugoState,
      // Persist only the user toggles — bridgeUrl is hardcoded above.
      partialize: (state) => ({
        wandInverted: state.wandInverted,
        navInverted: state.navInverted,
      }),
    }
  )
);

export default useYugoStore;

// Convenience hook: returns mood color + pulse duration. Prefers the hex the
// body sends in its mood frame, falling back to the local MOOD_COLORS table.
export function useMoodColor(): { color: string; pulseDuration: number } {
  const mood = useYugoStore((s) => s.mood);
  const moodColor = useYugoStore((s) => s.moodColor);
  const base = MOOD_COLORS[mood] ?? MOOD_COLORS.idle;
  return { color: moodColor || base.color, pulseDuration: base.pulseDuration };
}
