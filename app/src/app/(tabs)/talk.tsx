import React, { useState, useRef, useCallback } from 'react';
import {
  View,
  Text,
  Pressable,
  ScrollView,
  Platform,
  ActivityIndicator,
  TextInput,
  Keyboard,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  withSequence,
  Easing,
} from 'react-native-reanimated';
import { Audio } from 'expo-av';
import { File, Paths } from 'expo-file-system';
import * as Haptics from 'expo-haptics';
import useYugoStore, { useMoodColor } from '@/lib/state/yugo-store';
import { agentSay } from '@/lib/api/yugo-api';
import { getElevenLabsKey, getVoiceId } from '@/lib/api-keys';
import MoodBackground from '@/components/MoodBackground';
import YugoOrb from '@/components/YugoOrb';
import { TalkGlyph, AlertGlyph } from '@/components/Glyph';
import { font } from '@/lib/typography';

interface ChatMessage {
  id: string;
  role: 'user' | 'yugo';
  text: string;
}

async function transcribeWithOpenbeam(uri: string): Promise<string> {
  const form = new FormData();
  // React Native FormData accepts { uri, name, type }
  form.append('audio', {
    uri,
    name: 'recording.m4a',
    type: 'audio/m4a',
  } as unknown as Blob);

  const response = await fetch('https://openbeam.tensorkit.net/infer/stt/whisper', {
    method: 'POST',
    body: form,
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Transcription error ${response.status}: ${err}`);
  }

  const data = await response.json() as {
    transcript?: string;
    text?: string;
    results?: { transcript?: string };
  };
  return data?.transcript ?? data?.text ?? data?.results?.transcript ?? '';
}

async function speakWithElevenLabs(text: string, key: string, voiceId: string): Promise<string> {
  const response = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`,
    {
      method: 'POST',
      headers: {
        'xi-api-key': key,
        'Content-Type': 'application/json',
        Accept: 'audio/mpeg',
      },
      body: JSON.stringify({
        text,
        model_id: 'eleven_turbo_v2',
        voice_settings: { stability: 0.5, similarity_boost: 0.75 },
      }),
    }
  );

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`ElevenLabs error ${response.status}: ${err}`);
  }

  const blob = await response.blob();
  const base64 = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(',')[1] ?? '');
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });

  const audioFile = new File(Paths.cache, `yugo_reply_${Date.now()}.mp3`);
  audioFile.write(base64, { encoding: 'base64' });
  return audioFile.uri;
}

