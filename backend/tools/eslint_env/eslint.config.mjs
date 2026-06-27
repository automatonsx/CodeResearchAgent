// Bundled flat config Scout uses to lint arbitrary JS/TS/React/Vue as ground truth.
// Invoked with --no-config-lookup so the target repo's own config is ignored.
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import react from "eslint-plugin-react";
import vue from "eslint-plugin-vue";

export default [
  // Base JavaScript recommended rules.
  js.configs.recommended,

  // TypeScript — parses .ts/.tsx (non-type-checked, so no tsconfig needed).
  ...tseslint.configs.recommended,

  // Vue — sets up vue-eslint-parser for .vue single-file components.
  ...vue.configs["flat/recommended"],

  // React rules for JSX/TSX (covers React + Next.js).
  {
    files: ["**/*.{jsx,tsx}"],
    ...react.configs.flat.recommended,
    settings: { react: { version: "detect" } },
  },

  // Plain .jsx needs JSX parsing enabled on the default parser.
  {
    files: ["**/*.jsx"],
    languageOptions: { parserOptions: { ecmaFeatures: { jsx: true } } },
  },

  // Global tweaks applied to everything.
  {
    languageOptions: { ecmaVersion: "latest", sourceType: "module" },
    rules: {
      // no-undef produces false positives without per-repo env/globals — disable it.
      "no-undef": "off",
      "no-unused-vars": "warn",
      // Security-relevant rules kept as errors:
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
    },
  },
];
