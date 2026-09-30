import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The IPv4 loopback explicitly: left alone, Vite may listen on ::1 only.
    host: '127.0.0.1',
    strictPort: true,
    // The API runs in the Python process on 8000 during development. Proxying
    // makes page and API one origin, as they are when the server serves both.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    // Straight into the directory `app/main.py` serves, so the packaged build
    // needs no copy step.
    outDir: '../app/static',
    emptyOutDir: true,
  },
})
