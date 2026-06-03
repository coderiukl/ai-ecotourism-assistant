import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const proxyTarget = process.env.VITE_BACKEND_URL || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    allowedHosts: [
      'localhost',
      '127.0.0.1',
      '.ngrok-free.app',
      '563a-2405-4802-9190-1a70-514f-67e9-93b4-c096.ngrok-free.app',
    ],
    proxy: {
      '/api': proxyTarget,
      '/images': proxyTarget,
    },
  },
});
