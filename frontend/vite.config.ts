import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

const proxy = {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'vendor-element-plus',
              test: /node_modules[\\/](?:element-plus|@element-plus)[\\/]/,
              maxSize: 450000,
              includeDependenciesRecursively: false,
            },
            {
              name: 'vendor-vue',
              test: /node_modules[\\/](?:vue|@vue|vue-router|pinia)[\\/]/,
              maxSize: 450000,
              includeDependenciesRecursively: false,
            },
            {
              name: 'vendor',
              test: /node_modules[\\/]/,
              maxSize: 450000,
              includeDependenciesRecursively: false,
            },
          ],
        },
      },
    },
  },
  server: {
    port: 5173,
    // 允许内网穿透域名访问（localtunnel 每次 URL 会变，放行整个 .loca.lt 子域）
    allowedHosts: ['.loca.lt'],
    proxy,
  },
  preview: {
    proxy,
  },
})
