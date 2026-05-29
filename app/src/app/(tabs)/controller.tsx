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
import {
  cmdVel,
  stop,
  sleep,
  // nudge, // D-pad disabled — re-enable when ↑←→↓ comes back
  sayHello,
  sit,
  stretch,
  heart,
  trick,
} from '@/lib/api/yugo-api';
// import type { Nudge } from '@/lib/api/yugo-api'; // D-pad disabled
import MoodBackground from '@/components/MoodBackground';
import { StopGlyph } from '@/components/Glyph';
import { font } from '@/lib/typography';

const { width: SW } = Dimensions.get('window');
const PAD_SIZE = Math.min(SW * 0.5, 220);
const THUMB_RADIUS = PAD_SIZE * 0.18;
const MAX_OFFSET = PAD_SIZE / 2 - THUMB_RADIUS;

// Joystick fires re-sends at 15 Hz to satisfy the ~0.5s deadman.
const JOYSTICK_TICK_MS = 66;
// D-pad re-fires the same nudge every 250 ms while held (~4 Hz).
// const DPAD_TICK_MS = 250; // D-pad disabled

type DedicatedTrickId = 'hello' | 'sit' | 'stretch' | 'heart';
type GenericTrickId = 'WiggleHips' | 'Dance' | 'StandUp' | 'StandDown';

const DEDICATED_TRICKS: { id: DedicatedTrickId; label: string; emoji: string }[] = [
  { id: 'hello', label: 'Hello', emoji: '👋' },
  { id: 'sit', label: 'Sit', emoji: '🪑' },
  { id: 'stretch', label: 'Stretch', emoji: '🤸' },
  { id: 'heart', label: 'Heart', emoji: '🤞' },
];

const GENERIC_TRICKS: { id: GenericTrickId; label: string; emoji: string }[] = [
  { id: 'WiggleHips', label: 'Wiggle', emoji: '💃' },
  { id: 'Dance', label: 'Dance', emoji: '🕺' },
  { id: 'StandUp', label: 'Stand', emoji: '🧍' },
  { id: 'StandDown', label: 'Down', emoji: '🐕' },
];

