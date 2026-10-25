import { globalIgnores } from 'eslint/config';
import pluginVue from 'eslint-plugin-vue';
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript';
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting';

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,mts,tsx,vue}'],
  },

  globalIgnores(['**/dist/**', '**/dist-ssr/**', '**/coverage/**', 'env.d.ts']),

  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,

  {
    name: 'app/relaxed-rules',
    rules: {
      // views are named after their route and never used as custom elements; renaming them is churn
      'vue/multi-word-component-names': 'off',
      // every <script> is TypeScript, so vue-tsc checks it (and the template)
      'vue/block-lang': ['error', { script: { lang: 'ts' } }],
      // WebSocket payloads aren't typed yet: a warning rather than an error until they are
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },

  skipFormatting,
);
