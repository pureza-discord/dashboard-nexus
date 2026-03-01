import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const DEV_PROXY_TARGET = process.env.VITE_DEV_API_PROXY || 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': DEV_PROXY_TARGET,
    },
  },
})
