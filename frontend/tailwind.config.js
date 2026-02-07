/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surfaceHighlight: 'var(--surface-highlight)',
        border: 'var(--border)',
        primary: 'var(--accent-color)',
        success: 'var(--success-color)',
        warning: 'var(--warning-color)',
        text: 'var(--text-primary)',
        textMuted: 'var(--text-secondary)'
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
