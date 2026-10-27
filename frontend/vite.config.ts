import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Must match BACKEND_PORT in .env (backend default is 8000).
const backendTarget = process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/health': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/ready': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
})
