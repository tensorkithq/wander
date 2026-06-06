import React, { useEffect, useRef, useState } from 'react';
import { View, Text, Pressable, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  Easing,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';
import useYugoStore from '@/lib/state/yugo-store';
import { sit, trick, setMode } from '@/lib/api/yugo-api';
import { font } from '@/lib/typography';
import YugoOrb from '@/components/YugoOrb';

const { width: SW } = Dimensions.get('window');
const ORB_SIZE = Math.min(SW * 0.66, 260);

const MEDITATION_COLOR = '#6366F1';
const MEDITATION_DEEP = '#0D0F1E';

type Phase = 'inhale' | 'holdIn' | 'exhale' | 'holdOut';

const PHASES: { id: Phase; label: string; duration: number; scale: number }[] = [
  { id: 'inhale', label: 'Breathe in', duration: 4000, scale: 1.35 },
  { id: 'holdIn', label: 'Hold', duration: 2000, scale: 1.35 },
  { id: 'exhale', label: 'Breathe out', duration: 4000, scale: 1.0 },
  { id: 'holdOut', label: 'Rest', duration: 2000, scale: 1.0 },
];

const PROMPTS = [
  'Feel the calm settle in',
  'You are safe here',
  'Yugo is breathing with you',
  'Let the day go',
  'Sink a little deeper',
  'Soft. Slow. Open.',
  'Nothing to hold on to',
];

function BreathRing({ phase, active }: { phase: Phase; active: boolean }) {
  const scale = useSharedValue(1);
  const opacity = useSharedValue(0.4);

  useEffect(() => {
    if (!active) {
      scale.value = withTiming(1, { duration: 800 });
      opacity.value = withTiming(0.3, { duration: 800 });
      return;
    }
    const cfg = PHASES.find((p) => p.id === phase);
    if (!cfg) return;
    scale.value = withTiming(cfg.scale, {
      duration: cfg.duration,
      easing: Easing.inOut(Easing.sin),
    });
    opacity.value = withTiming(phase === 'inhale' || phase === 'holdIn' ? 0.7 : 0.4, {
      duration: cfg.duration,
      easing: Easing.inOut(Easing.sin),
    });
  }, [phase, active, scale, opacity]);

  const style = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
    opacity: opacity.value,
  }));

  return (
    <Animated.View
      style={[
        style,
        {
          position: 'absolute',
          width: ORB_SIZE * 1.6,
          height: ORB_SIZE * 1.6,
          borderRadius: ORB_SIZE * 0.8,
          borderWidth: 1,
          borderColor: MEDITATION_COLOR,
        },
      ]}
      pointerEvents="none"
    />
  );
}

function InnerHalo({ phase, active }: { phase: Phase; active: boolean }) {
  const scale = useSharedValue(1);

  useEffect(() => {
    if (!active) {
      scale.value = withTiming(1, { duration: 800 });
      return;
    }
    const cfg = PHASES.find((p) => p.id === phase);
    if (!cfg) return;
    scale.value = withTiming(cfg.scale * 0.85, {
      duration: cfg.duration,
      easing: Easing.inOut(Easing.sin),
    });
  }, [phase, active, scale]);

  const style = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  return (
    <Animated.View
      style={[
        style,
        {
          position: 'absolute',
          width: ORB_SIZE * 1.25,
          height: ORB_SIZE * 1.25,
          borderRadius: ORB_SIZE * 0.625,
          borderWidth: 1,
          borderColor: `${MEDITATION_COLOR}55`,
        },
      ]}
      pointerEvents="none"
    />
  );
}

