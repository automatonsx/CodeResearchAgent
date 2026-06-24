// Bundled flat config Scout uses to lint arbitrary JS/TS as ground truth.
// Invoked with --no-config-lookup so the target repo's own config is ignored.
import js from "@eslint/js";

export default [
  js.configs.recommended,
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
