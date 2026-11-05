import { preview } from 'vite'
import { fileURLToPath } from 'node:url'
const root = fileURLToPath(new URL('../', import.meta.url))
const target = 'http://127.0.0.1:9099'
const server = await preview({ configFile: false, root, preview: {
  host: '127.0.0.1', port: 5173, strictPort: true,
  proxy: {
    '/prod-api': { target, changeOrigin: true, rewrite: p => p.replace(/^\/prod-api/, '') },
    '/dev-api': { target, changeOrigin: true, rewrite: p => p.replace(/^\/dev-api/, '') }
  }
}})
server.printUrls()
