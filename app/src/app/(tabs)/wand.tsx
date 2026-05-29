import React, { useEffect, useRef, useState } from 'react';
import { View, Text, Pressable, Dimensions, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  withSpring,
  withSequence,
  Easing,
} from 'react-native-reanimated';
import { Magnetometer, Gyroscope, Accelerometer } from 'expo-sensors';
import * as Haptics from 'expo-haptics';
import { useIsFocused } from '@react-navigation/native';
import { Svg, Circle, Path, Line } from 'react-native-svg';
import useYugoStore, { useMoodColor } from '@/lib/state/yugo-store';
import { sensorSpell, sensorStream } from '@/lib/api/yugo-api';
import type { SpellSample, SpellCastResult } from '@/lib/api/yugo-api';
import { font } from '@/lib/typography';
import MoodBackground from '@/components/MoodBackground';

const { width: SW } = Dimensions.get('window');
const COMPASS_SIZE = Math.min(SW - 60, 320);

// Spell-cast sampling: PRD says target 50 Hz → 20 ms update interval.
const SPELL_SAMPLE_HZ = 50;
const SPELL_INTERVAL_MS = Math.round(1000 / SPELL_SAMPLE_HZ);
const SPELL_MAX_SAMPLES = 400; // ~8 s cap

// Direction sub-mode (gyro).
type Direction = 'left' | 'right' | 'up' | 'down' | null;
const SWING_THRESHOLD = 2.2;
const COOLDOWN_MS = 280;
const HISTORY_LEN = 6;

const DIRECTION_LABEL: Record<Exclude<Direction, null>, string> = {
  left: 'LEFT',
  right: 'RIGHT',
  up: 'UP',
  down: 'DOWN',
};
const DIRECTION_ARROW: Record<Exclude<Direction, null>, string> = {
  left: '←',
  right: '→',
  up: '↑',
  down: '↓',
};

type WandMode = 'spell' | 'direction';

// --- Shared dial -----------------------------------------------------------

function CompassRings({ size, color, intensity }: { size: number; color: string; intensity: number }) {
  const cx = size / 2;
  const cy = size / 2;
  return (
    <Svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <Circle cx={cx} cy={cy} r={size / 2 - 1} stroke={color} strokeWidth={1} fill="none" opacity={0.32} />
      <Circle cx={cx} cy={cy} r={size / 3} stroke={color} strokeWidth={0.75} fill="none" opacity={0.22} />
      <Circle cx={cx} cy={cy} r={size / 6} stroke={color} strokeWidth={0.5} fill="none" opacity={0.16} />
      <Line x1={cx} y1={4} x2={cx} y2={size - 4} stroke={color} strokeWidth={0.5} opacity={0.14} />
      <Line x1={4} y1={cy} x2={size - 4} y2={cy} stroke={color} strokeWidth={0.5} opacity={0.14} />
      <Circle cx={cx} cy={cy} r={(size / 5) * Math.max(0.2, intensity)} fill={color} opacity={0.14 * intensity + 0.05} />
      <Circle cx={cx} cy={cy} r={4} fill={color} />
    </Svg>
  );
}

function DirectionArrows({ size, color, active }: { size: number; color: string; active: Direction }) {
  const cx = size / 2;
  const cy = size / 2;
  const tipOffset = 18;

  const arrow = (dir: Exclude<Direction, null>) => {
    const isActive = active === dir;
    const opacity = isActive ? 1 : 0.22;
    const fill = isActive ? color : '#FFFFFF';
    let tip = { x: cx, y: cy };
    let a = { x: cx, y: cy };
    let b = { x: cx, y: cy };
    switch (dir) {
      case 'up':
        tip = { x: cx, y: 6 };
        a = { x: cx - 10, y: 6 + tipOffset };
        b = { x: cx + 10, y: 6 + tipOffset };
        break;
      case 'down':
        tip = { x: cx, y: size - 6 };
        a = { x: cx - 10, y: size - 6 - tipOffset };
        b = { x: cx + 10, y: size - 6 - tipOffset };
        break;
      case 'left':
        tip = { x: 6, y: cy };
        a = { x: 6 + tipOffset, y: cy - 10 };
        b = { x: 6 + tipOffset, y: cy + 10 };
        break;
      case 'right':
        tip = { x: size - 6, y: cy };
        a = { x: size - 6 - tipOffset, y: cy - 10 };
        b = { x: size - 6 - tipOffset, y: cy + 10 };
        break;
    }
    return (
      <Path
        key={`a-${dir}`}
        d={`M ${tip.x} ${tip.y} L ${a.x} ${a.y} L ${b.x} ${b.y} Z`}
        fill={fill}
        opacity={opacity}
      />
    );
  };

  return (
    <Svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} pointerEvents="none">
      {(['up', 'down', 'left', 'right'] as const).map(arrow)}
    </Svg>
  );
}

