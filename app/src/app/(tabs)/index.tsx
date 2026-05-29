import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  Image,
  Animated as RNAnimated,
  Dimensions,
  Pressable,
  TextInput,
  Keyboard,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';
import useYugoStore, { useMoodColor, MOOD_COLORS } from '@/lib/state/yugo-store';
import type { YugoMode } from '@/lib/state/yugo-store';
import { setMode } from '@/lib/api/yugo-api';
import YugoOrb from '@/components/YugoOrb';
import MoodBackground from '@/components/MoodBackground';
import WSStatus from '@/components/WSStatus';
import { BatteryGlyph, PersonGlyph } from '@/components/Glyph';
import { font } from '@/lib/typography';

const MODES: { id: YugoMode; label: string }[] = [
  { id: 'creature', label: 'Creature' },
  { id: 'wand', label: 'Wand' },
  { id: 'personal', label: 'Personal' },
  { id: 'find', label: 'Find' },
  { id: 'friend', label: 'Friend' },
];

const { width: SW } = Dimensions.get('window');

const MODE_LABELS: Record<string, string> = {
  creature: 'CREATURE',
  ghost: 'GHOST',
  hunt: 'HUNT',
  scanner: 'SCANNER',
  music: 'MUSIC',
  meditation: 'MEDITATION',
};

function BatteryIcon({ level }: { level: number }) {
  const color = level > 50 ? '#22C55E' : level > 20 ? '#F59E0B' : '#EF4444';
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
      <BatteryGlyph size={22} color={color} level={level} />
      <Text style={{ fontFamily: font.semibold, color, fontSize: 11, letterSpacing: 1 }}>
        {level}%
      </Text>
    </View>
  );
}

