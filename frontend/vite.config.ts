import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import fs from 'node:fs'
import path from 'node:path'

// https://vitejs.dev/config/
const portsPath = path.resolve(__dirname, '../config/ports.json')
if (!fs.existsSync(portsPath)) {
  throw new Error('Missing config/ports.json')
}
const ports = JSON.parse(fs.readFileSync(portsPath, 'utf-8'))
const frontendPort = Number(ports.frontend_port || 8080)
const backendPort = Number(ports.backend_port || 8081)

const argPortIndex = process.argv.findIndex((arg) => arg === '--port')
if (argPortIndex !== -1) {
  const cliPort = Number(process.argv[argPortIndex + 1])
  if (cliPort && cliPort !== frontendPort) {
    throw new Error(`Frontend port must be ${frontendPort} (config/ports.json)`)
  }
}

export default defineConfig({
  plugins: [vue()],
  server: {
    port: frontendPort,
    host: ports.frontend_host || '0.0.0.0',
    strictPort: true,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true
      },
      '/static': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true
      }
    }
  },
  preview: {
    port: frontendPort,
    host: ports.frontend_host || '0.0.0.0'
  }
})