export default function ZenScreen() {
  const setMood = useYugoStore((s) => s.setMood);
  const storeSetMode = useYugoStore((s) => s.setMode);

  const [active, setActive] = useState(false);
  const [phaseIdx, setPhaseIdx] = useState(0);
  const [promptIdx, setPromptIdx] = useState(0);

  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const promptTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Lock mood to meditation locally when active, and sit the dog (zen posture).
  useEffect(() => {
    if (active) {
      setMood('meditation');
      storeSetMode('meditation');
      setMode('meditation');
      sit(); // dedicated /sit route — zen posture
    }
  }, [active, setMood, storeSetMode]);

  // Drive phase loop
  useEffect(() => {
    if (!active) {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      return;
    }
    const phase = PHASES[phaseIdx];
    if (!phase) return;
    Haptics.selectionAsync();
    timeoutRef.current = setTimeout(() => {
      setPhaseIdx((i) => (i + 1) % PHASES.length);
    }, phase.duration);
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [active, phaseIdx]);

  // Cycle prompts every 12s
  useEffect(() => {
    if (!active) {
      if (promptTimerRef.current) clearInterval(promptTimerRef.current);
      return;
    }
    promptTimerRef.current = setInterval(() => {
      setPromptIdx((i) => (i + 1) % PROMPTS.length);
    }, 12000);
    return () => {
      if (promptTimerRef.current) clearInterval(promptTimerRef.current);
    };
  }, [active]);

  // Prompt fade
  const promptOpacity = useSharedValue(0);
  useEffect(() => {
    promptOpacity.value = 0;
    promptOpacity.value = withTiming(1, { duration: 800 });
  }, [promptIdx, promptOpacity]);
  const promptStyle = useAnimatedStyle(() => ({ opacity: promptOpacity.value }));

  const phase = PHASES[phaseIdx];

  const toggle = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    // Ending the session → stand the dog back up. (active is the pre-toggle value,
    // so this only fires on a real END press, never on mount.)
    if (active) trick('StandUp'); // rise from the seated zen posture (BalanceStand won't lift from a full sit)
    setActive((a) => !a);
    setPhaseIdx(0);
  };

  return (
    <View style={{ flex: 1, backgroundColor: MEDITATION_DEEP }}>
      {/* Deep ambient gradient backdrop */}
      <View
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: MEDITATION_COLOR,
          opacity: 0.06,
        }}
        pointerEvents="none"
      />

      <SafeAreaView style={{ flex: 1 }} edges={['top', 'bottom']}>
        <View style={{ paddingHorizontal: 24, paddingTop: 4 }}>
          <Text style={{ fontFamily: font.bold, color: '#FFFFFF', fontSize: 11, letterSpacing: 3, opacity: 0.5 }}>
            MEDITATION
          </Text>
        </View>

        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <BreathRing phase={phase?.id ?? 'holdOut'} active={active} />
          <InnerHalo phase={phase?.id ?? 'holdOut'} active={active} />
          <YugoOrb size={ORB_SIZE} showGlow overrideColor={MEDITATION_COLOR} overridePulseDuration={6000} />
        </View>

        {/* Prompt */}
        <View style={{ minHeight: 56, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32 }}>
          {active ? (
            <Animated.Text
              style={[
                promptStyle,
                {
                  fontFamily: font.light,
                  color: '#FFFFFF99',
                  fontSize: 14,
                  fontStyle: 'italic',
                  textAlign: 'center',
                  letterSpacing: 0.5,
                  lineHeight: 22,
                },
              ]}
            >
              {PROMPTS[promptIdx]}
            </Animated.Text>
          ) : null}
        </View>

        {/* Toggle button */}
        <View style={{ alignItems: 'center', paddingBottom: 18 }}>
          <Pressable
            onPress={toggle}
            testID="zen-toggle"
            style={({ pressed }) => ({
              paddingHorizontal: 32,
              paddingVertical: 14,
              borderRadius: 100,
              borderWidth: 1,
              borderColor: `${MEDITATION_COLOR}88`,
              backgroundColor: pressed ? `${MEDITATION_COLOR}33` : `${MEDITATION_COLOR}18`,
            })}
          >
            <Text style={{ fontFamily: font.semibold, color: '#FFFFFF', fontSize: 12, letterSpacing: 3 }}>
              {active ? 'END SESSION' : 'BEGIN'}
            </Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </View>
  );
}
