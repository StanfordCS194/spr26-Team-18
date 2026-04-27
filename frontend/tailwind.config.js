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
        card: "0 2px 18px rgba(140, 120, 180, 0.08)",
        "card-hover": "0 6px 28px rgba(140, 120, 180, 0.16)",
        sidebar: "1px 0 0 var(--border-border)",
      },
      backgroundImage: {
        page: `radial-gradient(ellipse at 80% -10%, #f7e6d6 0%, transparent 55%),
               radial-gradient(ellipse at 0% 100%, #e3dcef 0%, transparent 60%),
               linear-gradient(180deg, #fbf8f3 0%, #f4ecf5 100%)`,
        "sidebar-gradient": `linear-gradient(180deg, #efe9f6 0%, #e8e0f1 100%)`,
      },
    },
  },
  plugins: [],
};
