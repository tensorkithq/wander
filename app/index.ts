import "react-native-get-random-values";
import "react-native-reanimated";
import { LogBox } from "react-native";
import "./global.css";
import { installNetworkDebug } from "./src/lib/net-debug";

// Patch global fetch/WebSocket before expo-router/entry boots the app, so the
// first network call is already instrumented.
installNetworkDebug();

// eslint-disable-next-line import/first -- must load after installNetworkDebug()
import "expo-router/entry";
LogBox.ignoreLogs(["Expo AV has been deprecated", "Disconnected from Metro"]);
