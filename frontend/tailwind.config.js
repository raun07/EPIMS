/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // EPIMS design tokens — steel-blue professional ERP palette
        // Signature: deep navy sidebar + amber accent for actionable states
        brand: {
          50:  "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          500: "#6366f1",  // primary action indigo
          600: "#4f46e5",
          700: "#4338ca",
          900: "#1e1b4b",  // sidebar navy
        },
        amber: {
          400: "#fbbf24",
          500: "#f59e0b",  // status: pending, warning
          600: "#d97706",
        },
        surface: {
          DEFAULT: "#f8f9fb",
          card: "#ffffff",
          border: "#e4e7ec",
          hover: "#f3f4f8",
        },
        ink: {
          DEFAULT: "#111827",
          muted: "#6b7280",
          subtle: "#9ca3af",
        },
        status: {
          draft:     "#94a3b8",
          pending:   "#f59e0b",
          approved:  "#10b981",
          rejected:  "#ef4444",
          released:  "#6366f1",
          received:  "#0ea5e9",
          matched:   "#10b981",
          disputed:  "#f43f5e",
          paid:      "#059669",
        },
      },
      fontFamily: {
        // Inter for body + data density; JetBrains for numbers/codes
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
        md: "8px",
        lg: "12px",
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(0 0 0 / 0.08), 0 1px 2px -1px rgb(0 0 0 / 0.04)",
        "card-hover": "0 4px 12px 0 rgb(0 0 0 / 0.10)",
        sidebar: "1px 0 0 0 #e4e7ec",
      },
    },
  },
  plugins: [],
};
