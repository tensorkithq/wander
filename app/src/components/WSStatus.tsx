import React from 'react';
import { Pressable, View } from 'react-native';
import { useRouter } from 'expo-router';
import useYugoStore from '@/lib/state/yugo-store';

export default function WSStatus() {
  const router = useRouter();
  const wsConnected = useYugoStore((s) => s.wsConnected);
  const bridgeUrl = useYugoStore((s) => s.bridgeUrl);

  const color = wsConnected ? '#22C55E' : bridgeUrl ? '#F59E0B' : '#EF4444';

  return (
    <Pressable
      onPress={() => router.push('/settings' as never)}
      testID="ws-status-indicator"
      style={{ padding: 6 }}
    >
      <View
        style={{
          width: 10,
          height: 10,
          borderRadius: 5,
          backgroundColor: color,
          shadowColor: color,
          shadowOpacity: 0.8,
          shadowRadius: 4,
          shadowOffset: { width: 0, height: 0 },
          elevation: 4,
        }}
      />
    </Pressable>
  );
}
