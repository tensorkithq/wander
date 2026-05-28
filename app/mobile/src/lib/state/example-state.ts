// This is an example of a Zustand store, use this for async storage.
// DO NOTE USE THIS FILE, create new ones in the state folder.

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import AsyncStorage from "@react-native-async-storage/async-storage";

interface RootStore {
  someData: number;
  addSomeData: () => void;
}

// Make sure to persist the store using the persist middleware.
const useRootStore = create<RootStore>()(
  persist(
    (set, get) => ({
      someData: 0,
      addSomeData: () => set({ someData: get().someData + 1 }),
    }),
    {
      name: "root-storage",
      storage: createJSONStorage(() => AsyncStorage),
    }
  )
);

export default useRootStore;
