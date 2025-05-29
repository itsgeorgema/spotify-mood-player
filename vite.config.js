// vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  envDir: 'src', // Load .env from src/
  server: {
    host: '127.0.0.1', // Explicitly tell Vite to use 127.0.0.1
    port: 5173,        // Your desired frontend port (matches your FRONTEND_URL)
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5001', // Your backend
        changeOrigin: true, // Good for proxies
        secure: false,      // If your backend is HTTP
      }
    }
  }
})
