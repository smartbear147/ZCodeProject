import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发期把 /api 和 /ws 代理到后端，前端可直接用相对路径
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
