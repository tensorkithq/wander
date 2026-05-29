import { DarkTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { useFonts } from 'expo-font';
import { useEffect } from 'react';
import { View } from 'react-native';
import useYugoStore from '@/lib/state/yugo-store';
import { fontMap } from '@/lib/typography';

export const unstable_settings = {
  initialRouteName: '(tabs)',
};

SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient();

function WSInitializer() {
  const bridgeUrl = useYugoStore((s) => s.bridgeUrl);
  const connectWS = useYugoStore((s) => s.connectWS);

  useEffect(() => {
    if (bridgeUrl) {
      connectWS();
    }
  }, [bridgeUrl, connectWS]);

  return null;
}

function RootLayoutNav() {
  return (
    <ThemeProvider value={DarkTheme}>
      <WSInitializer />
      <Stack>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="modal" options={{ presentation: 'modal' }} />
        <Stack.Screen
          name="settings"
          options={{
            presentation: 'modal',
            title: 'Settings',
            headerStyle: { backgroundColor: '#0A0A0F' },
            headerTintColor: '#FFFFFF',
            headerTitleStyle: { color: '#FFFFFF' },
          }}
        />
      </Stack>
    </ThemeProvider>
  );
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts(fontMap);

  useEffect(() => {
    if (fontsLoaded) {
      SplashScreen.hideAsync();
    }
  }, [fontsLoaded]);

  if (!fontsLoaded) {
    return <View style={{ flex: 1, backgroundColor: '#070709' }} />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <GestureHandlerRootView style={{ flex: 1, backgroundColor: '#070709' }}>
        <StatusBar style="light" />
        <RootLayoutNav />
      </GestureHandlerRootView>
    </QueryClientProvider>
  );
}
