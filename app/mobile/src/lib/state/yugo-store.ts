import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';

export type YugoMood = 'calm' | 'nervous' | 'excited' | 'meditation' | 'idle';
export type YugoMode = 'creature' | 'ghost' | 'hunt' | 'scanner' | 'music' | 'meditation';

export const MOOD_COLORS: Record<YugoMood, { color: string; pulseDuration: number }> = {
  calm: { color: '#F59E0B', pulseDuration: 4000 },
  nervous: { color: '#06B6D4', pulseDuration: 1500 },
  excited: { color: '#EC4899', pulseDuration: 800 },
  meditation: { color: '#6366F1', pulseDuration: 6000 },
  idle: { color: '#94A3B8', pulseDuration: 3000 },
};

interface YugoState {
  // Connection
  bridgeUrl: string;
  wsConnected: boolean;
  setBridgeUrl: (url: string) => void;

  // Yugo state (from WS)
  mood: YugoMood;
  mode: YugoMode;
  battery: number;
  ledColor: string;
  personCount: number;
  fieldIntensity: number;
  isSpeaking: boolean;
  lastUtterance: string;

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
      bridgeUrl: '',
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
      mode: 'creature',
      battery: 100,
      ledColor: '#94A3B8',
      personCount: 0,
      fieldIntensity: 0,
      isSpeaking: false,
      lastUtterance: '',

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
          ws = new WebSocket(wsUrl);
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
        if (typeof d.mood === 'string' && ['calm', 'nervous', 'excited', 'meditation', 'idle'].includes(d.mood)) {
          updates.mood = d.mood as YugoMood;
        }
        if (typeof d.mode === 'string' && ['creature', 'ghost', 'hunt', 'scanner', 'music', 'meditation'].includes(d.mode)) {
          updates.mode = d.mode as YugoMode;
        }
        if (typeof d.battery === 'number') updates.battery = d.battery;
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
      // Only persist bridgeUrl — everything else is live state
      partialize: (state) => ({ bridgeUrl: state.bridgeUrl }),
    }
  )
);

export default useYugoStore;

// Convenience hook: returns mood color + pulse duration
export function useMoodColor(): { color: string; pulseDuration: number } {
  const mood = useYugoStore((s) => s.mood);
  return MOOD_COLORS[mood] ?? MOOD_COLORS.idle;
}
