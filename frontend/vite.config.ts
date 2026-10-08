import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // 后端默认 API_PORT=8721（src/config.py），extension 同指向
        target: 'http://localhost:8721',
        changeOrigin: true,
      },
    },
  },
})
