import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  Pressable,
  ScrollView,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import useYugoStore, { useMoodColor, BRIDGE_HEADERS } from '@/lib/state/yugo-store';
import {
  getDeepgramKey,
  getElevenLabsKey,
  getVoiceId,
  setDeepgramKey,
  setElevenLabsKey,
  setVoiceId,
} from '@/lib/api-keys';
import { font } from '@/lib/typography';

type ConnState = 'idle' | 'testing' | 'ok' | 'fail';

function Field({
  label,
  value,
  onChangeText,
  placeholder,
  secureTextEntry,
  hint,
  keyboardType,
  testID,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  placeholder?: string;
  secureTextEntry?: boolean;
  hint?: string;
  keyboardType?: 'default' | 'url';
  testID?: string;
}) {
  return (
    <View style={{ marginBottom: 18 }}>
      <Text
        style={{
          fontFamily: font.semibold,
          color: '#FFFFFF99',
          fontSize: 10,
          letterSpacing: 2,
          marginBottom: 8,
        }}
      >
        {label.toUpperCase()}
      </Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor="#FFFFFF22"
        secureTextEntry={secureTextEntry}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType={keyboardType ?? 'default'}
        testID={testID}
        style={{
          fontFamily: font.regular,
          color: '#FFFFFF',
          fontSize: 14,
          backgroundColor: '#FFFFFF08',
          borderWidth: 1,
          borderColor: '#FFFFFF14',
          borderRadius: 12,
          paddingHorizontal: 14,
          paddingVertical: Platform.OS === 'ios' ? 14 : 10,
        }}
      />
      {hint ? (
        <Text style={{ fontFamily: font.light, color: '#FFFFFF44', fontSize: 11, marginTop: 6, fontStyle: 'italic' }}>
          {hint}
        </Text>
      ) : null}
    </View>
  );
}

