import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
  },
  build: {
    rollupOptions: {
      output: {
        // Libraries change rarely, so browsers can keep them between releases.
        manualChunks: (id) => {
          if (/node_modules\/(@mui|@emotion)\//.test(id)) return 'mui';
          return id.includes('node_modules') ? 'vendor' : undefined;
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    restoreMocks: true,
    testTimeout: 20000,
  },
});