export default function PortholeScreen() {
  const bridgeUrl = useYugoStore((s) => s.bridgeUrl);
  const mood = useYugoStore((s) => s.mood);
  const mode = useYugoStore((s) => s.mode);
  const battery = useYugoStore((s) => s.battery);
  const personCount = useYugoStore((s) => s.personCount);
  const fieldIntensity = useYugoStore((s) => s.fieldIntensity);
  const isSpeaking = useYugoStore((s) => s.isSpeaking);
  const lastUtterance = useYugoStore((s) => s.lastUtterance);
  const findTarget = useYugoStore((s) => s.findTarget);
  const setFindTarget = useYugoStore((s) => s.setFindTarget);

  const { color: moodColor } = useMoodColor();

  const [pendingTarget, setPendingTarget] = useState(findTarget);

  const handleMode = async (m: YugoMode) => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    if (m === 'find') {
      useYugoStore.getState().setMode(m);
      if (findTarget) await setMode('find', findTarget);
      return;
    }
    await setMode(m);
    useYugoStore.getState().setMode(m);
  };

  const submitFindTarget = async () => {
    const t = pendingTarget.trim();
    if (!t) return;
    Keyboard.dismiss();
    setFindTarget(t);
    await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    await setMode('find', t);
  };

  // Camera refresh key (MJPEG polling)
  const [camKey, setCamKey] = useState(0);
  const camKeyRef = useRef(0);
  useEffect(() => {
    if (!bridgeUrl) return;
    const interval = setInterval(() => {
      camKeyRef.current += 1;
      setCamKey(camKeyRef.current);
    }, 500);
    return () => clearInterval(interval);
  }, [bridgeUrl]);

  // Caption fade
  const captionOpacity = useRef(new RNAnimated.Value(0)).current;
  useEffect(() => {
    if (lastUtterance) {
      RNAnimated.timing(captionOpacity, { toValue: 1, duration: 300, useNativeDriver: true }).start();
    } else {
      RNAnimated.timing(captionOpacity, { toValue: 0, duration: 300, useNativeDriver: true }).start();
    }
  }, [lastUtterance, captionOpacity]);

  const moodLabel = mood.charAt(0).toUpperCase() + mood.slice(1);

  return (
    <MoodBackground>
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>

        {/* Top bar */}
        <View style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingHorizontal: 20,
          paddingVertical: 10,
        }}>
          <Text style={{
            fontFamily: font.extrabold,
            color: '#FFFFFF',
            fontSize: 20,
            letterSpacing: 6,
          }}>
            YUGO
          </Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            {/* Mode badge */}
            <View style={{
              backgroundColor: `${moodColor}22`,
              borderWidth: 1,
              borderColor: `${moodColor}55`,
              paddingHorizontal: 8,
              paddingVertical: 3,
              borderRadius: 6,
            }}>
              <Text style={{ fontFamily: font.bold, color: moodColor, fontSize: 10, letterSpacing: 2 }}>
                {MODE_LABELS[mode] ?? mode.toUpperCase()}
              </Text>
            </View>
            <BatteryIcon level={battery} />
            <WSStatus />
          </View>
        </View>

        {/* Mode selector */}
        <View style={{ paddingHorizontal: 16, paddingBottom: 8 }}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ gap: 8, paddingRight: 16 }}
            style={{ flexGrow: 0 }}
          >
            {MODES.map((m) => {
              const active = mode === m.id;
              return (
                <Pressable
                  key={m.id}
                  onPress={() => handleMode(m.id)}
                  testID={`mode-${m.id}`}
                  style={{
                    paddingHorizontal: 14,
                    paddingVertical: 8,
                    borderRadius: 20,
                    backgroundColor: active ? `${moodColor}33` : '#FFFFFF0A',
                    borderWidth: 1,
                    borderColor: active ? moodColor : '#FFFFFF15',
                  }}
                >
                  <Text style={{
                    fontFamily: active ? font.semibold : font.regular,
                    color: active ? moodColor : '#FFFFFF66',
                    fontSize: 12,
                    letterSpacing: 0.5,
                  }}>
                    {m.label}
                  </Text>
                </Pressable>
              );
            })}
          </ScrollView>

          {mode === 'find' ? (
            <View
              style={{
                marginTop: 10,
                flexDirection: 'row',
                alignItems: 'center',
                gap: 8,
                backgroundColor: '#FFFFFF08',
                borderWidth: 1,
                borderColor: `${moodColor}55`,
                borderRadius: 12,
                paddingHorizontal: 12,
              }}
            >
              <Text style={{ fontFamily: font.bold, color: moodColor, fontSize: 10, letterSpacing: 2 }}>
                FIND
              </Text>
              <TextInput
                testID="find-target-input"
                value={pendingTarget}
                onChangeText={setPendingTarget}
                onSubmitEditing={submitFindTarget}
                placeholder="who? (e.g. Sarah)"
                placeholderTextColor="#FFFFFF33"
                returnKeyType="search"
                autoCapitalize="words"
                style={{
                  flex: 1,
                  fontFamily: font.regular,
                  color: '#FFFFFF',
                  fontSize: 14,
                  paddingVertical: 10,
                }}
              />
              <Pressable
                onPress={submitFindTarget}
                disabled={!pendingTarget.trim()}
                testID="find-target-submit"
                style={({ pressed }) => ({
                  paddingHorizontal: 10,
                  paddingVertical: 6,
                  borderRadius: 10,
                  backgroundColor: pendingTarget.trim() ? `${moodColor}33` : '#FFFFFF0A',
                  opacity: pressed ? 0.7 : 1,
                })}
              >
                <Text style={{
                  fontFamily: font.bold,
                  color: pendingTarget.trim() ? moodColor : '#FFFFFF44',
                  fontSize: 11,
                  letterSpacing: 1.5,
                }}>
                  GO
                </Text>
              </Pressable>
            </View>
          ) : null}
        </View>

        {/* Camera + Orb area */}
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>

          {/* Camera feed as ghosted background */}
          {bridgeUrl ? (
            <View style={{
              position: 'absolute',
              width: SW * 0.85,
              height: SW * 0.85,
              borderRadius: SW * 0.425,
              overflow: 'hidden',
              opacity: 0.15,
            }}>
              <Image
                key={camKey}
                source={{ uri: `${bridgeUrl}/video_feed/color_image` }}
                style={{ width: '100%', height: '100%' }}
                resizeMode="cover"
              />
            </View>
          ) : null}

          {/* Aura rings */}
          {[1.6, 1.35, 1.1].map((multiplier, i) => (
            <View
              key={i}
              style={{
                position: 'absolute',
                width: 300 * multiplier,
                height: 300 * multiplier,
                borderRadius: 150 * multiplier,
                borderWidth: 1,
                borderColor: moodColor,
                opacity: (fieldIntensity * 0.4 + 0.05) * (1 - i * 0.25),
              }}
            />
          ))}

          {/* Person count indicator */}
          {personCount > 0 ? (
            <View style={{
              position: 'absolute',
              top: -20,
              right: SW * 0.05,
              flexDirection: 'row',
              alignItems: 'center',
              gap: 4,
            }}>
              <PersonGlyph size={14} color={moodColor} />
              <Text style={{ fontFamily: font.bold, color: moodColor, fontSize: 12 }}>
                {personCount}
              </Text>
            </View>
          ) : null}

          {/* Central orb */}
          <YugoOrb size={260} showGlow />
        </View>

        {/* Bottom mood + caption */}
        <View style={{ paddingHorizontal: 24, paddingBottom: 12, alignItems: 'center', gap: 8 }}>
          <View style={{
            backgroundColor: `${moodColor}18`,
            borderWidth: 1,
            borderColor: `${moodColor}33`,
            paddingHorizontal: 20,
            paddingVertical: 8,
            borderRadius: 20,
          }}>
            <Text style={{
              fontFamily: font.bold,
              color: moodColor,
              fontSize: 14,
              letterSpacing: 4,
              textTransform: 'uppercase',
            }}>
              {moodLabel}
            </Text>
          </View>

          {lastUtterance ? (
            <RNAnimated.View style={{ opacity: captionOpacity }}>
              <View style={{
                backgroundColor: '#FFFFFF0E',
                borderRadius: 12,
                paddingHorizontal: 16,
                paddingVertical: 8,
                maxWidth: SW - 48,
              }}>
                <Text style={{
                  fontFamily: isSpeaking ? font.light : font.regular,
                  color: '#FFFFFFCC',
                  fontSize: 14,
                  textAlign: 'center',
                  fontStyle: isSpeaking ? 'italic' : 'normal',
                  lineHeight: 20,
                }}>
                  {isSpeaking ? `"${lastUtterance}"` : lastUtterance}
                </Text>
              </View>
            </RNAnimated.View>
          ) : null}
        </View>
      </SafeAreaView>
    </MoodBackground>
  );
}
