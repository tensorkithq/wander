import AsyncStorage from '@react-native-async-storage/async-storage';

const KEYS = {
  deepgram: 'yugo_deepgram_key',
  elevenlabs: 'yugo_el_key',
  voiceId: 'yugo_el_voice_id',
};

export async function getDeepgramKey(): Promise<string> {
  const stored = await AsyncStorage.getItem(KEYS.deepgram);
  return stored || (process.env.EXPO_PUBLIC_DEEPGRAM_API_KEY ?? '');
}

export async function getElevenLabsKey(): Promise<string> {
  const stored = await AsyncStorage.getItem(KEYS.elevenlabs);
  return stored || (process.env.EXPO_PUBLIC_ELEVENLABS_API_KEY ?? '');
}

export async function getVoiceId(): Promise<string> {
  const stored = await AsyncStorage.getItem(KEYS.voiceId);
  return stored || (process.env.EXPO_PUBLIC_ELEVENLABS_VOICE_ID ?? 'pNInz6obpgDQGcFmaJgB');
}

export async function setDeepgramKey(key: string): Promise<void> {
  await AsyncStorage.setItem(KEYS.deepgram, key);
}

export async function setElevenLabsKey(key: string): Promise<void> {
  await AsyncStorage.setItem(KEYS.elevenlabs, key);
}

export async function setVoiceId(id: string): Promise<void> {
  await AsyncStorage.setItem(KEYS.voiceId, id);
}
