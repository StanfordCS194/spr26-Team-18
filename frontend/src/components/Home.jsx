import { useEffect, useRef, useState } from "react";
import { FileText, Building2, Gauge, ArrowRight, Sparkles } from "lucide-react";

const FEATURE_CARDS = [
  {
    id: "bills",
    Icon: FileText,
    title: "Bill Lookup",
    description:
      "Browse and search California environmental bills with plain-language summaries.",
    cta: "Browse bills",
  },
  {
    id: "company",
    Icon: Building2,
    title: "Company Match",
    description:
      "Describe your company and get matched to the bills most relevant to your operations.",
    cta: "Find your bills",
  },
  {
    id: "grade",
    Icon: Gauge,
    title: "10-K Grader",
    description:
      "Upload a 10-K and receive a letter grade across 5 regulatory exposure axes.",
    cta: "Grade your company",
  },
];

function gradeColor(grade) {
  if (!grade) return "text-text-muted";
  const g = grade[0];
  if (g === "A") return "text-status-chaptered-text";
  if (g === "B") return "text-accent-gold";
  if (g === "C") return "text-status-enrolled-text";
  return "text-status-committee-text";
}

function useCountUp(target, duration = 1200) {
  const [count, setCount] = useState(0);
  const rafRef = useRef(null);
  useEffect(() => {
    if (target === null) return;
    const start = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setCount(Math.round(target * eased));
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);
  return count;
}

export default function Home({ onTabChange }) {
  const [featured, setFeatured] = useState([]);
  const [billCount, setBillCount] = useState(null);

  useEffect(() => {
    fetch("/api/grade/featured")
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setFeatured(Array.isArray(d) ? d : []))
      .catch(() => {});

    fetch("/api/bills")
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setBillCount(Array.isArray(d) ? d.length : null))
      .catch(() => {});
  }, []);

  const animatedBillCount = useCountUp(billCount);

  const stats = [
    { label: "Bills tracked", value: billCount !== null ? animatedBillCount : "—" },
    { label: "Regulatory axes", value: "5" },
    { label: "Featured companies", value: featured.length || "—" },
    { label: "State", value: "CA" },
  ];

  return (
    <div className="space-y-10">
      {/* Header */}
      <div className="animate-slide-up" style={{ animationDelay: "0s" }}>
        <div className="mb-2 flex items-center gap-2 text-text-secondary">
          <Sparkles className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
          <span className="text-[12px] uppercase tracking-[0.18em]">
            California environmental compliance
          </span>
        </div>
        <h1 className="animate-shimmer-text text-[32px] font-bold tracking-tight">
          Welcome to Legi-Bill
        </h1>
        <p className="mt-2 max-w-[560px] text-[15px] leading-relaxed text-text-secondary">
          Track California environmental legislation, match bills to your business,
          and grade your regulatory exposure — all in one place.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map(({ label, value }, i) => (
          <div
            key={label}
            className="animate-slide-up rounded-2xl border border-border bg-card px-5 py-4 shadow-card"
            style={{ animationDelay: `${0.1 + i * 0.07}s` }}
          >
            <div className="text-[28px] font-bold tabular-nums text-text-primary">
              {value}
            </div>
            <div className="mt-1 text-[12px] text-text-muted">{label}</div>
          </div>
        ))}
      </div>

      {/* Feature cards */}
      <div>
        <h2
          className="animate-slide-up mb-4 text-[13px] uppercase tracking-[0.18em] text-text-muted"
          style={{ animationDelay: "0.38s" }}
        >
          Tools
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {FEATURE_CARDS.map(({ id, Icon, title, description, cta }, i) => (
            <button
              key={id}
              onClick={() => onTabChange(id)}
              className="animate-slide-up group flex flex-col items-start gap-3 rounded-3xl border border-border bg-card p-6 text-left shadow-card transition-all hover:-translate-y-1 hover:shadow-card-hover"
              style={{ animationDelay: `${0.44 + i * 0.09}s` }}
            >
              <div className="animate-float flex h-10 w-10 items-center justify-center rounded-xl bg-chip-alt">
                <Icon className="h-5 w-5 text-accent-gold" strokeWidth={2} />
              </div>
              <div>
                <div className="text-[16px] font-semibold text-text-primary">
                  {title}
                </div>
                <div className="mt-1 text-[13px] leading-relaxed text-text-secondary">
                  {description}
                </div>
              </div>
              <div className="mt-auto flex items-center gap-1.5 text-[13px] font-medium text-text-secondary transition-colors group-hover:text-text-primary">
                {cta}
                <ArrowRight
                  className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1"
                  strokeWidth={2.4}
                />
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Featured company grades */}
      {featured.length > 0 && (
        <div>
          <h2
            className="animate-slide-up mb-4 text-[13px] uppercase tracking-[0.18em] text-text-muted"
            style={{ animationDelay: "0.7s" }}
          >
            Featured grades
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {featured.map((c, i) => (
              <button
                key={c.ticker}
                onClick={() => onTabChange("grade")}
                className="animate-slide-up group flex flex-col items-start gap-2 rounded-2xl border border-border bg-card px-4 py-5 text-left shadow-card transition-all hover:-translate-y-1 hover:shadow-card-hover"
                style={{ animationDelay: `${0.76 + i * 0.07}s` }}
              >
                <div className="flex w-full items-center justify-between">
                  <span className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
                    {c.ticker}
                  </span>
                  <span className={`text-[22px] font-bold ${gradeColor(c.grade)}`}>
                    {c.grade}
                  </span>
                </div>
                <span className="text-[14px] font-semibold leading-snug text-text-primary">
                  {c.name}
                </span>
                <span className="text-[12px] text-text-muted transition-colors group-hover:text-text-secondary">
                  View grade →
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
