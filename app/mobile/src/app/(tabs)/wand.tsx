import React, { useEffect, useRef, useState } from 'react';
import { View, Text, Pressable, Dimensions, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  Easing,
} from 'react-native-reanimated';
import { Magnetometer, Accelerometer } from 'expo-sensors';
import * as Haptics from 'expo-haptics';
import { useIsFocused } from '@react-navigation/native';
import { Svg, Circle, Line, Path } from 'react-native-svg';
import useYugoStore, { useMoodColor } from '@/lib/state/yugo-store';
import { sendSensor, playAudio, dance } from '@/lib/api/yugo-api';
import { font } from '@/lib/typography';
import MoodBackground from '@/components/MoodBackground';

const { width: SW } = Dimensions.get('window');
const RADAR_SIZE = Math.min(SW - 60, 320);

const FIELD_BASELINE = 50; // earth's field µT
const FIELD_MAX = 200;

function RadarSweep({ size, color }: { size: number; color: string }) {
  const rotation = useSharedValue(0);

  useEffect(() => {
    rotation.value = withRepeat(
      withTiming(360, { duration: 3000, easing: Easing.linear }),
      -1,
      false
    );
  }, [rotation]);

  const style = useAnimatedStyle(() => ({
    transform: [{ rotate: `${rotation.value}deg` }],
  }));

  return (
    <Animated.View
      style={[
        style,
        {
          position: 'absolute',
          width: size,
          height: size,
        },
      ]}
      pointerEvents="none"
    >
      <Svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <Path
          d={`M ${size / 2} ${size / 2} L ${size / 2 + size / 2 - 8} ${size / 2} A ${size / 2 - 8} ${size / 2 - 8} 0 0 0 ${size / 2 + (size / 2 - 8) * Math.cos(-Math.PI / 4)} ${size / 2 + (size / 2 - 8) * Math.sin(-Math.PI / 4)} Z`}
          fill={color}
          opacity={0.18}
        />
        <Line
          x1={size / 2}
          y1={size / 2}
          x2={size - 8}
          y2={size / 2}
          stroke={color}
          strokeWidth={1.5}
          opacity={0.7}
        />
      </Svg>
    </Animated.View>
  );
}

function RadarRings({ size, color, intensity }: { size: number; color: string; intensity: number }) {
  const cx = size / 2;
  const cy = size / 2;
  return (
    <Svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <Circle cx={cx} cy={cy} r={size / 2 - 1} stroke={color} strokeWidth={1} fill="none" opacity={0.35} />
      <Circle cx={cx} cy={cy} r={size / 3} stroke={color} strokeWidth={0.75} fill="none" opacity={0.25} />
      <Circle cx={cx} cy={cy} r={size / 6} stroke={color} strokeWidth={0.5} fill="none" opacity={0.18} />
      <Line x1={cx} y1={4} x2={cx} y2={size - 4} stroke={color} strokeWidth={0.5} opacity={0.18} />
      <Line x1={4} y1={cy} x2={size - 4} y2={cy} stroke={color} strokeWidth={0.5} opacity={0.18} />
      {/* Heat blob at center, scales with intensity */}
      <Circle cx={cx} cy={cy} r={(size / 4) * Math.max(0.15, intensity)} fill={color} opacity={0.18 * intensity + 0.04} />
      <Circle cx={cx} cy={cy} r={(size / 6) * Math.max(0.2, intensity)} fill={color} opacity={0.35 * intensity + 0.08} />
      <Circle cx={cx} cy={cy} r={4} fill={color} />
    </Svg>
  );
}

