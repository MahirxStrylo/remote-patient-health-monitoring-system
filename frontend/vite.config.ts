import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('plotly.js') || id.includes('react-plotly.js')) {
            return 'plotly-vendor';
          }
          if (id.includes('lucide-react')) {
            return 'lucide-vendor';
          }
          if (id.includes('date-fns')) {
            return 'date-fns-vendor';
          }
          if (id.includes('react') || id.includes('react-dom') || id.includes('react-router-dom') || id.includes('@tanstack')) {
            return 'react-vendor';
          }
        }
      }
    }
  }
})
