import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8000'
  const simulatorTarget = env.VITE_SIMULATOR_TARGET || 'http://127.0.0.1:8001'

  return {
    plugins: [
      react(),
      tailwindcss(),
    ],
    server: {
      port: 5173,
      proxy: {
        '/health': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/ready': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/v1': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/admin': {
          target: simulatorTarget,
          changeOrigin: true,
        },
        '/simulator': {
          target: simulatorTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/simulator/, ''),
        },
      },
    },
  }
})
