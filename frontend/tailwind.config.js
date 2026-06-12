/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bgDark: "#05080f",
        bgPanel: "#0c101a",
        bgCard: "#111827",
        borderAccent: "#e63946",
        borderSubtle: "#1e293b",
        textWhite: "#f1f5f9",
        textMuted: "#64748b",
        textGold: "#f8fafc",
        accentRed: "#e63946",
        accentTeal: "#2dd4bf",
      }
    },
  },
  plugins: [],
}
