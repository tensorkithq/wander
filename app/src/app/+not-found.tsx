import { Link, Stack } from 'expo-router';
import { Text, View } from 'react-native';

export default function NotFoundScreen() {
  return (
    <>
      <Stack.Screen options={{ title: 'Oops!' }} />
      <View testID="not-found-screen" className="flex-1 items-center justify-center bg-white p-5 dark:bg-black">
        <Text className="text-xl font-bold text-black dark:text-white">
          This screen doesn't exist.
        </Text>

        <Link href="/" testID="go-home-link" className="mt-4 py-4">
          <Text className="text-sm text-blue-500">Go to home screen!</Text>
        </Link>
      </View>
    </>
  );
}
