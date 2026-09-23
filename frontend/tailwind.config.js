/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        industrial: {
          950: '#0a0d14',
          900: '#0f1422',
          850: '#141b2d',
          800: '#1c2438',
          700: '#2a354f',
          600: '#3c4b6e',
          500: '#5a6e9a',
          400: '#8ba2cc',
          300: '#b8c9e6',
          200: '#dae4f5',
          100: '#f0f4fa',
        },
        risk: {
          low: '#10b981',      // Emerald / Green
          medium: '#f59e0b',   // Amber / Yellow
          high: '#f97316',     // Orange
          critical: '#ef4444', // Red
        },
        integrity: {
          verified: '#10b981',
          review: '#f59e0b',
          failed: '#ef4444',
          compromised: '#dc2626',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Courier New', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}

