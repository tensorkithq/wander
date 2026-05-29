import { StatusBar } from 'expo-status-bar';
import { Platform, Text, View } from 'react-native';


export default function ModalScreen() {
  return (
    <View testID="modal-screen" className="flex-1 items-center justify-center bg-white dark:bg-black">
      <Text className="text-xl font-bold text-black dark:text-white">Modal</Text>
      <View className="my-8 h-px w-4/5 bg-gray-200 dark:bg-white/10" />

      {/* Use a light status bar on iOS to account for the black space above the modal */}
      <StatusBar style={Platform.OS === 'ios' ? 'light' : 'auto'} />
    </View>
  );
}
