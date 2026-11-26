import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Fail instead of silently moving to another port: the backend's
    // CORS_ALLOWED_ORIGINS lists 5173, so a different port would be blocked
    // in a way that is confusing to debug.
    strictPort: true,
  },
});
