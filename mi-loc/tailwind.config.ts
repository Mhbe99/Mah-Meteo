import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0a0a0a",
        anthracite: "#1c1c1e",
        graphite: "#2b2b2d",
        cream: "#f6f3ec",
        gold: {
          DEFAULT: "#b8964f",
          light: "#d4b876",
          dark: "#8f7238",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "serif"],
        sans: ["var(--font-sans)", "sans-serif"],
      },
      maxWidth: {
        content: "1200px",
      },
      boxShadow: {
        premium: "0 20px 60px -20px rgba(0,0,0,0.35)",
        card: "0 4px 24px -8px rgba(0,0,0,0.12)",
      },
      borderRadius: {
        xl2: "1.25rem",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(24px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards",
      },
    },
  },
  plugins: [],
};

export default config;
