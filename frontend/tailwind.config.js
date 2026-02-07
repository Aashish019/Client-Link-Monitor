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
        // Grafana-inspired dark theme
        bg: '#111217',
        surface: '#181b1f',
        surfaceHighlight: '#22252b',
        border: '#2c3235',
        primary: '#3274d9',
        success: '#299c46',
        warning: '#d44a3a',
        text: '#c7d0d9',
        textMuted: '#6e7687'
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
