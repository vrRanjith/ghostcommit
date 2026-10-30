import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

// Inside docker compose the API is reachable as http://api:8000; outside, on localhost.
const apiUrl = process.env.API_URL ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    // Docker Desktop on Windows doesn't forward file-change events into the container,
    // so poll for changes there (WATCH_POLLING is set in docker-compose.yml).
    watch: process.env.WATCH_POLLING ? { usePolling: true, interval: 300 } : undefined,
    // The browser only ever talks to :5173; Vite forwards API calls, so cookies
    // stay same-origin exactly like in production.
    proxy: {
      '/api': apiUrl,
      '/auth': apiUrl,
    },
  },
})
