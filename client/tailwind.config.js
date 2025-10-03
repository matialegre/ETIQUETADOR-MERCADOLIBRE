/****** Tailwind Config ******/
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          500: '#22c55e'
        }
      }
    }
  },
  plugins: []
}
