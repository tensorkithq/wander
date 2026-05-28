import React from 'react';
import { View, Pressable, Text } from 'react-native';
import { Tabs, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  Easing,
} from 'react-native-reanimated';
import { useEffect } from 'react';
import { useMoodColor } from '@/lib/state/yugo-store';
import { font } from '@/lib/typography';
import {
  PortholeGlyph,
  ControlGlyph,
  TalkGlyph,
  WandGlyph,
  ZenGlyph,
  SettingsGlyph,
} from '@/components/Glyph';

const INACTIVE_COLOR = '#3D3D4F';

type GlyphComponent = (props: { size?: number; color?: string; active?: boolean }) => React.JSX.Element;

const TABS: { name: string; Glyph: GlyphComponent; label: string }[] = [
  { name: 'index', Glyph: PortholeGlyph, label: 'Porthole' },
  { name: 'controller', Glyph: ControlGlyph, label: 'Control' },
  { name: 'talk', Glyph: TalkGlyph, label: 'Voice' },
  { name: 'wand', Glyph: WandGlyph, label: 'Wand' },
  { name: 'zen', Glyph: ZenGlyph, label: 'Zen' },
];

function TabIndicator({ color }: { color: string }) {
  const pulse = useSharedValue(0.5);

  useEffect(() => {
    pulse.value = withRepeat(
      withTiming(1, { duration: 1400, easing: Easing.inOut(Easing.sin) }),
      -1,
      true
    );
  }, [pulse]);

  const style = useAnimatedStyle(() => ({
    opacity: pulse.value,
  }));

  return (
    <Animated.View
      style={[
        style,
        {
          width: 14,
          height: 1.5,
          borderRadius: 1,
          marginTop: 4,
          backgroundColor: color,
        },
      ]}
    />
  );
}

function YugoTabBar({ state, navigation }: { state: any; navigation: any }) {
  const insets = useSafeAreaInsets();
  const { color: moodColor } = useMoodColor();
  const router = useRouter();

  return (
    <View
      style={{
        backgroundColor: '#08080C',
        borderTopWidth: 0.5,
        borderTopColor: '#181826',
        paddingBottom: insets.bottom,
        paddingTop: 10,
        paddingHorizontal: 6,
      }}
    >
      {/* Subtle glow line at top of tab bar */}
      <View style={{
        position: 'absolute',
        top: 0,
        left: '15%',
        right: '15%',
        height: 1,
        backgroundColor: moodColor,
        opacity: 0.18,
      }} />

      <View style={{ flexDirection: 'row', alignItems: 'flex-start' }}>
        {state.routes.map((route: { key: string; name: string }, index: number) => {
          const isFocused = state.index === index;
          const tab = TABS.find((t) => t.name === route.name);
          if (!tab) return null;
          const Glyph = tab.Glyph;
          const tint = isFocused ? moodColor : INACTIVE_COLOR;

          return (
            <Pressable
              key={route.key}
              onPress={() => {
                const event = navigation.emit({
                  type: 'tabPress',
                  target: route.key,
                  canPreventDefault: true,
                });
                if (!isFocused && !event.defaultPrevented) {
                  navigation.navigate(route.name);
                }
              }}
              style={{ flex: 1, alignItems: 'center', paddingVertical: 4 }}
              testID={`tab-${tab.label.toLowerCase()}`}
            >
              <View style={{ alignItems: 'center' }}>
                <Glyph size={24} color={tint} active={isFocused} />
                {isFocused ? <TabIndicator color={moodColor} /> : (
                  <View style={{ height: 1.5, marginTop: 4 }} />
                )}
              </View>
              <Text
                style={{
                  fontFamily: isFocused ? font.semibold : font.regular,
                  color: tint,
                  fontSize: 9,
                  letterSpacing: 1.5,
                  marginTop: 4,
                  textTransform: 'uppercase',
                  opacity: isFocused ? 1 : 0.55,
                }}
              >
                {tab.label}
              </Text>
            </Pressable>
          );
        })}

        {/* Settings */}
        <Pressable
          onPress={() => router.push('/settings' as never)}
          style={{ width: 50, alignItems: 'center', paddingVertical: 4 }}
          testID="tab-settings"
        >
          <SettingsGlyph size={22} color={INACTIVE_COLOR} />
          <View style={{ height: 1.5, marginTop: 4 }} />
          <Text
            style={{
              fontFamily: font.regular,
              color: INACTIVE_COLOR,
              fontSize: 9,
              letterSpacing: 1.5,
              marginTop: 4,
              opacity: 0.55,
            }}
          >
            CFG
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

export default function TabLayout() {
  return (
    <Tabs
      tabBar={(props) => <YugoTabBar state={props.state} navigation={props.navigation} />}
      screenOptions={{ headerShown: false }}
    >
      <Tabs.Screen name="index" />
      <Tabs.Screen name="controller" />
      <Tabs.Screen name="talk" />
      <Tabs.Screen name="wand" />
      <Tabs.Screen name="zen" />
    </Tabs>
  );
}
