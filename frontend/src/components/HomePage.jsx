import { useEffect, useRef, useState } from "react";
import {
  ArrowRight, Scale, Sparkles, Gauge, MessageCircle,
  Upload, CheckCircle2, DollarSign, FileText, GitBranch, ShieldAlert,
} from "lucide-react";

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(n) {
  return new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", maximumFractionDigits: 0,
  }).format(n);
}

function useCountUp(target, duration = 1800, delay = 0) {
  const [count, setCount] = useState(0);
  const rafRef = useRef(null);
  useEffect(() => {
    if (target === null) return;
    const timeout = setTimeout(() => {
      const start = performance.now();
      const tick = (now) => {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        setCount(Math.round(target * eased));
        if (t < 1) rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    }, delay);
    return () => { clearTimeout(timeout); cancelAnimationFrame(rafRef.current); };
  }, [target, duration, delay]);
  return count;
}

// ── static data ───────────────────────────────────────────────────────────────

const STEPS = [
  {
    n: "01",
    Icon: GitBranch,
    title: "Paste a GitHub URL",
    body: "Link any public repository. No account, no install, no code execution — we read only.",
    tags: ["Public repos", "No OAuth", "Static analysis only"],
  },
  {
    n: "02",
    Icon: ShieldAlert,
    title: "Tell us your industry",
    body: "We load the right scanners for your domain — HIPAA for health, PCI for fintech, OSS license rules for dev tools.",
    tags: ["Health", "Fintech", "SaaS", "AI/ML", "EdTech"],
  },
  {
    n: "03",
    Icon: CheckCircle2,
    title: "Get evidence-backed findings",
    body: "Every finding points to a specific file and line. Severity and confidence are always listed separately.",
    tags: ["File + line evidence", "Severity", "Confidence"],
  },
];

const FEATURES = [
  {
    id: "scanner",
    Icon: ShieldAlert,
    title: "Repo Risk Scanner",
    body: "Paste a GitHub URL, pick your industry, and get evidence-backed findings across licenses, privacy, supply chain, and more.",
    cta: "Scan a repository",
    accent: "text-rose-500",
    bg: "bg-rose-50",
  },
  {
    id: "startup",
    Icon: Sparkles,
    title: "Startup Health Grade",
    body: "Grade your back office in 30 seconds. Engineering, legal, financial, compliance, and product — scored against 50+ rules.",
    cta: "Grade my startup",
    accent: "text-status-enrolled-text",
    bg: "bg-status-enrolled-bg",
  },
  {
    id: "legal",
    Icon: Scale,
    title: "Legal Cost Savings",
    body: "Line-item breakdown of what a compliance attorney would invoice. Rates matched to your industry and state. Sources cited.",
    cta: "Calculate savings",
    accent: "text-accent-gold",
    bg: "bg-accent-gold/20",
  },
  {
    id: "financial",
    Icon: Gauge,
    title: "Financial Compliance",
    body: "Runway forecasting, transaction categorization from Mercury/Stripe/Gusto, R&D tax credit estimation, and filing tracker.",
    cta: "View financials",
    accent: "text-status-committee-text",
    bg: "bg-status-committee-bg",
  },
];

// ── component ─────────────────────────────────────────────────────────────────

export default function HomePage({ onTabChange }) {
  const savings  = useCountUp(47_000, 2000, 300);
  const bills    = useCountUp(4_821,  1600, 500);
  const hours    = useCountUp(350,    1400, 400);

  return (
    <div className="space-y-20 pb-4">

      {/* ── Hero ── */}
      <section className="space-y-8 pt-4">
        <div className="animate-slide-up flex items-center gap-2 text-text-secondary" style={{ animationDelay: "0s" }}>
          <ShieldAlert className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
          <span className="text-[12px] uppercase tracking-[0.18em]">Startup Risk Intelligence · Static Analysis + LLMs</span>
        </div>

        <div className="animate-slide-up max-w-[680px] space-y-4" style={{ animationDelay: "0.06s" }}>
          <h1 className="animate-shimmer-text text-[44px] font-bold leading-[1.1] tracking-tight">
            Find compliance debt before it gets expensive.
          </h1>
          <p className="text-[17px] leading-relaxed text-text-secondary">
            Paste a public GitHub URL. We compare what your code actually does against
            industry-specific risk patterns — licenses, privacy, supply chain, and more.
          </p>
        </div>

        {/* Scanner hero card */}
        <div
          className="animate-slide-up inline-flex flex-col rounded-3xl border border-accent-gold/40 bg-accent-gold/10 px-8 py-6 shadow-card"
          style={{ animationDelay: "0.12s" }}
        >
          <div className="text-[11px] uppercase tracking-wider text-text-muted">
            What we scan for
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {["License risk", "Privacy gaps", "Supply chain", "PII in logs", "Missing security files", "AI data use", "HIPAA triggers", "OSS obligations"].map((tag) => (
              <span key={tag} className="rounded-full border border-accent-gold/30 bg-white/50 px-3 py-1 text-[12px] text-text-secondary">
                {tag}
              </span>
            ))}
          </div>
          <div className="mt-4 flex items-center gap-4 text-[12px] text-text-secondary">
            <span><span className="font-semibold text-text-primary">4</span> scanners running</span>
            <span className="text-text-muted">·</span>
            <span><span className="font-semibold text-text-primary">8</span> industry verticals</span>
            <span className="text-text-muted">·</span>
            <span>Evidence-backed findings</span>
          </div>
        </div>

        {/* CTAs */}
        <div className="animate-slide-up flex items-center gap-3" style={{ animationDelay: "0.18s" }}>
          <button
            onClick={() => onTabChange("scanner")}
            className="flex items-center gap-2 rounded-xl bg-action-dark px-6 py-2.5 text-[14px] font-semibold text-text-invert transition-opacity hover:opacity-90"
          >
            <GitBranch className="h-4 w-4" strokeWidth={2} />
            Scan a repository
            <ArrowRight className="h-4 w-4" strokeWidth={2.4} />
          </button>
          <button
            onClick={() => onTabChange("startup")}
            className="flex items-center gap-2 rounded-xl border border-border bg-card px-6 py-2.5 text-[14px] font-medium text-text-primary shadow-card transition-all hover:shadow-card-hover"
          >
            <Sparkles className="h-4 w-4 text-accent-gold" strokeWidth={2} />
            Startup health grade
          </button>
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="space-y-6">
        <div className="animate-slide-up flex items-center gap-4" style={{ animationDelay: "0.1s" }}>
          <h2 className="text-[13px] uppercase tracking-[0.18em] text-text-muted">How it works</h2>
          <div className="h-px flex-1 bg-border" />
        </div>

        <div className="grid grid-cols-3 gap-5">
          {STEPS.map((step, i) => (
            <div
              key={step.n}
              className="animate-slide-up relative flex flex-col rounded-3xl border border-border bg-card p-6 shadow-card"
              style={{ animationDelay: `${0.12 + i * 0.08}s` }}
            >
              {/* Connector arrow */}
              {i < STEPS.length - 1 && (
                <div className="absolute -right-[14px] top-1/2 z-10 -translate-y-1/2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full border border-border bg-card shadow-card">
                    <ArrowRight className="h-3.5 w-3.5 text-text-muted" strokeWidth={2.4} />
                  </div>
                </div>
              )}

              <div className="mb-5 flex items-center gap-3">
                <span className="text-[11px] font-bold uppercase tracking-[0.2em] text-accent-gold">
                  {step.n}
                </span>
                <div className="h-px flex-1 bg-border" />
              </div>

              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-chip-alt">
                <step.Icon className="h-5 w-5 text-accent-gold" strokeWidth={2} />
              </div>

              <div className="text-[15px] font-semibold text-text-primary">{step.title}</div>
              <div className="mt-2 text-[13px] leading-relaxed text-text-secondary">{step.body}</div>

              <div className="mt-4 flex flex-wrap gap-1.5">
                {step.tags.map((t) => (
                  <span
                    key={t}
                    className="rounded-full border border-border-chip bg-chip px-2.5 py-0.5 text-[11px] text-text-muted"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Feature cards ── */}
      <section className="space-y-6">
        <div className="animate-slide-up flex items-center gap-4" style={{ animationDelay: "0.1s" }}>
          <h2 className="text-[13px] uppercase tracking-[0.18em] text-text-muted">What's inside</h2>
          <div className="h-px flex-1 bg-border" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          {FEATURES.map((f, i) => (
            <button
              key={f.id}
              onClick={() => onTabChange(f.id)}
              className="animate-slide-up group flex flex-col items-start gap-4 rounded-3xl border border-border bg-card p-6 text-left shadow-card transition-all hover:-translate-y-1 hover:shadow-card-hover"
              style={{ animationDelay: `${0.12 + i * 0.07}s` }}
            >
              <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${f.bg}`}>
                <f.Icon className={`h-5 w-5 ${f.accent}`} strokeWidth={2} />
              </div>
              <div className="flex-1">
                <div className="text-[15px] font-semibold text-text-primary">{f.title}</div>
                <div className="mt-1.5 text-[13px] leading-relaxed text-text-secondary">{f.body}</div>
              </div>
              <div className="flex items-center gap-1.5 text-[13px] font-medium text-text-secondary transition-colors group-hover:text-text-primary">
                {f.cta}
                <ArrowRight
                  className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1"
                  strokeWidth={2.4}
                />
              </div>
            </button>
          ))}
        </div>
      </section>

      {/* ── Bottom stat strip ── */}
      <section
        className="animate-slide-up grid grid-cols-3 gap-4"
        style={{ animationDelay: "0.2s" }}
      >
        {[
          { value: "4+",       label: "scanners per repo" },
          { value: "8",        label: "industry verticals covered" },
          { value: "Evidence", label: "backed — file + line number" },
        ].map(({ value, label }) => (
          <div
            key={label}
            className="rounded-2xl border border-border bg-card px-5 py-4 shadow-card text-center"
          >
            <div className="text-[24px] font-bold tabular-nums text-text-primary">{value}</div>
            <div className="mt-0.5 text-[12px] text-text-muted">{label}</div>
          </div>
        ))}
      </section>

    </div>
  );
}
