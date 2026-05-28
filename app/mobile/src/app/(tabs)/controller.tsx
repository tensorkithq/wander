import React, { useEffect, useRef, useCallback } from 'react';
import { View, Text, Pressable, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  runOnJS,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';
import useYugoStore, { useMoodColor } from '@/lib/state/yugo-store';
import { cmdVel, stop, trick, setMode } from '@/lib/api/yugo-api';
import MoodBackground from '@/components/MoodBackground';
import { StopGlyph } from '@/components/Glyph';
import { font } from '@/lib/typography';
import type { YugoMode } from '@/lib/state/yugo-store';

const { width: SW } = Dimensions.get('window');
const PAD_SIZE = Math.min(SW * 0.55, 240);
const THUMB_RADIUS = PAD_SIZE * 0.18;
const MAX_OFFSET = PAD_SIZE / 2 - THUMB_RADIUS;

const MODES: { id: YugoMode; label: string }[] = [
  { id: 'creature', label: 'Creature' },
  { id: 'ghost', label: 'Ghost' },
  { id: 'hunt', label: 'Hunt' },
  { id: 'scanner', label: 'Scanner' },
  { id: 'music', label: 'Music' },
  { id: 'meditation', label: 'Meditation' },
];

const TRICKS: { id: 'Hello' | 'WiggleHips' | 'Stretch' | 'FingerHeart'; label: string; emoji: string }[] = [
  { id: 'Hello', label: 'Hello', emoji: '👋' },
  { id: 'WiggleHips', label: 'Wiggle', emoji: '💃' },
  { id: 'Stretch', label: 'Stretch', emoji: '🤸' },
  { id: 'FingerHeart', label: '♥ Heart', emoji: '🤞' },
];

export default function ControllerScreen() {
  const currentMode = useYugoStore((s) => s.mode);
  const { color: moodColor } = useMoodColor();

  const thumbX = useSharedValue(0);
  const thumbY = useSharedValue(0);

  const velocityRef = useRef({ linear: 0, angular: 0 });
  const isActiveRef = useRef(false);

  const updateVelocity = useCallback((dx: number, dy: number) => {
    velocityRef.current = {
      linear: -dy / MAX_OFFSET,
      angular: dx / MAX_OFFSET,
    };
  }, []);

  const deactivate = useCallback(() => {
    isActiveRef.current = false;
    velocityRef.current = { linear: 0, angular: 0 };
    stop();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      if (isActiveRef.current) {
        cmdVel(velocityRef.current.linear, velocityRef.current.angular);
      }
    }, 100);
    return () => clearInterval(interval);
  }, []);

  const panGesture = Gesture.Pan()
    .onBegin(() => {
      runOnJS(() => { isActiveRef.current = true; })();
    })
    .onUpdate((e) => {
      const dx = Math.min(Math.max(e.translationX, -MAX_OFFSET), MAX_OFFSET);
      const dy = Math.min(Math.max(e.translationY, -MAX_OFFSET), MAX_OFFSET);
      thumbX.value = dx;
      thumbY.value = dy;
      runOnJS(updateVelocity)(dx, dy);
    })
    .onEnd(() => {
      thumbX.value = withTiming(0, { duration: 200 });
      thumbY.value = withTiming(0, { duration: 200 });
      runOnJS(deactivate)();
    })
    .onFinalize(() => {
      thumbX.value = withTiming(0, { duration: 200 });
      thumbY.value = withTiming(0, { duration: 200 });
      runOnJS(deactivate)();
    });

  const thumbStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: thumbX.value }, { translateY: thumbY.value }],
  }));

  const handleMode = async (m: YugoMode) => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await setMode(m);
    useYugoStore.getState().setMode(m);
  };

  const handleTrick = async (t: 'Hello' | 'WiggleHips' | 'Stretch' | 'FingerHeart') => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    await trick(t);
  };

  const handleStop = async () => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
    await stop();
  };

  return (
    <MoodBackground>
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>

        {/* Header */}
        <View style={{ paddingHorizontal: 20, paddingTop: 4, paddingBottom: 8 }}>
          <Text style={{ fontFamily: font.bold, color: '#FFFFFF', fontSize: 11, letterSpacing: 3, opacity: 0.5 }}>
            CONTROLLER
          </Text>
        </View>

        {/* Mode selector */}
        <View style={{ paddingHorizontal: 16 }}>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {MODES.map((m) => {
              const active = currentMode === m.id;
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
          </View>
        </View>

        {/* Joystick */}
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <GestureDetector gesture={panGesture}>
            <View
              style={{
                width: PAD_SIZE,
                height: PAD_SIZE,
                borderRadius: PAD_SIZE / 2,
                backgroundColor: '#FFFFFF08',
                borderWidth: 1.5,
                borderColor: `${moodColor}33`,
                alignItems: 'center',
                justifyContent: 'center',
              }}
              testID="joystick-pad"
            >
              {/* Crosshair lines */}
              <View style={{
                position: 'absolute',
                width: PAD_SIZE * 0.7,
                height: 0.5,
                backgroundColor: `${moodColor}22`,
              }} />
              <View style={{
                position: 'absolute',
                height: PAD_SIZE * 0.7,
                width: 0.5,
                backgroundColor: `${moodColor}22`,
              }} />

              {/* Thumb */}
              <Animated.View
                style={[
                  thumbStyle,
                  {
                    width: THUMB_RADIUS * 2,
                    height: THUMB_RADIUS * 2,
                    borderRadius: THUMB_RADIUS,
                    backgroundColor: moodColor,
                    shadowColor: moodColor,
                    shadowOpacity: 0.8,
                    shadowRadius: 12,
                    shadowOffset: { width: 0, height: 0 },
                    elevation: 8,
                  },
                ]}
              />
            </View>
          </GestureDetector>

          {/* STOP button */}
          <Pressable
            onPress={handleStop}
            testID="stop-button"
            style={({ pressed }) => ({
              position: 'absolute',
              bottom: 0,
              right: 16,
              width: 64,
              height: 64,
              borderRadius: 32,
              backgroundColor: pressed ? '#DC2626' : '#7F1D1D',
              borderWidth: 2,
              borderColor: '#EF4444',
              alignItems: 'center',
              justifyContent: 'center',
              shadowColor: '#EF4444',
              shadowOpacity: 0.6,
              shadowRadius: 12,
              shadowOffset: { width: 0, height: 0 },
              elevation: 8,
            })}
          >
            <StopGlyph size={28} color="#EF4444" />
          </Pressable>
        </View>

        {/* Trick buttons */}
        <View style={{ paddingHorizontal: 16, paddingBottom: 8 }}>
          <Text style={{ fontFamily: font.bold, color: '#FFFFFF44', fontSize: 10, letterSpacing: 2, marginBottom: 10 }}>
            TRICKS
          </Text>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            {TRICKS.map((t) => (
              <Pressable
                key={t.id}
                onPress={() => handleTrick(t.id)}
                testID={`trick-${t.id.toLowerCase()}`}
                style={({ pressed }) => ({
                  flex: 1,
                  aspectRatio: 1,
                  backgroundColor: pressed ? `${moodColor}22` : '#FFFFFF0A',
                  borderWidth: 1,
                  borderColor: '#FFFFFF15',
                  borderRadius: 16,
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 4,
                })}
              >
                <Text style={{ fontSize: 22 }}>{t.emoji}</Text>
                <Text style={{ fontFamily: font.semibold, color: '#FFFFFF88', fontSize: 10, letterSpacing: 0.5 }}>{t.label}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      </SafeAreaView>
    </MoodBackground>
  );
}
