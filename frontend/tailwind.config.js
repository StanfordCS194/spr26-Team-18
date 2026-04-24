/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "text-muted": "var(--text-muted)",
        "text-invert": "var(--text-invert)",

        card: "var(--bg-card)",
        nav: "var(--bg-nav)",
        action: "var(--bg-action)",
        "action-dark": "var(--bg-action-dark)",
        chip: "var(--bg-chip)",
        "chip-alt": "var(--bg-chip-alt)",

        border: "var(--border-border)",
        "border-muted": "var(--border-muted)",
        "border-chip": "var(--border-chip)",

        "accent-gold": "var(--accent-gold)",
        "accent-gold-soft": "var(--accent-gold-soft)",

        "status-chaptered-bg": "var(--status-chaptered-bg)",
        "status-chaptered-text": "var(--status-chaptered-text)",
        "status-enrolled-bg": "var(--status-enrolled-bg)",
        "status-enrolled-text": "var(--status-enrolled-text)",
        "status-committee-bg": "var(--status-committee-bg)",
        "status-committee-text": "var(--status-committee-text)",
        "status-default-bg": "var(--status-default-bg)",
        "status-default-text": "var(--status-default-text)",
      },
      fontFamily: {
        sans: ['"Avenir Next"', '"Segoe UI"', "sans-serif"],
      },
      boxShadow: {
        card: "0 2px 12px rgba(16,33,51,0.07)",
        "card-hover": "0 4px 20px rgba(16,33,51,0.12)",
      },
      backgroundImage: {
        page: `radial-gradient(ellipse at 60% 0%, #f6f0e0 0%, transparent 60%),
               linear-gradient(160deg, #f6f3ea 0%, #eef2f7 100%)`,
      },
    },
  },
  plugins: [],
};
