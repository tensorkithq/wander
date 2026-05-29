// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require("eslint/config");
const expoConfig = require("eslint-config-expo/flat");
const pluginQuery = require("@tanstack/eslint-plugin-query");

module.exports = defineConfig([
  expoConfig,
  {
    ignores: [
      "**/dist/**",
      "**/backend/generated/**",
      "**/backend/prisma/**",
      "backend/generated/**",
      "backend/prisma/**",
      "backend/node_modules/**",
      "backend/src/generated/**",
      "**/node_modules/**",
      "node_modules/**",
      "**/.expo/**",
      ".expo/**",
      "**/.expo-shared/**",
      ".expo-shared/**",
      "**/patches/**",
      "patches/**",
      "bun.lock",
      "eslint.config.js",
      "nativewind-env.d.ts",
      "rootStore.example.ts",
    ],
    settings: {
      "import/resolver": {
        typescript: {
          alwaysTryTypes: true,
          project: "./tsconfig.json",
        },
      },
    },
    plugins: {
      react: require("eslint-plugin-react"),
      "react-hooks": require("eslint-plugin-react-hooks"),
    },
    rules: {
      // Formatting nits the sorter doesn't fix
      "comma-spacing": ["warn", { before: false, after: true }],
      // React recommended rules (only those not already covered by expo config)
      "react/jsx-no-undef": "error",
      "react/jsx-uses-react": "off", // React 17+ JSX transform
      "react/react-in-jsx-scope": "off",
      "react/jsx-no-leaked-render": [
        "error",
        { validStrategies: ["ternary", "coerce"] },
      ],

      // Enforce React Hooks rules
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",

      "react/no-unescaped-entities": "off",
    },
  },
  ...pluginQuery.configs["flat/recommended"],
]);
