/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Read-only Python API: `uv run lucidnews-api` (override with LUCIDNEWS_API)
    // The browser's Host header is kept (changeOrigin off): sign-in checks that the Origin of a POST is the
    // host it was sent to, and Google must come back to the address the browser used (localhost:5173).
    proxy: { '/api': { target: process.env.LUCIDNEWS_API ?? 'http://127.0.0.1:8765', changeOrigin: false } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    // First render of a screen loads its lazy chunk.
    testTimeout: 15_000,
  },
})