// --- Screen ---------------------------------------------------------------

export default function WandScreen() {
  const { color: moodColor } = useMoodColor();
  const wandInverted = useYugoStore((s) => s.wandInverted);
  const setFieldIntensity = useYugoStore((s) => s.setFieldIntensity);
  const isFocused = useIsFocused();

  const [wandMode, setWandMode] = useState<WandMode>('spell');
  const [available, setAvailable] = useState(true);

  // Spell-cast state
  const [isCasting, setIsCasting] = useState(false);
  const [sampleCount, setSampleCount] = useState(0);
  const [lastMatch, setLastMatch] = useState<SpellCastResult | null>(null);
  const [isResolving, setIsResolving] = useState(false);

  // Direction state
  const [currentDir, setCurrentDir] = useState<Direction>(null);
  const [history, setHistory] = useState<Exclude<Direction, null>[]>([]);
  const [swingMag, setSwingMag] = useState(0);
  const [intensity, setIntensity] = useState(0);

  // Refs
  const invertedRef = useRef(wandInverted);
  useEffect(() => {
    invertedRef.current = wandInverted;
  }, [wandInverted]);

  const wandModeRef = useRef<WandMode>(wandMode);
  useEffect(() => {
    wandModeRef.current = wandMode;
  }, [wandMode]);

  const castStartRef = useRef(0);
  const castMagBufRef = useRef<SpellSample[]>([]);
  const castAccelBufRef = useRef<SpellSample[]>([]);
  const lastAccelRef = useRef<{ x: number; y: number; z: number }>({ x: 0, y: 0, z: 0 });
  const lastMagRef = useRef<{ x: number; y: number; z: number }>({ x: 0, y: 0, z: 0 });
  const lastSwingRef = useRef(0);
  const clearDirTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isCastingRef = useRef(false);

  const flashPulse = useSharedValue(0);
  const castGlow = useSharedValue(0);

  // --- Sensor subscriptions -----------------------------------------------
  useEffect(() => {
    if (!isFocused) return;
    if (Platform.OS === 'web') {
      setAvailable(false);
      return;
    }

    let magSub: { remove: () => void } | null = null;
    let gyroSub: { remove: () => void } | null = null;
    let accelSub: { remove: () => void } | null = null;

    (async () => {
      try {
        const magOk = await Magnetometer.isAvailableAsync();
        const gyroOk = await Gyroscope.isAvailableAsync();
        const accelOk = await Accelerometer.isAvailableAsync();
        if (!magOk && !gyroOk && !accelOk) {
          setAvailable(false);
          return;
        }

        Magnetometer.setUpdateInterval(SPELL_INTERVAL_MS);
        Gyroscope.setUpdateInterval(50);
        Accelerometer.setUpdateInterval(SPELL_INTERVAL_MS);

        accelSub = Accelerometer.addListener(({ x, y, z }) => {
          lastAccelRef.current = { x, y, z };
          if (isCastingRef.current) {
            const t = Date.now() - castStartRef.current;
            if (castAccelBufRef.current.length < SPELL_MAX_SAMPLES) {
              castAccelBufRef.current.push([t, x, y, z]);
            }
          }
        });

        magSub = Magnetometer.addListener(({ x, y, z }) => {
          lastMagRef.current = { x, y, z };
          const mag = Math.sqrt(x * x + y * y + z * z);

          if (isCastingRef.current) {
            const t = Date.now() - castStartRef.current;
            if (castMagBufRef.current.length < SPELL_MAX_SAMPLES) {
              castMagBufRef.current.push([t, x, y, z]);
              setSampleCount(castMagBufRef.current.length);
            }
          }

          // Intensity readout for the dial (local only — no network).
          const norm = Math.min(1, Math.max(0, (mag - 50) / 150));
          setIntensity(norm);
          setFieldIntensity(norm);
        });

        gyroSub = Gyroscope.addListener(({ x, y, z }) => {
          // Direction sub-mode only.
          if (wandModeRef.current !== 'direction') return;

          const pitch = x;
          const yaw = z;
          const m = Math.sqrt(pitch * pitch + yaw * yaw);
          setSwingMag(m);

          if (m < SWING_THRESHOLD) return;
          const now = Date.now();
          if (now - lastSwingRef.current < COOLDOWN_MS) return;

          let dir: Exclude<Direction, null>;
          if (Math.abs(pitch) > Math.abs(yaw)) {
            dir = pitch > 0 ? 'up' : 'down';
          } else {
            dir = yaw > 0 ? 'left' : 'right';
          }
          if (invertedRef.current) {
            dir = ({ up: 'down', down: 'up', left: 'right', right: 'left' } as const)[dir];
          }
          lastSwingRef.current = now;
          setCurrentDir(dir);
          setHistory((h) => [dir, ...h].slice(0, HISTORY_LEN));

          Haptics.impactAsync(
            m > 5 ? Haptics.ImpactFeedbackStyle.Heavy
              : m > 3.5 ? Haptics.ImpactFeedbackStyle.Medium
                : Haptics.ImpactFeedbackStyle.Light
          );

          if (clearDirTimerRef.current) clearTimeout(clearDirTimerRef.current);
          clearDirTimerRef.current = setTimeout(() => setCurrentDir(null), 600);
        });
      } catch (e) {
        console.warn('[Wand] sensors error', e);
        setAvailable(false);
      }
    })();

    return () => {
      magSub?.remove();
      gyroSub?.remove();
      accelSub?.remove();
      if (clearDirTimerRef.current) clearTimeout(clearDirTimerRef.current);
      setFieldIntensity(0);
    };
  }, [isFocused, setFieldIntensity]);

  // --- Spell-cast lifecycle ------------------------------------------------
  const startCast = () => {
    if (wandModeRef.current !== 'spell' || !available) return;
    castStartRef.current = Date.now();
    castMagBufRef.current = [];
    castAccelBufRef.current = [];
    setSampleCount(0);
    setLastMatch(null);
    setIsCasting(true);
    isCastingRef.current = true;
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    castGlow.value = withTiming(1, { duration: 200 });
  };

  const endCast = async () => {
    if (!isCastingRef.current) return;
    isCastingRef.current = false;
    setIsCasting(false);

    // One /sensor per gesture: send only the final reading on release, never a stream.
    sensorStream({
      magnetometer: lastMagRef.current,
      accel: lastAccelRef.current,
      gesture: 'cast',
    });

    const mag = castMagBufRef.current.slice();
    const accel = castAccelBufRef.current.slice();
    castGlow.value = withTiming(0, { duration: 300 });

    // Too-short hold: skip the POST.
    if (mag.length < 8) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      return;
    }

    setIsResolving(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    try {
      const result = await sensorSpell({
        sampleHz: SPELL_SAMPLE_HZ,
        magnetometer: mag,
        accel: accel.length ? accel : undefined,
      });
      setLastMatch(result);
      if (result.ok && result.matched) {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        flashPulse.value = withSequence(
          withTiming(1, { duration: 80 }),
          withTiming(0, { duration: 400, easing: Easing.out(Easing.quad) })
        );
      } else {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      }
    } finally {
      setIsResolving(false);
    }
  };

  // --- Animations ----------------------------------------------------------
  const scanPulse = useSharedValue(0.4);
  useEffect(() => {
    scanPulse.value = withRepeat(
      withTiming(1, { duration: 1200, easing: Easing.inOut(Easing.sin) }),
      -1,
      true
    );
  }, [scanPulse]);
  const scanStyle = useAnimatedStyle(() => ({ opacity: scanPulse.value }));

  const flashStyle = useAnimatedStyle(() => ({ opacity: flashPulse.value * 0.22 }));

  const arrowScale = useSharedValue(1);
  useEffect(() => {
    if (currentDir) {
      arrowScale.value = withSequence(
        withSpring(1.25, { damping: 8, stiffness: 200 }),
        withSpring(1, { damping: 12, stiffness: 140 })
      );
    }
  }, [currentDir, arrowScale]);
  const arrowStyle = useAnimatedStyle(() => ({ transform: [{ scale: arrowScale.value }] }));

  const castGlowStyle = useAnimatedStyle(() => ({
    opacity: 0.15 + castGlow.value * 0.4,
    transform: [{ scale: 1 + castGlow.value * 0.06 }],
  }));

  // --- Render --------------------------------------------------------------
  const matchedName = lastMatch?.matched?.move;

  return (
    <MoodBackground>
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']} testID="wand-screen">
        {/* Flash on match */}
        <Animated.View
          pointerEvents="none"
          style={[
            flashStyle,
            { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: moodColor },
          ]}
        />

        {/* Header + mode toggle */}
        <View style={{ paddingHorizontal: 20, paddingTop: 4, paddingBottom: 12 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <Text style={{ fontFamily: font.bold, color: '#FFFFFF', fontSize: 11, letterSpacing: 3, opacity: 0.5 }}>
              WAND
            </Text>
            <Animated.View style={[scanStyle, { flexDirection: 'row', alignItems: 'center', gap: 6 }]}>
              <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: moodColor }} />
              <Text style={{ fontFamily: font.semibold, color: moodColor, fontSize: 10, letterSpacing: 2 }}>
                {available ? 'READY' : 'OFFLINE'}
              </Text>
            </Animated.View>
          </View>

          {/* Sub-mode pills */}
          <View style={{ flexDirection: 'row', gap: 6, marginTop: 10 }}>
            {(['spell', 'direction'] as const).map((m) => {
              const active = wandMode === m;
              return (
                <Pressable
                  key={m}
                  onPress={() => {
                    Haptics.selectionAsync();
                    setWandMode(m);
                  }}
                  testID={`wand-submode-${m}`}
                  style={{
                    paddingHorizontal: 12,
                    paddingVertical: 6,
                    borderRadius: 14,
                    backgroundColor: active ? `${moodColor}26` : '#FFFFFF0A',
                    borderWidth: 1,
                    borderColor: active ? moodColor : '#FFFFFF15',
                  }}
                >
                  <Text style={{
                    fontFamily: active ? font.bold : font.regular,
                    color: active ? moodColor : '#FFFFFF66',
                    fontSize: 10,
                    letterSpacing: 1.5,
                  }}>
                    {m === 'spell' ? 'SPELLBOOK' : 'DIRECTION'}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        {/* Dial */}
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <Animated.View style={[castGlowStyle, { position: 'absolute', width: COMPASS_SIZE + 60, height: COMPASS_SIZE + 60, borderRadius: (COMPASS_SIZE + 60) / 2, backgroundColor: moodColor, opacity: 0.12 }]} />

          <View style={{ width: COMPASS_SIZE, height: COMPASS_SIZE, alignItems: 'center', justifyContent: 'center' }}>
            <CompassRings size={COMPASS_SIZE} color={moodColor} intensity={intensity} />

            {wandMode === 'direction' ? (
              <>
                <View style={{ position: 'absolute' }}>
                  <DirectionArrows size={COMPASS_SIZE} color={moodColor} active={currentDir} />
                </View>
                <Animated.View style={[arrowStyle, { position: 'absolute', alignItems: 'center', justifyContent: 'center' }]}>
                  <Text style={{
                    fontFamily: font.extrabold,
                    color: currentDir ? moodColor : '#FFFFFF22',
                    fontSize: 80,
                    lineHeight: 80,
                  }}
                    testID="wand-arrow"
                  >
                    {currentDir ? DIRECTION_ARROW[currentDir] : '·'}
                  </Text>
                </Animated.View>
              </>
            ) : (
              <View style={{ position: 'absolute', alignItems: 'center', justifyContent: 'center' }}>
                <Text style={{
                  fontFamily: font.extrabold,
                  color: isCasting ? moodColor : (matchedName ? moodColor : '#FFFFFF1A'),
                  fontSize: 56,
                  lineHeight: 60,
                  letterSpacing: 1,
                }}
                  testID="wand-spell-center"
                >
                  {isResolving ? '…' : matchedName ?? '✦'}
                </Text>
                <Text style={{
                  fontFamily: font.semibold,
                  color: '#FFFFFF66',
                  fontSize: 11,
                  letterSpacing: 2,
                  marginTop: 4,
                }}>
                  {isCasting ? `${sampleCount} SAMPLES` : (matchedName ? 'CAST' : 'HOLD TO CAST')}
                </Text>
              </View>
            )}
          </View>

          {/* Readouts */}
          {wandMode === 'direction' ? (
            <View style={{ marginTop: 24, alignItems: 'center', gap: 4 }}>
              <Text
                style={{ fontFamily: font.extrabold, color: '#FFFFFF', fontSize: 34, letterSpacing: 4 }}
                testID="wand-direction"
              >
                {currentDir ? DIRECTION_LABEL[currentDir] : '— — —'}
              </Text>
              <Text style={{ fontFamily: font.regular, color: '#FFFFFF66', fontSize: 11, letterSpacing: 2 }}>
                {swingMag.toFixed(1)} RAD/S
              </Text>
            </View>
          ) : (
            <View style={{ marginTop: 24, alignItems: 'center', gap: 4 }}>
              <Text style={{ fontFamily: font.bold, color: '#FFFFFF44', fontSize: 10, letterSpacing: 2 }}>
                {SPELL_SAMPLE_HZ} Hz · MAGNETOMETER
              </Text>
              {lastMatch?.matched ? (
                <Text style={{ fontFamily: font.semibold, color: moodColor, fontSize: 12, letterSpacing: 1 }}>
                  bucket {lastMatch.matched.bucket} → {lastMatch.matched.move}
                </Text>
              ) : null}
            </View>
          )}
        </View>

        {/* Direction history (only for direction mode) */}
        {wandMode === 'direction' ? (
          <View style={{ paddingHorizontal: 24, paddingBottom: 12 }}>
            <View style={{ flexDirection: 'row', gap: 8, justifyContent: 'center', minHeight: 40 }}>
              {Array.from({ length: HISTORY_LEN }).map((_, i) => {
                const dir = history[i];
                const opacity = dir ? 1 - i * 0.15 : 0.08;
                return (
                  <View
                    key={i}
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 18,
                      borderWidth: 1,
                      borderColor: dir ? moodColor : '#FFFFFF22',
                      alignItems: 'center',
                      justifyContent: 'center',
                      opacity,
                    }}
                  >
                    <Text style={{
                      fontFamily: font.bold,
                      color: dir ? moodColor : '#FFFFFF44',
                      fontSize: 18,
                      lineHeight: 20,
                    }}>
                      {dir ? DIRECTION_ARROW[dir] : '·'}
                    </Text>
                  </View>
                );
              })}
            </View>
          </View>
        ) : null}

        {/* Cast button (spell mode only) */}
        {wandMode === 'spell' ? (
          <View style={{ alignItems: 'center', paddingBottom: 18, paddingTop: 4 }}>
            <Pressable
              testID="wand-cast-button"
              disabled={!available || isResolving}
              onPressIn={startCast}
              onPressOut={endCast}
              style={({ pressed }) => ({
                width: 90,
                height: 90,
                borderRadius: 45,
                backgroundColor: isCasting ? `${moodColor}40` : (pressed ? `${moodColor}30` : `${moodColor}18`),
                borderWidth: 2,
                borderColor: moodColor,
                alignItems: 'center',
                justifyContent: 'center',
                shadowColor: moodColor,
                shadowOpacity: isCasting ? 0.9 : 0.4,
                shadowRadius: 18,
                shadowOffset: { width: 0, height: 0 },
                elevation: 10,
              })}
            >
              <Text style={{ fontSize: 34, color: moodColor }}>✦</Text>
            </Pressable>
            <Text style={{ fontFamily: font.semibold, color: '#FFFFFF66', fontSize: 10, letterSpacing: 3, marginTop: 10 }}>
              {isResolving ? 'RESOLVING…' : isCasting ? 'CASTING…' : 'HOLD TO CAST'}
            </Text>
          </View>
        ) : (
          <View style={{ paddingHorizontal: 24, paddingBottom: 18 }}>
            <Text style={{
              fontFamily: font.light,
              color: '#FFFFFF44',
              fontSize: 11,
              textAlign: 'center',
              fontStyle: 'italic',
              lineHeight: 16,
            }}>
              {Platform.OS === 'web'
                ? 'Open on iOS or Android to swing the wand'
                : 'Flick the phone · ← → ↑ ↓'}
            </Text>
          </View>
        )}
      </SafeAreaView>
    </MoodBackground>
  );
}
