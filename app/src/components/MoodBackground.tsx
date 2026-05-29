import React, { useEffect, useRef } from 'react';
import { View, Dimensions } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  Easing,
} from 'react-native-reanimated';
import { useMoodColor } from '@/lib/state/yugo-store';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

const PARTICLE_COUNT = 12;

interface Particle {
  id: number;
  x: number;
  startY: number;
  size: number;
  duration: number;
  delay: number;
}

function generateParticles(): Particle[] {
  return Array.from({ length: PARTICLE_COUNT }, (_, i) => ({
    id: i,
    x: Math.random() * SCREEN_WIDTH,
    startY: SCREEN_HEIGHT + 20,
    size: 2 + Math.random() * 4,
    duration: 8000 + Math.random() * 6000,
    delay: Math.random() * 8000,
  }));
}

const particles = generateParticles();

function FloatingParticle({ particle, color }: { particle: Particle; color: string }) {
  const translateY = useSharedValue(0);
  const opacity = useSharedValue(0);

  useEffect(() => {
    const totalTravel = SCREEN_HEIGHT + 40;
    translateY.value = 0;
    opacity.value = 0;

    setTimeout(() => {
      translateY.value = withRepeat(
        withTiming(-totalTravel, {
          duration: particle.duration,
          easing: Easing.linear,
        }),
        -1,
        false
      );
      opacity.value = withRepeat(
        withTiming(0.25, { duration: particle.duration / 4, easing: Easing.inOut(Easing.quad) }),
        -1,
        true
      );
    }, particle.delay);
  }, [particle.delay, particle.duration, translateY, opacity]);

  const animStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: translateY.value }],
    opacity: opacity.value,
  }));

  return (
    <Animated.View
      style={[
        animStyle,
        {
          position: 'absolute',
          left: particle.x,
          bottom: 0,
          width: particle.size,
          height: particle.size,
          borderRadius: particle.size / 2,
          backgroundColor: color,
        },
      ]}
    />
  );
}

interface MoodBackgroundProps {
  children: React.ReactNode;
}

export default function MoodBackground({ children }: MoodBackgroundProps) {
  const { color, pulseDuration } = useMoodColor();
  const glowOpacity = useSharedValue(0.06);

  // Use a ref to track previous pulse duration so we only restart when it changes
  const prevPulse = useRef(pulseDuration);

  useEffect(() => {
    prevPulse.current = pulseDuration;
    glowOpacity.value = withRepeat(
      withTiming(0.14, {
        duration: pulseDuration,
        easing: Easing.inOut(Easing.sin),
      }),
      -1,
      true
    );
  }, [pulseDuration, glowOpacity]);

  const glowStyle = useAnimatedStyle(() => ({
    opacity: glowOpacity.value,
  }));

  return (
    <View style={{ flex: 1, backgroundColor: '#070709' }}>
      {/* Radial glow overlay at top */}
      <Animated.View
        style={[
          glowStyle,
          {
            position: 'absolute',
            top: -SCREEN_HEIGHT * 0.3,
            left: SCREEN_WIDTH / 2 - SCREEN_HEIGHT * 0.6,
            width: SCREEN_HEIGHT * 1.2,
            height: SCREEN_HEIGHT * 1.2,
            borderRadius: SCREEN_HEIGHT * 0.6,
            backgroundColor: color,
          },
        ]}
        pointerEvents="none"
      />

      {/* Floating particles */}
      {particles.map((p) => (
        <FloatingParticle key={p.id} particle={p} color={color} />
      ))}

      {children}
    </View>
  );
}
