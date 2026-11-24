import type { Config } from 'tailwindcss'

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#060a12',
          900: '#0a101d',
          850: '#0f172a',
          800: '#131d33',
          700: '#1b2a47',
          600: '#253a60',
        },
        charcoal: {
          950: '#0b0f17',
          900: '#111827',
          850: '#161f33',
          800: '#1f293d',
          700: '#2e3d57',
          600: '#435473',
          500: '#627494',
        },
        cyan: {
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
        },
        medical: {
          green: '#10b981',
          yellow: '#f59e0b',
          red: '#f43f5e',
          blue: '#0ea5e9',
          purple: '#8b5cf6',
          ecg: '#22d3ee',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'monospace'],
      },
      boxShadow: {
        'glow-cyan': '0 0 20px -5px rgba(14, 165, 233, 0.25)',
        'glow-emerald': '0 0 20px -5px rgba(16, 185, 129, 0.25)',
        'glow-rose': '0 0 20px -5px rgba(244, 63, 94, 0.25)',
        'card-dark': '0 4px 20px -2px rgba(0, 0, 0, 0.35)',
        'card-light': '0 2px 12px -2px rgba(15, 23, 42, 0.08)',
      }
    },
  },
  plugins: [],
} satisfies Config
