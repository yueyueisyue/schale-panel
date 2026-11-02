import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 前端开发服务器 7880，API 打到本地 BFF 7870
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: '0.0.0.0',      // 局域网可访问
    port: 7880,
    strictPort: true,
    watch: {
      // 截图/日志目录不参与热更新监听，避免外部进程写文件时 EBUSY 把 dev server 拖崩
      ignored: ['**/_shots/**', '**/_ref/**', '**/*.log', '**/*.txt'],
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:7870',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    assetsInlineLimit: 4096,
    chunkSizeWarningLimit: 1500,
  },
})
