import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: process.env.WTS_WEB_PORT ? parseInt(process.env.WTS_WEB_PORT) : 9000,
    proxy: {
      '/api': {
        target: 'http://localhost:' + (process.env.WTS_API_PORT || '7503'),
        changeOrigin: true,
      },
    },
  },
})