export default function WandScreen() {
  const { color: moodColor } = useMoodColor();
  const setFieldIntensity = useYugoStore((s) => s.setFieldIntensity);
  const fieldIntensity = useYugoStore((s) => s.fieldIntensity);
  const bridgeUrl = useYugoStore((s) => s.bridgeUrl);
  const isFocused = useIsFocused();

  const [magMagnitude, setMagMagnitude] = useState(0);
  const [accelData, setAccelData] = useState<[number, number, number]>([0, 0, 0]);
  const [lastShake, setLastShake] = useState(0);
  const [available, setAvailable] = useState(true);

  const lastSendRef = useRef(0);
  const lastHapticRef = useRef(0);

  // Subscribe sensors when focused
  useEffect(() => {
    if (!isFocused) return;
    if (Platform.OS === 'web') {
      setAvailable(false);
      return;
    }

    let magSub: { remove: () => void } | null = null;
    let accelSub: { remove: () => void } | null = null;

    (async () => {
      try {
        const magOk = await Magnetometer.isAvailableAsync();
        const accelOk = await Accelerometer.isAvailableAsync();
        if (!magOk && !accelOk) {
          setAvailable(false);
          return;
        }

        Magnetometer.setUpdateInterval(80);
        Accelerometer.setUpdateInterval(80);

        magSub = Magnetometer.addListener(({ x, y, z }) => {
          const mag = Math.sqrt(x * x + y * y + z * z);
          setMagMagnitude(mag);
          const normalized = Math.min(1, Math.max(0, (mag - FIELD_BASELINE) / (FIELD_MAX - FIELD_BASELINE)));
          setFieldIntensity(normalized);

          const now = Date.now();
          // 2Hz to bridge
          if (bridgeUrl && now - lastSendRef.current > 500) {
            lastSendRef.current = now;
            sendSensor({ mag, accel: accelData, light: 0 });
          }

          // Haptics
          if (now - lastHapticRef.current > 250) {
            if (normalized > 0.85) {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
              lastHapticRef.current = now;
            } else if (normalized > 0.65) {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
              lastHapticRef.current = now;
            } else if (normalized > 0.4) {
              Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
              lastHapticRef.current = now;
            }
          }
        });

        accelSub = Accelerometer.addListener(({ x, y, z }) => {
          setAccelData([x, y, z]);
          const totalG = Math.sqrt(x * x + y * y + z * z);
          if (totalG > 2.5) {
            const now = Date.now();
            if (now - lastShake > 1500) {
              setLastShake(now);
              Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
              playAudio('default');
              dance(120, 'wave');
            }
          }
        });
      } catch (e) {
        console.warn('[Wand] sensors error', e);
        setAvailable(false);
      }
    })();

    return () => {
      magSub?.remove();
      accelSub?.remove();
      setFieldIntensity(0);
    };
  }, [isFocused, accelData, bridgeUrl, lastShake, setFieldIntensity]);

  // Scanning pulse
  const scanPulse = useSharedValue(0.4);
  useEffect(() => {
    scanPulse.value = withRepeat(
      withTiming(1, { duration: 1200, easing: Easing.inOut(Easing.sin) }),
      -1,
      true
    );
  }, [scanPulse]);

  const scanStyle = useAnimatedStyle(() => ({ opacity: scanPulse.value }));

  return (
    <MoodBackground>
      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>

        {/* Header */}
        <View style={{ paddingHorizontal: 20, paddingTop: 4, paddingBottom: 12 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <Text style={{ fontFamily: font.bold, color: '#FFFFFF', fontSize: 11, letterSpacing: 3, opacity: 0.5 }}>
              FIELD SCANNER
            </Text>
            <Animated.View style={[scanStyle, { flexDirection: 'row', alignItems: 'center', gap: 6 }]}>
              <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: moodColor }} />
              <Text style={{ fontFamily: font.semibold, color: moodColor, fontSize: 10, letterSpacing: 2 }}>
                {available ? 'SCANNING' : 'OFFLINE'}
              </Text>
            </Animated.View>
          </View>
        </View>

        {/* Radar */}
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <View style={{ width: RADAR_SIZE, height: RADAR_SIZE, alignItems: 'center', justifyContent: 'center' }}>
            <RadarRings size={RADAR_SIZE} color={moodColor} intensity={fieldIntensity} />
            {available ? <RadarSweep size={RADAR_SIZE} color={moodColor} /> : null}
          </View>

          {/* Numeric readout */}
          <View style={{ marginTop: 24, alignItems: 'center', gap: 4 }}>
            <Text style={{ fontFamily: font.extrabold, color: '#FFFFFF', fontSize: 48, letterSpacing: -1 }}>
              {available ? magMagnitude.toFixed(1) : '--.-'}
              <Text style={{ fontFamily: font.medium, color: moodColor, fontSize: 18 }}>{' µT'}</Text>
            </Text>
            <Text style={{ fontFamily: font.regular, color: '#FFFFFF66', fontSize: 11, letterSpacing: 2 }}>
              MAGNETIC FIELD STRENGTH
            </Text>
          </View>
        </View>

        {/* Field intensity bar */}
        <View style={{ paddingHorizontal: 24, paddingBottom: 16 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 }}>
            <Text style={{ fontFamily: font.semibold, color: '#FFFFFF66', fontSize: 10, letterSpacing: 1.5 }}>
              INTENSITY
            </Text>
            <Text style={{ fontFamily: font.bold, color: moodColor, fontSize: 10, letterSpacing: 1.5 }}>
              {Math.round(fieldIntensity * 100)}%
            </Text>
          </View>
          <View style={{ height: 4, backgroundColor: '#FFFFFF10', borderRadius: 2, overflow: 'hidden' }}>
            <View
              style={{
                height: '100%',
                width: `${fieldIntensity * 100}%`,
                backgroundColor: moodColor,
                borderRadius: 2,
              }}
            />
          </View>
          <Text
            style={{
              fontFamily: font.light,
              color: '#FFFFFF44',
              fontSize: 11,
              textAlign: 'center',
              marginTop: 14,
              fontStyle: 'italic',
              lineHeight: 16,
            }}
          >
            {Platform.OS === 'web'
              ? 'Open on iOS or Android to feel the field'
              : 'Sweep your phone slowly · wave to summon music'}
          </Text>
        </View>
      </SafeAreaView>
    </MoodBackground>
  );
}
