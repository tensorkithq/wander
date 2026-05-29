import React, { useEffect } from 'react';
import { View } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  Easing,
  interpolate,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';
import useYugoStore from '@/lib/state/yugo-store';
import { useMoodColor } from '@/lib/state/yugo-store';

interface YugoOrbProps {
  size?: number;
  showGlow?: boolean;
  interactive?: boolean;
  overrideColor?: string;
  overridePulseDuration?: number;
}

export default function YugoOrb({
  size = 300,
  showGlow = true,
  interactive: _interactive = false,
  overrideColor,
  overridePulseDuration,
}: YugoOrbProps) {
  const { color, pulseDuration } = useMoodColor();
  const isSpeaking = useYugoStore((s) => s.isSpeaking);
  const fieldIntensity = useYugoStore((s) => s.fieldIntensity);

  const activeColor = overrideColor ?? color;
  const activePulse = overridePulseDuration ?? pulseDuration;

  // Breathing scale
  const breathScale = useSharedValue(0.95);
  // Glow ring opacity
  const glowOpacity = useSharedValue(0.3);
  // Speaking ripple
  const rippleScale = useSharedValue(1);
  const rippleOpacity = useSharedValue(0);
  // Shimmer for fieldIntensity
  const shimmerOpacity = useSharedValue(0);

  useEffect(() => {
    breathScale.value = withRepeat(
      withTiming(1.05, {
        duration: activePulse,
        easing: Easing.inOut(Easing.sin),
      }),
      -1,
      true
    );
    glowOpacity.value = withRepeat(
      withTiming(0.6, {
        duration: activePulse,
        easing: Easing.inOut(Easing.sin),
      }),
      -1,
      true
    );
  }, [activePulse, breathScale, glowOpacity]);

  useEffect(() => {
    if (isSpeaking) {
      rippleScale.value = 1;
      rippleOpacity.value = 0.7;
      rippleScale.value = withRepeat(
        withTiming(1.6, { duration: 800, easing: Easing.out(Easing.quad) }),
        -1,
        false
      );
      rippleOpacity.value = withRepeat(
        withTiming(0, { duration: 800, easing: Easing.out(Easing.quad) }),
        -1,
        false
      );
    } else {
      rippleScale.value = withTiming(1, { duration: 300 });
      rippleOpacity.value = withTiming(0, { duration: 300 });
    }
  }, [isSpeaking, rippleScale, rippleOpacity]);

  useEffect(() => {
    const intensity = fieldIntensity;
    if (intensity > 0.5) {
      shimmerOpacity.value = withRepeat(
        withTiming(intensity * 0.5, { duration: 150, easing: Easing.inOut(Easing.quad) }),
        -1,
        true
      );
    } else {
      shimmerOpacity.value = withTiming(0, { duration: 300 });
    }
  }, [fieldIntensity, shimmerOpacity]);

  const breathStyle = useAnimatedStyle(() => ({
    transform: [{ scale: breathScale.value }],
  }));

  const glowStyle = useAnimatedStyle(() => ({
    opacity: interpolate(glowOpacity.value, [0.3, 0.6], [0.15, 0.45]),
  }));

  const outerGlowStyle = useAnimatedStyle(() => ({
    opacity: interpolate(glowOpacity.value, [0.3, 0.6], [0.08, 0.25]),
  }));

  const rippleStyle = useAnimatedStyle(() => ({
    transform: [{ scale: rippleScale.value }],
    opacity: rippleOpacity.value,
  }));

  const shimmerStyle = useAnimatedStyle(() => ({
    opacity: shimmerOpacity.value,
  }));

  const orbRadius = size / 2;
  const glowRadius = size * 0.7;
  const outerGlowRadius = size * 0.95;

  return (
    <View
      style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}
      testID="yugo-orb"
    >
      {/* Outer diffuse glow */}
      {showGlow ? (
        <Animated.View
          style={[
            outerGlowStyle,
            {
              position: 'absolute',
              width: outerGlowRadius * 2,
              height: outerGlowRadius * 2,
              borderRadius: outerGlowRadius,
              backgroundColor: activeColor,
            },
          ]}
        />
      ) : null}

      {/* Inner glow ring */}
      {showGlow ? (
        <Animated.View
          style={[
            glowStyle,
            {
              position: 'absolute',
              width: glowRadius * 2,
              height: glowRadius * 2,
              borderRadius: glowRadius,
              backgroundColor: activeColor,
            },
          ]}
        />
      ) : null}

      {/* Speaking ripple */}
      <Animated.View
        style={[
          rippleStyle,
          {
            position: 'absolute',
            width: size,
            height: size,
            borderRadius: orbRadius,
            borderWidth: 2,
            borderColor: activeColor,
          },
        ]}
      />

      {/* Core orb with breathing */}
      <Animated.View style={[breathStyle, { width: size, height: size, borderRadius: orbRadius, overflow: 'hidden' }]}>
        <LinearGradient
          colors={[activeColor, `${activeColor}88`, '#0A0A0F']}
          style={{ flex: 1, borderRadius: orbRadius }}
          start={{ x: 0.3, y: 0.2 }}
          end={{ x: 0.9, y: 0.9 }}
        />

        {/* Shimmer overlay for field intensity */}
        <Animated.View
          style={[
            shimmerStyle,
            {
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              borderRadius: orbRadius,
              backgroundColor: '#FFFFFF',
            },
          ]}
        />
      </Animated.View>
    </View>
  );
}
