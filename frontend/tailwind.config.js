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
        "accent-green": "var(--accent-green)",
        "accent-blue": "var(--accent-blue)",

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
        sans: ['"Space Grotesk"', '"Segoe UI"', "sans-serif"],
      },
      boxShadow: {
        card: "0 2px 12px rgba(0, 82, 255, 0.08)",
        "card-hover": "0 8px 32px rgba(0, 82, 255, 0.18)",
        sidebar: "2px 0 0 var(--border-border)",
        glow: "0 0 32px rgba(0, 82, 255, 0.25)",
        "glow-green": "0 0 24px rgba(0, 200, 100, 0.3)",
      },
      backgroundImage: {
        page: `radial-gradient(ellipse at 90% -5%, #dbeafe 0%, transparent 45%),
               radial-gradient(ellipse at -5% 95%, #d1fae5 0%, transparent 45%),
               linear-gradient(180deg, #f8faff 0%, #f0f7ff 100%)`,
        "sidebar-gradient": `linear-gradient(160deg, #0d1b3e 0%, #0f2554 100%)`,
        "hero-glow": `radial-gradient(ellipse at 50% 0%, rgba(0,82,255,0.12) 0%, transparent 70%)`,
        "blue-gradient": `linear-gradient(135deg, #0052FF 0%, #0066FF 50%, #0080FF 100%)`,
        "green-gradient": `linear-gradient(135deg, #00C853 0%, #00E676 100%)`,
      },
      borderRadius: {
        "4xl": "2rem",
      },
      animation: {
        "pulse-slow": "pulse 3s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
