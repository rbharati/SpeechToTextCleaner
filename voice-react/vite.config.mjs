import { readFileSync } from 'node:fs';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const useHttps = process.env.VITE_USE_HTTPS === '1';

export default defineConfig({
  plugins: [react()],
  server: {
    https: useHttps
      ? {
          cert: readFileSync('certs/lan-cert.pem'),
          key: readFileSync('certs/lan-key.pem'),
        }
      : undefined,
    proxy: {
      '/correct': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
      },
      '/compare': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
