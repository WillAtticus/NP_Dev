/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'np-blue':  '#2868D7',
        'np-green': '#169C82',
        'np-warn':  '#B7791F',
        'np-red':   '#C04458',
        'np-dark':  '#F2F7FD',
        'np-panel': '#FFFFFF',
        'np-border':'#DCE7F3',
      },
    },
  },
  plugins: [],
}