export default function ControllerScreen() {
  const { color: moodColor } = useMoodColor();
  const navInverted = useYugoStore((s) => s.navInverted);
  const toggleNavInverted = useYugoStore((s) => s.toggleNavInverted);

  const thumbX = useSharedValue(0);
  const thumbY = useSharedValue(0);

  // PRD axes: vx forward/back, vy strafe, wz yaw.
  // Joystick maps stick-Y → vx (forward when pushed up) and stick-X → wz (yaw).
  // Strafe (vy) stays 0 here — keep single stick for now.
  const velRef = useRef({ vx: 0, vy: 0, wz: 0 });
  const isActiveRef = useRef(false);
  const invertedRef = useRef(navInverted);
  useEffect(() => {
    invertedRef.current = navInverted;
  }, [navInverted]);

  const updateVelocity = useCallback((dx: number, dy: number) => {
    const sign = invertedRef.current ? 1 : -1;
    velRef.current = {
      vx: (sign * dy) / MAX_OFFSET,
      vy: 0,
      wz: dx / MAX_OFFSET,
    };
  }, []);

  const activate = useCallback(() => {
    isActiveRef.current = true;
  }, []);

  const deactivate = useCallback(() => {
    isActiveRef.current = false;
    velRef.current = { vx: 0, vy: 0, wz: 0 };
    stop();
  }, []);

  // Joystick tick: re-send held velocity to keep the dog moving.
  useEffect(() => {
    const interval = setInterval(() => {
      if (isActiveRef.current) {
        const v = velRef.current;
        cmdVel(v.vx, v.vy, v.wz);
      }
    }, JOYSTICK_TICK_MS);
    return () => clearInterval(interval);
  }, []);

  const panGesture = Gesture.Pan()
    .onBegin(() => {
      runOnJS(activate)();
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

  // --- D-pad held-repeat (disabled) ---------------------------------------
  // const dpadTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // const dpadDirRef = useRef<Nudge | null>(null);
  //
  // const startNudge = (dir: Nudge) => {
  //   if (dpadTimerRef.current) clearInterval(dpadTimerRef.current);
  //   dpadDirRef.current = dir;
  //   Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  //   nudge(dir);
  //   dpadTimerRef.current = setInterval(() => {
  //     if (dpadDirRef.current) nudge(dpadDirRef.current);
  //   }, DPAD_TICK_MS);
  // };
  //
  // const endNudge = () => {
  //   if (dpadTimerRef.current) {
  //     clearInterval(dpadTimerRef.current);
  //     dpadTimerRef.current = null;
  //   }
  //   dpadDirRef.current = null;
  //   stop();
  // };
  //
  // useEffect(() => () => {
  //   if (dpadTimerRef.current) clearInterval(dpadTimerRef.current);
  // }, []);

  // --- Tricks --------------------------------------------------------------
  const handleDedicated = async (id: DedicatedTrickId) => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    switch (id) {
      case 'hello': return sayHello();
      case 'sit': return sit();
      case 'stretch': return stretch();
      case 'heart': return heart();
    }
  };

  const handleGeneric = async (id: GenericTrickId) => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    await trick(id);
  };

  const handleStop = async () => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
    await stop();
  };

  const handleSleep = async () => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
    await sleep();
  };

  const handleToggleInvert = async () => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    toggleNavInverted();
  };

  return (
    <MoodBackground>
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        {/* Header */}
        <View style={{ paddingHorizontal: 20, paddingTop: 4, paddingBottom: 8 }}>
          <Text style={{ fontFamily: font.bold, color: '#FFFFFF', fontSize: 11, letterSpacing: 3, opacity: 0.5 }}>
            CONTROLLER
          </Text>
        </View>

        {/* Joystick (D-pad disabled) */}
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 12 }}>
          {/* D-pad disabled — re-enable when ↑←→↓ comes back
          <DPad color={moodColor} onStart={startNudge} onEnd={endNudge} />
          <View style={{ flex: 1 }} />
          */}

          {/* Joystick */}
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
        </View>

        {/* Action row: invert toggle (left), STOP (yellow) + SLEEP (red) circles (right) */}
        <View style={{
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingHorizontal: 20,
          paddingBottom: 6,
        }}>
          <Pressable
            onPress={handleToggleInvert}
            testID="nav-invert-toggle"
            style={({ pressed }) => ({
              flexDirection: 'row',
              alignItems: 'center',
              gap: 8,
              paddingHorizontal: 12,
              paddingVertical: 10,
              borderRadius: 20,
              backgroundColor: navInverted ? `${moodColor}33` : '#FFFFFF0A',
              borderWidth: 1,
              borderColor: navInverted ? moodColor : '#FFFFFF15',
              opacity: pressed ? 0.7 : 1,
            })}
          >
            <Text style={{ fontSize: 14, color: navInverted ? moodColor : '#FFFFFF66' }}>⇅</Text>
            <Text style={{
              fontFamily: navInverted ? font.semibold : font.regular,
              color: navInverted ? moodColor : '#FFFFFF66',
              fontSize: 11,
              letterSpacing: 1.5,
            }}>
              {navInverted ? 'INVERTED' : 'INVERT'}
            </Text>
          </Pressable>

          <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
            <Pressable
              onPress={handleStop}
              testID="stop-button"
              style={({ pressed }) => ({
                width: 64,
                height: 64,
                borderRadius: 32,
                backgroundColor: pressed ? '#CA8A04' : '#854D0E',
                borderWidth: 2,
                borderColor: '#FACC15',
                alignItems: 'center',
                justifyContent: 'center',
                shadowColor: '#FACC15',
                shadowOpacity: 0.6,
                shadowRadius: 12,
                shadowOffset: { width: 0, height: 0 },
                elevation: 8,
              })}
            >
              <StopGlyph size={28} color="#FACC15" />
            </Pressable>

            <Pressable
              onPress={handleSleep}
              testID="sleep-button"
              style={({ pressed }) => ({
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
              <Text style={{ fontSize: 26 }}>😴</Text>
            </Pressable>
          </View>
        </View>

        {/* Trick buttons — dedicated row */}
        <View style={{ paddingHorizontal: 16, paddingBottom: 8 }}>
          <Text style={{ fontFamily: font.bold, color: '#FFFFFF44', fontSize: 10, letterSpacing: 2, marginBottom: 8 }}>
            TRICKS
          </Text>
          <View style={{ flexDirection: 'row', gap: 8, marginBottom: 8 }}>
            {DEDICATED_TRICKS.map((t) => (
              <Pressable
                key={t.id}
                onPress={() => handleDedicated(t.id)}
                testID={`trick-${t.id}`}
                style={({ pressed }) => ({
                  flex: 1,
                  aspectRatio: 1,
                  backgroundColor: pressed ? `${moodColor}22` : '#FFFFFF0A',
                  borderWidth: 1,
                  borderColor: `${moodColor}44`,
                  borderRadius: 16,
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 4,
                })}
              >
                <Text style={{ fontSize: 22 }}>{t.emoji}</Text>
                <Text style={{ fontFamily: font.semibold, color: moodColor, fontSize: 10, letterSpacing: 0.5 }}>{t.label}</Text>
              </Pressable>
            ))}
          </View>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {GENERIC_TRICKS.map((t) => (
              <Pressable
                key={t.id}
                onPress={() => handleGeneric(t.id)}
                testID={`trick-${t.id.toLowerCase()}`}
                style={({ pressed }) => ({
                  flex: 1,
                  aspectRatio: 1.2,
                  backgroundColor: pressed ? `${moodColor}1A` : '#FFFFFF06',
                  borderWidth: 1,
                  borderColor: '#FFFFFF15',
                  borderRadius: 14,
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 2,
                })}
              >
                <Text style={{ fontSize: 18 }}>{t.emoji}</Text>
                <Text style={{ fontFamily: font.regular, color: '#FFFFFF88', fontSize: 9, letterSpacing: 0.5 }}>{t.label}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      </SafeAreaView>
    </MoodBackground>
  );
}

// --- D-pad component (disabled) ------------------------------------------
//
// function DPad({
//   color,
//   onStart,
//   onEnd,
// }: {
//   color: string;
//   onStart: (dir: Nudge) => void;
//   onEnd: () => void;
// }) {
//   const arm = (dir: Nudge, glyph: string, testID: string) => (
//     <Pressable
//       key={dir}
//       testID={testID}
//       onPressIn={() => onStart(dir)}
//       onPressOut={onEnd}
//       style={({ pressed }) => ({
//         width: 44,
//         height: 44,
//         borderRadius: 10,
//         backgroundColor: pressed ? `${color}44` : '#FFFFFF0A',
//         borderWidth: 1,
//         borderColor: pressed ? color : '#FFFFFF18',
//         alignItems: 'center',
//         justifyContent: 'center',
//       })}
//     >
//       <Text style={{ fontFamily: font.bold, color: color, fontSize: 22, lineHeight: 24 }}>
//         {glyph}
//       </Text>
//     </Pressable>
//   );
//
//   return (
//     <View testID="dpad" style={{ alignItems: 'center', gap: 6 }}>
//       {arm('up', '↑', 'dpad-up')}
//       <View style={{ flexDirection: 'row', gap: 6 }}>
//         {arm('left', '←', 'dpad-left')}
//         <View style={{ width: 44, height: 44 }} />
//         {arm('right', '→', 'dpad-right')}
//       </View>
//       {arm('down', '↓', 'dpad-down')}
//     </View>
//   );
// }
