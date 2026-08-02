import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0a0a1a',
        surface: {
          DEFAULT: '#13132b',
          '2': '#1a1a3e',
        },
        border: '#2a2a5a',
        text: {
          DEFAULT: '#e0e0f0',
          '2': '#9090b0',
          '3': '#5e5e88',
        },
        primary: {
          DEFAULT: '#6c5ce7',
          '2': '#a78bfa',
        },
        success: '#22c55e',
        warn: '#f59e0b',
        danger: '#ef4444',
      },
      borderRadius: {
        card: '14px',
        btn: '10px',
      },
    },
  },
  plugins: [],
} satisfies Config