export default function TalkScreen() {
  const { color: moodColor } = useMoodColor();
  const setIsSpeaking = useYugoStore((s) => s.setIsSpeaking);
  const setLastUtterance = useYugoStore((s) => s.setLastUtterance);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [textDraft, setTextDraft] = useState('');
  const [isSendingText, setIsSendingText] = useState(false);

  const recordingRef = useRef<Audio.Recording | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);
  const scrollRef = useRef<ScrollView>(null);

  // Pulse for recording state
  const pulseScale = useSharedValue(1);
  const pulseOpacity = useSharedValue(1);

  const startRecordingAnim = useCallback(() => {
    pulseScale.value = withRepeat(
      withSequence(
        withTiming(1.15, { duration: 600, easing: Easing.out(Easing.quad) }),
        withTiming(1.0, { duration: 600, easing: Easing.in(Easing.quad) })
      ),
      -1
    );
    pulseOpacity.value = withRepeat(
      withSequence(withTiming(0.5, { duration: 600 }), withTiming(1, { duration: 600 })),
      -1
    );
  }, [pulseScale, pulseOpacity]);

  const stopRecordingAnim = useCallback(() => {
    pulseScale.value = withTiming(1);
    pulseOpacity.value = withTiming(1);
  }, [pulseScale, pulseOpacity]);

  const btnStyle = useAnimatedStyle(() => ({
    transform: [{ scale: pulseScale.value }],
    opacity: pulseOpacity.value,
  }));

  const addMessage = (role: 'user' | 'yugo', text: string) => {
    const msg: ChatMessage = { id: `${Date.now()}-${role}`, role, text };
    setMessages((prev) => [...prev, msg]);
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
  };

  const startRecording = async () => {
    setErrorMsg(null);
    try {
      const perm = await Audio.requestPermissionsAsync();
      if (!perm.granted) {
        setErrorMsg('Microphone permission required');
        return;
      }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      recordingRef.current = recording;
      setIsRecording(true);
      startRecordingAnim();
      await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    } catch (e) {
      console.warn('[Talk] start recording error:', e);
      setErrorMsg('Could not start recording');
    }
  };

  const sendText = async () => {
    const t = textDraft.trim();
    if (!t || isSendingText) return;
    Keyboard.dismiss();
    setErrorMsg(null);
    setTextDraft('');
    setIsSendingText(true);
    addMessage('user', t);
    try {
      const { reply } = await agentSay(t);
      const replyText = reply || 'Yugo looks at you thoughtfully…';
      addMessage('yugo', replyText);
      setLastUtterance(replyText);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Send failed';
      setErrorMsg(msg);
    } finally {
      setIsSendingText(false);
    }
  };

  const stopRecordingAndProcess = async () => {
    if (!recordingRef.current) return;
    setIsRecording(false);
    stopRecordingAnim();
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    setIsProcessing(true);
    try {
      await recordingRef.current.stopAndUnloadAsync();
      const uri = recordingRef.current.getURI();
      recordingRef.current = null;

      if (!uri) throw new Error('No audio URI');

      const transcript = await transcribeWithOpenbeam(uri);
      if (!transcript.trim()) {
        setIsProcessing(false);
        return;
      }

      addMessage('user', transcript);

      const { reply } = await agentSay(transcript);
      const replyText = reply || 'Yugo looks at you thoughtfully…';
      addMessage('yugo', replyText);
      setLastUtterance(replyText);

      const elKey = await getElevenLabsKey();
      if (elKey) {
        const voiceId = await getVoiceId();
        setIsSpeaking(true);
        try {
          await Audio.setAudioModeAsync({ allowsRecordingIOS: false, playsInSilentModeIOS: true });
          const audioUri = await speakWithElevenLabs(replyText, elKey, voiceId);
          const { sound } = await Audio.Sound.createAsync({ uri: audioUri });
          soundRef.current = sound;
          await sound.playAsync();
          sound.setOnPlaybackStatusUpdate((status) => {
            if (status.isLoaded && status.didJustFinish) {
              setIsSpeaking(false);
              sound.unloadAsync();
            }
          });
        } catch (e) {
          console.warn('[Talk] ElevenLabs error:', e);
          setIsSpeaking(false);
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Processing failed';
      console.warn('[Talk] error:', e);
      setErrorMsg(msg);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <MoodBackground>
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>

        {/* Header */}
        <View style={{ paddingHorizontal: 20, paddingTop: 4, paddingBottom: 8 }}>
          <Text style={{ fontFamily: font.bold, color: '#FFFFFF', fontSize: 11, letterSpacing: 3, opacity: 0.5 }}>
            TALK TO YUGO
          </Text>
        </View>

        {/* Orb */}
        <View style={{ alignItems: 'center', paddingTop: 8 }}>
          <YugoOrb size={160} showGlow />
        </View>

        {/* Chat messages */}
        <ScrollView
          ref={scrollRef}
          style={{ flex: 1, marginTop: 12 }}
          contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 8, gap: 8 }}
          showsVerticalScrollIndicator={false}
        >
          {messages.length === 0 ? (
            <Text style={{
              fontFamily: font.light,
              color: '#FFFFFF33',
              fontSize: 14,
              textAlign: 'center',
              marginTop: 24,
              lineHeight: 22,
              fontStyle: 'italic',
            }}>
              {Platform.OS === 'web'
                ? 'Press and hold to speak'
                : 'Hold the button below to speak with Yugo'}
            </Text>
          ) : null}

          {messages.map((msg) => (
            <View
              key={msg.id}
              style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '80%',
                backgroundColor: msg.role === 'user' ? `${moodColor}33` : '#FFFFFF0F',
                borderWidth: 1,
                borderColor: msg.role === 'user' ? `${moodColor}55` : '#FFFFFF18',
                borderRadius: 16,
                borderBottomRightRadius: msg.role === 'user' ? 4 : 16,
                borderBottomLeftRadius: msg.role === 'yugo' ? 4 : 16,
                paddingHorizontal: 14,
                paddingVertical: 10,
              }}
            >
              {msg.role === 'yugo' ? (
                <Text style={{ fontFamily: font.bold, color: moodColor, fontSize: 10, marginBottom: 4, letterSpacing: 2 }}>
                  YUGO
                </Text>
              ) : null}
              <Text style={{
                fontFamily: font.regular,
                color: msg.role === 'user' ? '#FFFFFFCC' : '#FFFFFF',
                fontSize: 15,
                lineHeight: 22,
              }}>
                {msg.text}
              </Text>
            </View>
          ))}
        </ScrollView>

        {/* Error */}
        {errorMsg ? (
          <View style={{
            flexDirection: 'row',
            alignItems: 'center',
            gap: 8,
            marginHorizontal: 16,
            marginBottom: 8,
            backgroundColor: '#7F1D1D44',
            borderRadius: 10,
            padding: 10,
            borderWidth: 1,
            borderColor: '#EF444433',
          }}>
            <AlertGlyph size={14} color="#EF4444" />
            <Text style={{ fontFamily: font.regular, color: '#EF4444', fontSize: 13, flex: 1 }}>{errorMsg}</Text>
          </View>
        ) : null}

        {/* PTT button */}
        <View style={{ alignItems: 'center', paddingTop: 8, paddingBottom: 12 }}>
          {isProcessing ? (
            <View style={{
              width: 80,
              height: 80,
              borderRadius: 40,
              backgroundColor: '#FFFFFF0A',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <ActivityIndicator color={moodColor} />
            </View>
          ) : (
            <Animated.View style={btnStyle}>
              <Pressable
                onPressIn={startRecording}
                onPressOut={stopRecordingAndProcess}
                testID="ptt-button"
                style={{
                  width: 80,
                  height: 80,
                  borderRadius: 40,
                  backgroundColor: isRecording ? '#EF444422' : `${moodColor}22`,
                  borderWidth: 2,
                  borderColor: isRecording ? '#EF4444' : moodColor,
                  alignItems: 'center',
                  justifyContent: 'center',
                  shadowColor: isRecording ? '#EF4444' : moodColor,
                  shadowOpacity: 0.6,
                  shadowRadius: 16,
                  shadowOffset: { width: 0, height: 0 },
                  elevation: 8,
                }}
              >
                <TalkGlyph
                  size={36}
                  color={isRecording ? '#EF4444' : moodColor}
                  active
                />
              </Pressable>
            </Animated.View>
          )}
          <Text style={{ fontFamily: font.semibold, color: '#FFFFFF44', fontSize: 11, marginTop: 10, letterSpacing: 3 }}>
            {isProcessing ? 'THINKING…' : isRecording ? 'LISTENING…' : 'HOLD TO SPEAK'}
          </Text>
        </View>

        {/* Text fallback */}
        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            gap: 8,
            marginHorizontal: 16,
            marginBottom: 16,
            backgroundColor: '#FFFFFF08',
            borderWidth: 1,
            borderColor: '#FFFFFF15',
            borderRadius: 14,
            paddingHorizontal: 12,
          }}
        >
          <TextInput
            testID="talk-text-input"
            value={textDraft}
            onChangeText={setTextDraft}
            onSubmitEditing={sendText}
            placeholder="Type to Yugo…"
            placeholderTextColor="#FFFFFF33"
            returnKeyType="send"
            editable={!isSendingText}
            style={{
              flex: 1,
              fontFamily: font.regular,
              color: '#FFFFFF',
              fontSize: 14,
              paddingVertical: 10,
            }}
          />
          <Pressable
            onPress={sendText}
            disabled={!textDraft.trim() || isSendingText}
            testID="talk-text-send"
            style={({ pressed }) => ({
              paddingHorizontal: 12,
              paddingVertical: 6,
              borderRadius: 10,
              backgroundColor: textDraft.trim() ? `${moodColor}33` : '#FFFFFF0A',
              opacity: pressed ? 0.7 : 1,
            })}
          >
            {isSendingText ? (
              <ActivityIndicator size="small" color={moodColor} />
            ) : (
              <Text style={{
                fontFamily: font.bold,
                color: textDraft.trim() ? moodColor : '#FFFFFF44',
                fontSize: 11,
                letterSpacing: 1.5,
              }}>
                SEND
              </Text>
            )}
          </Pressable>
        </View>
      </SafeAreaView>
    </MoodBackground>
  );
}
