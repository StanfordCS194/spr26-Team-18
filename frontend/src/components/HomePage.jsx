import { useEffect, useRef, useState } from "react";
import {
  ArrowRight, Scale, Sparkles, Gauge, MessageCircle,
  Upload, DollarSign, ShieldCheck, TrendingUp, Zap,
  CheckCircle2, Star, Database, RefreshCw,
} from "lucide-react";

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

/* ── SVG Illustrations ─────────────────────────────────────────────────────── */

function IllustrationDoc() {
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="72" height="72" rx="20" fill="#EEF3FF" />
      <rect x="18" y="14" width="28" height="36" rx="4" fill="#0052FF" fillOpacity="0.15" stroke="#0052FF" strokeWidth="1.5" />
      <rect x="22" y="20" width="20" height="2.5" rx="1.25" fill="#0052FF" fillOpacity="0.6" />
      <rect x="22" y="26" width="16" height="2.5" rx="1.25" fill="#0052FF" fillOpacity="0.4" />
      <rect x="22" y="32" width="18" height="2.5" rx="1.25" fill="#0052FF" fillOpacity="0.4" />
      <rect x="22" y="38" width="12" height="2.5" rx="1.25" fill="#0052FF" fillOpacity="0.3" />
      <circle cx="52" cy="50" r="10" fill="#00C853" />
      <path d="M47.5 50l3 3 5-6" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IllustrationGrade() {
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="72" height="72" rx="20" fill="#CCFCE7" />
      <circle cx="36" cy="34" r="16" fill="#00C853" fillOpacity="0.15" stroke="#00C853" strokeWidth="2" />
      <text x="36" y="40" textAnchor="middle" fontSize="20" fontWeight="700" fill="#00874a" fontFamily="Space Grotesk, sans-serif">A</text>
      <path d="M20 54 Q36 46 52 54" stroke="#00C853" strokeWidth="1.5" strokeDasharray="3 3" fill="none" />
      <circle cx="20" cy="54" r="3" fill="#00C853" />
      <circle cx="36" cy="48" r="3" fill="#00C853" />
      <circle cx="52" cy="54" r="3" fill="#00C853" />
    </svg>
  );
}

