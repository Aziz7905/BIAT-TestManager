/** Brand-aligned Tailwind theme tokens for the BIAT Test Manager redesign. */
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "rgb(var(--color-primary) / <alpha-value>)",
        "primary-light": "rgb(var(--color-primary-light) / <alpha-value>)",
        surface: "rgb(var(--color-surface) / <alpha-value>)",
        bg: "rgb(var(--color-bg) / <alpha-value>)",
        warm: "rgb(var(--color-warm) / <alpha-value>)",
        text: "rgb(var(--color-text) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        border: "rgb(var(--color-border) / <alpha-value>)",
        "tag-fill": "#EBF5FF",
        "status-unverified-bg": "#F5EDE8",
        "status-unverified-text": "rgb(var(--color-warm) / <alpha-value>)",
        "status-verified-bg": "#E8F5E9",
        "status-verified-text": "#2E7D32",
        "status-automated-bg": "rgb(var(--color-primary) / <alpha-value>)",
        "status-automated-text": "#FFFFFF",
      },
      fontFamily: {
        sans: ["\"Plus Jakarta Sans\"", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        panel: "0 10px 30px rgba(30, 58, 95, 0.08)",
      },
    },
  },
} satisfies Config;
