/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        fondo: "var(--fondo)", tinta: "var(--tinta)", suave: "var(--suave)", linea: "var(--linea)",
        panel: "var(--panel)", pista: "var(--pista)", bola: "var(--bola)", aviso: "var(--aviso)", mal: "var(--mal)",
      },
      fontFamily: { titulo: ["Space Grotesk", "Segoe UI", "system-ui", "sans-serif"], texto: ["Inter", "Segoe UI", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
