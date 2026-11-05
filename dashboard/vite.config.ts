import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api/': { target: process.env.AEGIS_COLLECTOR_URL || 'http://127.0.0.1:8000' },
    },
  },
  test: { include: ['tests/**/*.test.ts'], environment: 'node' },
})