export default function SettingsScreen() {
  const { color: moodColor } = useMoodColor();
  const bridgeUrl = useYugoStore((s) => s.bridgeUrl);
  const setBridgeUrl = useYugoStore((s) => s.setBridgeUrl);

  const [url, setUrl] = useState(bridgeUrl);
  const [dgKey, setDgKey] = useState('');
  const [elKey, setElKey] = useState('');
  const [voice, setVoice] = useState('');
  const [conn, setConn] = useState<ConnState>('idle');
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    (async () => {
      setDgKey(await getDeepgramKey());
      setElKey(await getElevenLabsKey());
      setVoice(await getVoiceId());
    })();
  }, []);

  const testConnection = async () => {
    if (!url) return;
    setConn('testing');
    try {
      const ctrl = new AbortController();
      const timeout = setTimeout(() => ctrl.abort(), 5000);
      const res = await fetch(`${url}/healthz`, { signal: ctrl.signal, headers: BRIDGE_HEADERS });
      clearTimeout(timeout);
      setConn(res.ok ? 'ok' : 'fail');
      Haptics.notificationAsync(
        res.ok ? Haptics.NotificationFeedbackType.Success : Haptics.NotificationFeedbackType.Error
      );
    } catch {
      setConn('fail');
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
    }
  };

  const save = async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setBridgeUrl(url.trim());
    await setDeepgramKey(dgKey.trim());
    await setElevenLabsKey(elKey.trim());
    await setVoiceId(voice.trim() || 'pNInz6obpgDQGcFmaJgB');
    setSavedFlash(true);
    setTimeout(() => setSavedFlash(false), 1500);
  };

  const connColor =
    conn === 'ok' ? '#22C55E' : conn === 'fail' ? '#EF4444' : conn === 'testing' ? '#F59E0B' : '#FFFFFF55';
  const connLabel =
    conn === 'ok' ? 'CONNECTED' : conn === 'fail' ? 'NO RESPONSE' : conn === 'testing' ? 'CHECKING' : 'TEST';

  return (
    <View style={{ flex: 1, backgroundColor: '#0A0A0F' }}>
      <SafeAreaView style={{ flex: 1 }} edges={['bottom']}>
        <ScrollView
          contentContainerStyle={{ padding: 20 }}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Heading */}
          <Text
            style={{
              fontFamily: font.extrabold,
              color: '#FFFFFF',
              fontSize: 28,
              letterSpacing: -0.5,
              marginBottom: 4,
            }}
          >
            Tune Yugo
          </Text>
          <Text style={{ fontFamily: font.light, color: '#FFFFFF66', fontSize: 13, marginBottom: 24, lineHeight: 18 }}>
            Connect to the bridge laptop and bring in voices.
          </Text>

          {/* Bridge */}
          <Text
            style={{
              fontFamily: font.bold,
              color: moodColor,
              fontSize: 11,
              letterSpacing: 3,
              marginBottom: 12,
            }}
          >
            BRIDGE
          </Text>

          <Field
            label="Bridge URL"
            value={url}
            onChangeText={(v) => {
              setUrl(v);
              setConn('idle');
            }}
            placeholder="http://192.168.1.100:8000"
            hint="The laptop running the Yugo bridge API"
            keyboardType="url"
            testID="bridge-url-input"
          />

          <Pressable
            onPress={testConnection}
            testID="test-connection-button"
            style={({ pressed }) => ({
              flexDirection: 'row',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              backgroundColor: pressed ? `${moodColor}33` : `${moodColor}1A`,
              borderWidth: 1,
              borderColor: `${moodColor}55`,
              borderRadius: 12,
              paddingVertical: 12,
              marginBottom: 28,
            })}
          >
            {conn === 'testing' ? (
              <ActivityIndicator size="small" color={connColor} />
            ) : (
              <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: connColor }} />
            )}
            <Text style={{ fontFamily: font.semibold, color: '#FFFFFF', fontSize: 12, letterSpacing: 2 }}>
              {connLabel}
            </Text>
          </Pressable>

          {/* Voice */}
          <Text
            style={{
              fontFamily: font.bold,
              color: moodColor,
              fontSize: 11,
              letterSpacing: 3,
              marginBottom: 12,
            }}
          >
            VOICE
          </Text>

          <Field
            label="Deepgram API key"
            value={dgKey}
            onChangeText={setDgKey}
            placeholder="Token used for speech-to-text"
            secureTextEntry
            hint="From deepgram.com — used to hear what you say"
            testID="deepgram-key-input"
          />

          <Field
            label="ElevenLabs API key"
            value={elKey}
            onChangeText={setElKey}
            placeholder="Key for Yugo's spoken voice"
            secureTextEntry
            hint="From elevenlabs.io — Yugo speaks back with this"
            testID="elevenlabs-key-input"
          />

          <Field
            label="ElevenLabs voice ID"
            value={voice}
            onChangeText={setVoice}
            placeholder="pNInz6obpgDQGcFmaJgB"
            hint="Which voice Yugo wears"
            testID="voice-id-input"
          />

          {/* Save */}
          <Pressable
            onPress={save}
            testID="save-settings-button"
            style={({ pressed }) => ({
              backgroundColor: pressed ? moodColor : `${moodColor}DD`,
              borderRadius: 14,
              paddingVertical: 16,
              alignItems: 'center',
              marginTop: 12,
              shadowColor: moodColor,
              shadowOpacity: 0.4,
              shadowRadius: 12,
              shadowOffset: { width: 0, height: 0 },
              elevation: 4,
            })}
          >
            <Text style={{ fontFamily: font.bold, color: '#0A0A0F', fontSize: 14, letterSpacing: 2 }}>
              {savedFlash ? 'SAVED ✓' : 'SAVE'}
            </Text>
          </Pressable>

          <Text
            style={{
              fontFamily: font.light,
              color: '#FFFFFF33',
              fontSize: 11,
              textAlign: 'center',
              marginTop: 24,
              fontStyle: 'italic',
              lineHeight: 16,
            }}
          >
            Yugo holds the keys locally on your device.{'\n'}Nothing is shared with the bridge.
          </Text>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
