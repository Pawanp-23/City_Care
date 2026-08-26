/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#092233',
        brand: '#0f766e',
        aqua: '#14b8a6',
        mist: '#e8f5f3',
      },
      boxShadow: {
        float: '0 20px 50px rgba(3, 38, 53, .14)',
        lift: '0 28px 66px rgba(3, 38, 53, .22)',
      },
    },
  },
  plugins: [],
}
