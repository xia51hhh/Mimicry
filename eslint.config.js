import js from "@eslint/js";
import tseslint from "typescript-eslint";
import pluginVue from "eslint-plugin-vue";

export default [
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs["flat/recommended"],
  {
    files: ["src/**/*.{vue,ts,js}"],
    languageOptions: {
      globals: {
        clearTimeout: "readonly",
        console: "readonly",
        document: "readonly",
        DragEvent: "readonly",
        HTMLElement: "readonly",
        localStorage: "readonly",
        MouseEvent: "readonly",
        MutationObserver: "readonly",
        navigator: "readonly",
        Node: "readonly",
        self: "readonly",
        setTimeout: "readonly",
        URL: "readonly",
        window: "readonly",
        Worker: "readonly",
      },
      parserOptions: {
        parser: tseslint.parser,
      },
    },
    rules: {
      "vue/multi-word-component-names": "off",
      "vue/attributes-order": "off",
      "vue/first-attribute-linebreak": "off",
      "vue/html-closing-bracket-newline": "off",
      "vue/html-indent": "off",
      "vue/html-quotes": "off",
      "vue/html-self-closing": "off",
      "vue/max-attributes-per-line": "off",
      "vue/singleline-html-element-content-newline": "off",
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_" },
      ],
    },
  },
  {
    ignores: ["dist/", "node_modules/", "src-tauri/"],
  },
];