function IllustrationMoney() {
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="72" height="72" rx="20" fill="#FFEDD5" />
      <rect x="14" y="26" width="44" height="28" rx="6" fill="#FF6B00" fillOpacity="0.15" stroke="#FF6B00" strokeWidth="1.5" />
      <circle cx="36" cy="40" r="8" fill="#FF6B00" fillOpacity="0.2" stroke="#FF6B00" strokeWidth="1.5" />
      <text x="36" y="45" textAnchor="middle" fontSize="14" fontWeight="700" fill="#FF6B00" fontFamily="Space Grotesk, sans-serif">$</text>
      <path d="M36 18 L36 24" stroke="#FF6B00" strokeWidth="2" strokeLinecap="round" />
      <path d="M30 20 L36 18 L42 20" stroke="#FF6B00" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function HeroIllustration() {
  return (
    <div className="relative flex-shrink-0 w-[340px] h-[280px]">
      {/* Main document card */}
      <div className="absolute top-0 right-0 w-[200px] rounded-2xl border-2 border-[#0052ff]/20 bg-white p-4 shadow-card animate-float">
        <div className="flex items-center gap-2 mb-3">
          <div className="h-2 w-2 rounded-full bg-[#FF6B00]" />
          <div className="h-1.5 flex-1 rounded bg-[#d4e0ff]" />
        </div>
        <div className="space-y-1.5">
          <div className="h-2 w-full rounded bg-[#d4e0ff]" />
          <div className="h-2 w-4/5 rounded bg-[#d4e0ff]" />
          <div className="h-2 w-3/4 rounded bg-[#d4e0ff]" />
        </div>
        <div className="mt-4 flex items-center justify-between">
          <span className="text-[11px] font-bold text-[#0052ff]">Grade: A</span>
          <div className="rounded-full bg-[#ccfce7] px-2 py-0.5 text-[10px] font-bold text-[#00874a]">+92%</div>
        </div>
      </div>

      {/* Savings badge */}
      <div className="absolute bottom-8 left-0 rounded-2xl border-2 border-[#FF6B00]/30 bg-white px-4 py-3 shadow-card">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-[#7a90b8]">Legal fees saved</div>
        <div className="text-[22px] font-bold text-[#FF6B00]">$47,000</div>
      </div>

      {/* Floating check badges */}
      <div className="absolute top-16 left-4 flex items-center gap-1.5 rounded-full border border-[#ccfce7] bg-white px-3 py-1.5 shadow-card">
        <CheckCircle2 className="h-3.5 w-3.5 text-[#00c853]" strokeWidth={2.5} />
        <span className="text-[11px] font-semibold text-[#050a14]">Compliant</span>
      </div>

      <div className="absolute bottom-[72px] right-4 flex items-center gap-1.5 rounded-full border border-[#dbeafe] bg-white px-3 py-1.5 shadow-card">
        <Zap className="h-3.5 w-3.5 text-[#0052ff]" strokeWidth={2.5} />
        <span className="text-[11px] font-semibold text-[#050a14]">30 sec</span>
      </div>

      {/* Star rating */}
      <div className="absolute top-[100px] right-[-8px] flex gap-0.5">
        {[1,2,3,4,5].map(i => (
          <Star key={i} className="h-3 w-3 fill-[#FF6B00] text-[#FF6B00]" />
        ))}
      </div>
    </div>
  );
}

/* ── Static data ───────────────────────────────────────────────────────────── */

const STEPS = [
  {
    n: "01",
    Illustration: IllustrationDoc,
    title: "Upload your docs",
    body: "Drop in your GitHub repo, PRD, and finance spreadsheet. No account needed — runs in 30 seconds.",
    tags: ["GitHub URL", "PRD / Markdown", "CSV / Excel"],
    color: "#0052FF",
    bgColor: "#EEF3FF",
  },
  {
    n: "02",
    Illustration: IllustrationGrade,
    title: "Get graded instantly",
    body: "50+ deterministic rules across 5 axes: Engineering, Legal, Financial, Compliance, and Product.",
    tags: ["Letter grade", "5 axes", "50+ rules"],
    color: "#00C853",
    bgColor: "#CCFCE7",
  },
  {
    n: "03",
    Illustration: IllustrationMoney,
    title: "Save real money",
    body: "See the exact legal fees a compliance attorney would charge — and your top 5 actions to raise your grade.",
    tags: ["Legal savings", "Action plan", "State-adjusted rates"],
    color: "#FF6B00",
    bgColor: "#FFEDD5",
  },
];

const FEATURES = [
  {
    id: "startup",
    Icon: Sparkles,
    title: "Startup Health Grade",
    body: "Grade your back office in 30 seconds. Engineering, legal, financial, compliance, and product — scored against 50+ rules.",
    cta: "Grade my startup",
    iconColor: "#1d4ed8",
    iconBg: "#dbeafe",
    borderColor: "#bfdbfe",
  },
  {
    id: "legal",
    Icon: Scale,
    title: "Legal Cost Savings",
    body: "Line-item breakdown of what a compliance attorney would invoice. Rates matched to your industry and state.",
    cta: "Calculate savings",
    iconColor: "#FF6B00",
    iconBg: "#ffedd5",
    borderColor: "#fed7aa",
  },
  {
    id: "recs",
    Icon: TrendingUp,
    title: "Active Recommendations",
    body: "Your 5 highest-leverage compliance fixes this week, ranked by impact and tied to your actual grade.",
    cta: "See recommendations",
    iconColor: "#00874a",
    iconBg: "#ccfce7",
    borderColor: "#86efac",
  },
  {
    id: "financial",
    Icon: Gauge,
    title: "Financial Compliance",
    body: "Runway forecasting, transaction categorization from Mercury/Stripe/Gusto, R&D tax credit estimation.",
    cta: "View financials",
    iconColor: "#7c3aed",
    iconBg: "#ede9fe",
    borderColor: "#c4b5fd",
  },
];

/* ── Component ─────────────────────────────────────────────────────────────── */

export default function HomePage({ onTabChange }) {
  const savings = useCountUp(47_000, 2000, 300);
  const bills   = useCountUp(4_821,  1600, 500);
  const hours   = useCountUp(350,    1400, 400);
  const [legalStatus, setLegalStatus] = useState(null);

  useEffect(() => {
    let alive = true;
    fetch("/api/legal-intelligence/status")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => { if (alive) setLegalStatus(data); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  return (
    <div className="space-y-20 pb-4">

      {/* ── Hero ── */}
      <section className="pt-4">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">

          {/* Left copy */}
          <div className="max-w-[560px] space-y-6">
            <div className="animate-slide-up flex items-center gap-2" style={{ animationDelay: "0s" }}>
              <div className="flex items-center gap-1.5 rounded-full bg-[#0052ff]/10 px-3 py-1 text-[12px] font-semibold text-[#0052ff]">
                <Zap className="h-3.5 w-3.5" strokeWidth={2.5} />
                <span>AI-powered · Founder Copilot</span>
              </div>
            </div>

            <div className="animate-slide-up space-y-3" style={{ animationDelay: "0.06s" }}>
              <h1 className="animate-shimmer-text text-[52px] font-bold leading-[1.05] tracking-tight">
                Your startup's<br />compliance HQ.
              </h1>
              <p className="text-[18px] font-medium leading-relaxed text-text-secondary">
                Grade your legal, financial, and product health in{" "}
                <span className="font-bold text-text-primary">30 seconds.</span>{" "}
                Know exactly what a lawyer would charge — and skip that bill entirely.
              </p>
            </div>

            {/* Savings card */}
            <div
              className="animate-slide-up w-fit rounded-2xl border-2 border-[#FF6B00]/30 bg-gradient-to-br from-[#fff7ed] to-white p-5 shadow-card"
              style={{ animationDelay: "0.12s" }}
            >
              <div className="text-[11px] font-bold uppercase tracking-widest text-[#FF6B00]/70">
                Average legal fees automated
              </div>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-[52px] font-bold tabular-nums leading-none text-[#FF6B00]">
                  {fmt(savings)}
                </span>
                <span className="text-[15px] font-medium text-text-muted">/ startup</span>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-text-secondary">
                <span className="font-bold text-text-primary">{bills.toLocaleString()}</span>
                <span className="text-text-muted">CA bills scanned</span>
                <span className="text-text-muted">·</span>
                <span className="font-bold text-text-primary">{hours}+</span>
                <span className="text-text-muted">attorney hours automated</span>
              </div>
            </div>

            {/* CTAs */}
            <div className="animate-slide-up flex flex-wrap items-center gap-3" style={{ animationDelay: "0.18s" }}>
              <button
                onClick={() => onTabChange("startup")}
                className="flex items-center gap-2 rounded-xl bg-[#0052ff] px-6 py-3 text-[14px] font-bold text-white shadow-glow transition-all hover:bg-[#0041cc] hover:shadow-glow active:scale-95"
              >
                Grade my startup
                <ArrowRight className="h-4 w-4" strokeWidth={2.5} />
              </button>
              <button
                onClick={() => onTabChange("legal")}
                className="flex items-center gap-2 rounded-xl border-2 border-[#FF6B00]/30 bg-white px-6 py-3 text-[14px] font-bold text-[#FF6B00] transition-all hover:border-[#FF6B00]/60 hover:shadow-card active:scale-95"
              >
                <Scale className="h-4 w-4" strokeWidth={2.2} />
                Calculate savings
              </button>
            </div>
          </div>

          {/* Hero illustration */}
          <div className="animate-slide-up hidden lg:flex" style={{ animationDelay: "0.1s" }}>
            <HeroIllustration />
          </div>
        </div>
      </section>

      {/* ── Trust strip ── */}
      <div
        className="animate-slide-up -mx-2 flex items-center gap-6 overflow-hidden rounded-2xl border-2 border-[#d4e0ff] bg-white px-6 py-4"
        style={{ animationDelay: "0.22s" }}
      >
        {[
          { icon: ShieldCheck, label: "50+ compliance rules", color: "#0052ff" },
          { icon: Zap,         label: "Under 30 seconds",     color: "#00C853" },
          { icon: DollarSign,  label: "No law firm needed",   color: "#FF6B00" },
          { icon: Star,        label: "State-adjusted rates", color: "#7c3aed" },
        ].map(({ icon: Icon, label, color }) => (
          <div key={label} className="flex items-center gap-2 text-[13px] font-semibold text-text-secondary">
            <Icon className="h-4 w-4 shrink-0" style={{ color }} strokeWidth={2.4} />
            {label}
          </div>
        ))}
      </div>

      <button
        onClick={() => onTabChange("legal")}
        className="animate-slide-up flex w-full items-center justify-between gap-5 rounded-2xl border-2 border-[#FF6B00]/20 bg-white px-6 py-4 text-left shadow-card transition-all hover:-translate-y-0.5 hover:border-[#FF6B00]/40 hover:shadow-card-hover"
        style={{ animationDelay: "0.24s" }}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#fff7ed]">
            <Database className="h-5 w-5 text-[#FF6B00]" strokeWidth={2.4} />
          </div>
          <div>
            <div className="text-[14px] font-bold text-text-primary">Legal guidance freshness</div>
            <div className="mt-0.5 text-[12px] text-text-secondary">
              {legalStatus?.last_checked
                ? `Last refreshed ${new Date(legalStatus.last_checked).toLocaleString()}`
                : "No legal source refresh has run yet"}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-[22px] font-bold tabular-nums text-[#FF6B00]">
              {legalStatus?.enabled_rule_count ?? 0}
            </div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">enabled rules</div>
          </div>
          <RefreshCw className="h-4 w-4 text-text-muted" strokeWidth={2.3} />
        </div>
      </button>

      {/* ── How it works ── */}
      <section className="space-y-6">
        <div className="animate-slide-up" style={{ animationDelay: "0.1s" }}>
          <div className="mb-1 text-[12px] font-bold uppercase tracking-[0.2em] text-[#0052ff]">
            How it works
          </div>
          <h2 className="text-[28px] font-bold text-text-primary">
            Three steps to compliance clarity
          </h2>
        </div>

        <div className="grid grid-cols-3 gap-5">
          {STEPS.map((step, i) => (
            <div
              key={step.n}
              className="animate-slide-up relative flex flex-col rounded-2xl border-2 bg-white p-6 shadow-card transition-all hover:-translate-y-1 hover:shadow-card-hover"
              style={{
                animationDelay: `${0.12 + i * 0.08}s`,
                borderColor: step.color + "33",
              }}
            >
              {i < STEPS.length - 1 && (
                <div className="absolute -right-[16px] top-1/2 z-10 -translate-y-1/2">
                  <div
                    className="flex h-8 w-8 items-center justify-center rounded-full border-2 bg-white shadow-card"
                    style={{ borderColor: step.color + "40" }}
                  >
                    <ArrowRight className="h-4 w-4" style={{ color: step.color }} strokeWidth={2.5} />
                  </div>
                </div>
              )}

              <div className="mb-4">
                <step.Illustration />
              </div>

              <div
                className="mb-1 text-[11px] font-bold uppercase tracking-[0.2em]"
                style={{ color: step.color }}
              >
                Step {step.n}
              </div>
              <div className="text-[16px] font-bold text-text-primary">{step.title}</div>
              <div className="mt-2 text-[13px] leading-relaxed text-text-secondary">{step.body}</div>

              <div className="mt-4 flex flex-wrap gap-1.5">
                {step.tags.map((t) => (
                  <span
                    key={t}
                    className="rounded-full border px-2.5 py-0.5 text-[11px] font-semibold"
                    style={{
                      borderColor: step.color + "40",
                      backgroundColor: step.bgColor,
                      color: step.color,
                    }}
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
        <div className="animate-slide-up" style={{ animationDelay: "0.1s" }}>
          <div className="mb-1 text-[12px] font-bold uppercase tracking-[0.2em] text-[#0052ff]">
            Features
          </div>
          <h2 className="text-[28px] font-bold text-text-primary">
            Everything your compliance team needs
          </h2>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {FEATURES.map((f, i) => (
            <button
              key={f.id}
              onClick={() => onTabChange(f.id)}
              className="animate-slide-up group flex flex-col items-start gap-4 rounded-2xl border-2 bg-white p-6 text-left shadow-card transition-all hover:-translate-y-1 hover:shadow-card-hover"
              style={{
                animationDelay: `${0.12 + i * 0.07}s`,
                borderColor: f.borderColor,
              }}
            >
              <div
                className="flex h-12 w-12 items-center justify-center rounded-xl"
                style={{ backgroundColor: f.iconBg }}
              >
                <f.Icon className="h-6 w-6" style={{ color: f.iconColor }} strokeWidth={2.2} />
              </div>
              <div className="flex-1">
                <div className="text-[16px] font-bold text-text-primary">{f.title}</div>
                <div className="mt-1.5 text-[13px] leading-relaxed text-text-secondary">{f.body}</div>
              </div>
              <div
                className="flex items-center gap-1.5 text-[13px] font-bold transition-all group-hover:gap-2.5"
                style={{ color: f.iconColor }}
              >
                {f.cta}
                <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" strokeWidth={2.5} />
              </div>
            </button>
          ))}
        </div>
      </section>

      {/* ── Bold stat strip ── */}
      <section
        className="animate-slide-up grid grid-cols-3 gap-4"
        style={{ animationDelay: "0.2s" }}
      >
        {[
          { value: fmt(47_000), label: "avg legal fees automated", color: "#FF6B00", bg: "#fff7ed" },
          { value: "4,821",    label: "CA bills tracked",          color: "#0052ff", bg: "#eef3ff" },
          { value: "5 axes",   label: "compliance dimensions",     color: "#00874a", bg: "#f0fdf4" },
        ].map(({ value, label, color, bg }) => (
          <div
            key={label}
            className="rounded-2xl border-2 p-5 text-center shadow-card"
            style={{ borderColor: color + "33", backgroundColor: bg }}
          >
            <div className="text-[28px] font-bold tabular-nums" style={{ color }}>{value}</div>
            <div className="mt-1 text-[12px] font-semibold text-text-secondary">{label}</div>
          </div>
        ))}
      </section>

    </div>
  );
}
