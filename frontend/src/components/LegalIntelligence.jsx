import { useRef, useState } from "react";
import {
  Scale, ChevronDown, ChevronUp, CheckCircle2,
  Clock, DollarSign, ShieldAlert, ShieldCheck, Minus,
} from "lucide-react";

// ── helpers ──────────────────────────────────────────────────────────────────

function fmt(n) {
  return new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", maximumFractionDigits: 0,
  }).format(n);
}

function fmtRange(lo, hi) {
  return `${fmt(lo)}–${fmt(hi)}`;
}

// ── static data ───────────────────────────────────────────────────────────────

const US_STATES = [
  ["", "Select state…"],
  ["AL","Alabama"],["AK","Alaska"],["AZ","Arizona"],["AR","Arkansas"],
  ["CA","California"],["CO","Colorado"],["CT","Connecticut"],["DE","Delaware"],
  ["DC","Washington D.C."],["FL","Florida"],["GA","Georgia"],["HI","Hawaii"],
  ["ID","Idaho"],["IL","Illinois"],["IN","Indiana"],["IA","Iowa"],
  ["KS","Kansas"],["KY","Kentucky"],["LA","Louisiana"],["ME","Maine"],
  ["MD","Maryland"],["MA","Massachusetts"],["MI","Michigan"],["MN","Minnesota"],
  ["MS","Mississippi"],["MO","Missouri"],["MT","Montana"],["NE","Nebraska"],
  ["NV","Nevada"],["NH","New Hampshire"],["NJ","New Jersey"],["NM","New Mexico"],
  ["NY","New York"],["NC","North Carolina"],["ND","North Dakota"],["OH","Ohio"],
  ["OK","Oklahoma"],["OR","Oregon"],["PA","Pennsylvania"],["RI","Rhode Island"],
  ["SC","South Carolina"],["SD","South Dakota"],["TN","Tennessee"],["TX","Texas"],
  ["UT","Utah"],["VT","Vermont"],["VA","Virginia"],["WA","Washington"],
  ["WV","West Virginia"],["WI","Wisconsin"],["WY","Wyoming"],
];

const INDUSTRY_DISPLAY = {
  environmental: "Environmental",
  finance:       "Finance",
  healthcare:    "Healthcare",
  tech:          "Technology",
  manufacturing: "Manufacturing",
  retail:        "Retail / CPG",
  real_estate:   "Real Estate",
  agriculture:   "Agriculture",
  general:       "General",
};

const CATEGORY_ACCENT = {
  "Research & Discovery":     "text-status-enrolled-text",
  "Analysis & Documentation": "text-status-committee-text",
  "Strategic Planning":       "text-accent-gold",
  "Client Communication":     "text-status-chaptered-text",
};

const CATEGORY_BADGE_BG = {
  "Research & Discovery":     "bg-status-enrolled-bg text-status-enrolled-text",
  "Analysis & Documentation": "bg-status-committee-bg text-status-committee-text",
  "Strategic Planning":       "bg-accent-gold/20 text-accent-gold",
  "Client Communication":     "bg-status-chaptered-bg text-status-chaptered-text",
};

// ── sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, delay = "0s" }) {
  return (
    <div
      className="animate-slide-up rounded-2xl border border-border bg-card px-5 py-4 shadow-card"
      style={{ animationDelay: delay }}
    >
      <div className="mb-1 text-[11px] uppercase tracking-wider text-text-muted">{label}</div>
      <div className="text-[22px] font-bold tabular-nums text-text-primary">{value}</div>
      {sub && <div className="mt-0.5 text-[12px] text-text-muted">{sub}</div>}
    </div>
  );
}

function ComparisonTable({ result }) {
  const rows = [
    {
      label: "Cost",
      legibill: "Included",
      lawyer: fmt(result.total_cost),
      nothing: "$0 today",
      legibillClass: "text-status-chaptered-text font-semibold",
      lawyerClass: "text-status-committee-text font-semibold",
      nothingClass: "text-text-muted",
    },
    {
      label: "Timeline",
      legibill: "Seconds",
      lawyer: "6–8 weeks",
      nothing: "—",
      legibillClass: "text-status-chaptered-text font-semibold",
      lawyerClass: "text-text-secondary",
      nothingClass: "text-text-muted",
    },
    {
      label: "Bills covered",
      legibill: `All ${result.ca_bills_introduced.toLocaleString()}`,
      lawyer: "Selective",
      nothing: "None",
      legibillClass: "text-status-chaptered-text font-semibold",
      lawyerClass: "text-text-secondary",
      nothingClass: "text-text-muted",
    },
    {
      label: "Compliance risk",
      legibill: "Managed",
      lawyer: "Managed",
      nothing: "High",
      legibillIcon: <ShieldCheck className="inline h-3.5 w-3.5 mr-1 text-status-chaptered-text" />,
      lawyerIcon:   <ShieldCheck className="inline h-3.5 w-3.5 mr-1 text-status-chaptered-text" />,
      nothingIcon:  <ShieldAlert className="inline h-3.5 w-3.5 mr-1 text-status-committee-text" />,
      legibillClass: "text-status-chaptered-text font-semibold",
      lawyerClass:   "text-status-chaptered-text",
      nothingClass:  "text-status-committee-text font-semibold",
    },
  ];

  return (
    <div className="animate-slide-up overflow-hidden rounded-3xl border border-border bg-card shadow-card" style={{ animationDelay: "0.14s" }}>
      <div className="border-b border-border px-6 py-4">
        <div className="text-[13px] font-semibold text-text-primary">How it compares</div>
        <div className="mt-0.5 text-[12px] text-text-muted">Legi-Bill vs. hiring a law firm vs. doing nothing</div>
      </div>

      {/* Header row */}
      <div className="grid grid-cols-4 border-b border-border bg-chip-alt/60 px-6 py-2.5">
        <div />
        <div className="text-center text-[12px] font-semibold text-text-primary">Legi-Bill</div>
        <div className="text-center text-[12px] font-medium text-text-secondary">Hire a Firm</div>
        <div className="text-center text-[12px] font-medium text-text-secondary">Do Nothing</div>
      </div>

      {rows.map((row, i) => (
        <div
          key={row.label}
          className={`grid grid-cols-4 px-6 py-3 ${i < rows.length - 1 ? "border-b border-border" : ""}`}
        >
          <div className="text-[13px] text-text-muted self-center">{row.label}</div>
          <div className={`text-center text-[13px] self-center ${row.legibillClass}`}>
            {row.legibillIcon}{row.legibill}
          </div>
          <div className={`text-center text-[13px] self-center ${row.lawyerClass}`}>
            {row.lawyerIcon}{row.lawyer}
          </div>
          <div className={`text-center text-[13px] self-center ${row.nothingClass}`}>
            {row.nothingIcon}{row.nothing}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export default function LegalIntelligence() {
  const [companyText, setCompanyText] = useState("");
  const [state, setState] = useState("");
  const [rateOverride, setRateOverride] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({});
  const resultsRef = useRef(null);

  async function calculate() {
    if (!companyText.trim()) return;
    setLoading(true);
    setError(null);
    const fd = new FormData();
    fd.append("company_text", companyText);
    if (state) fd.append("state", state);
    if (rateOverride) fd.append("hourly_rate", rateOverride);
    try {
      const res = await fetch("/api/legal-savings", { method: "POST", body: fd });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const open = {};
      data.categories.forEach((c) => (open[c.category] = true));
      setExpanded(open);
      setResult(data);
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function toggle(cat) {
    setExpanded((prev) => ({ ...prev, [cat]: !prev[cat] }));
  }

  return (
    <div className="space-y-8">

      {/* ── Header ── */}
      <div className="animate-slide-up">
        <div className="mb-2 flex items-center gap-2 text-text-secondary">
          <Scale className="h-4 w-4 text-accent-gold" strokeWidth={2.4} />
          <span className="text-[12px] uppercase tracking-[0.18em]">Legal Intelligence</span>
        </div>
        <h1 className="animate-shimmer-text text-[32px] font-bold tracking-tight">
          Legal Cost Savings
        </h1>
        <p className="mt-2 max-w-[560px] text-[15px] leading-relaxed text-text-secondary">
          Enter your company details and we'll show you exactly what a compliance
          attorney would charge — and what Legi-Bill handles for you automatically.
        </p>
      </div>

      {/* ── Input card ── */}
      <div
        className="animate-slide-up rounded-3xl border border-border bg-card p-6 shadow-card"
        style={{ animationDelay: "0.08s" }}
      >
        <label className="mb-2 block text-[13px] font-semibold text-text-primary">
          Describe your company
        </label>
        <textarea
          rows={3}
          placeholder="e.g. We're a 60-person fintech startup in Austin building B2B payment infrastructure for mid-market businesses…"
          className="w-full resize-none rounded-xl border border-border bg-chip-alt px-4 py-3 text-[14px] text-text-primary placeholder:text-text-muted focus:border-accent-gold focus:outline-none"
          value={companyText}
          onChange={(e) => setCompanyText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) calculate(); }}
        />

        <div className="mt-3 flex flex-wrap items-end gap-3">
          {/* State picker */}
          <div>
            <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">
              State
            </label>
            <select
              value={state}
              onChange={(e) => setState(e.target.value)}
              className="w-48 rounded-xl border border-border bg-chip-alt px-3 py-2 text-[13px] text-text-primary focus:border-accent-gold focus:outline-none"
            >
              {US_STATES.map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
          </div>

          {/* Rate override */}
          <div>
            <label className="mb-1 block text-[11px] uppercase tracking-wider text-text-muted">
              Override rate ($/hr)
            </label>
            <input
              type="number"
              min={0}
              placeholder="Auto by industry"
              className="w-40 rounded-xl border border-border bg-chip-alt px-3 py-2 text-[13px] text-text-primary placeholder:text-text-muted focus:border-accent-gold focus:outline-none"
              value={rateOverride}
              onChange={(e) => setRateOverride(e.target.value)}
            />
          </div>

          <button
            onClick={calculate}
            disabled={!companyText.trim() || loading}
            className="rounded-xl bg-action-dark px-6 py-2 text-[13px] font-semibold text-text-invert transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {loading ? "Calculating…" : "Calculate Savings"}
          </button>
        </div>

        {error && <p className="mt-3 text-[12px] text-status-committee-text">{error}</p>}
      </div>

      {/* ── Results ── */}
      {result && (
        <div ref={resultsRef} className="space-y-5">

          {/* Hero banner */}
          <div
            className="animate-slide-up overflow-hidden rounded-3xl border border-accent-gold/30 bg-accent-gold/10 px-8 py-6 shadow-card"
            style={{ animationDelay: "0s" }}
          >
            <div className="flex items-center justify-between gap-6">
              <div>
                <div className="text-[13px] uppercase tracking-wider text-text-muted">
                  Attorney work automated
                </div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-[52px] font-bold tabular-nums leading-none text-text-primary">
                    {result.total_hours}
                  </span>
                  <span className="text-[20px] text-text-muted">hours</span>
                </div>
                <div className="mt-2 text-[14px] text-text-secondary">
                  Delivered in seconds — not the{" "}
                  <span className="font-semibold text-text-primary">6–8 weeks</span> a firm would take.
                </div>
              </div>
              <div className="hidden flex-col items-end gap-2 sm:flex">
                <div className="text-[13px] uppercase tracking-wider text-text-muted">
                  Estimated legal bill
                </div>
                <div className="text-[44px] font-bold tabular-nums leading-none text-accent-gold">
                  {fmt(result.total_cost)}
                </div>
                <div className="text-[13px] font-semibold text-status-chaptered-text">
                  Included in your subscription
                </div>
              </div>
            </div>
          </div>

          {/* 3 stat cards */}
          <div className="grid grid-cols-3 gap-3">
            <StatCard
              label="Industry detected"
              value={INDUSTRY_DISPLAY[result.industry] ?? result.industry}
              sub={result.lawyer_title}
              delay="0.04s"
            />
            <StatCard
              label={`Attorney rate · ${result.state_label}`}
              value={`$${result.hourly_rate}/hr`}
              sub={
                result.state && result.state_multiplier !== 1.0
                  ? `${result.state_multiplier > 1 ? "+" : ""}${Math.round((result.state_multiplier - 1) * 100)}% vs. national avg`
                  : "National average rate"
              }
              delay="0.08s"
            />
            <StatCard
              label="Relevant bills found"
              value={result.matched_bill_count}
              sub={`of ${result.ca_bills_introduced.toLocaleString()} introduced this session`}
              delay="0.12s"
            />
          </div>

          {/* Benchmark context */}
          <div
            className="animate-slide-up rounded-2xl border border-border bg-chip-alt px-5 py-4 shadow-card"
            style={{ animationDelay: "0.1s" }}
          >
            <div className="flex items-start gap-3">
              <DollarSign className="mt-0.5 h-4 w-4 shrink-0 text-status-committee-text" strokeWidth={2} />
              <p className="text-[13px] leading-relaxed text-text-secondary">
                <span className="font-semibold text-text-primary">
                  {INDUSTRY_DISPLAY[result.industry] ?? result.industry} companies
                  {result.state ? ` in ${result.state_label}` : ""} typically budget{" "}
                  {fmtRange(result.benchmark_low, result.benchmark_high)}/year{" "}
                </span>
                {result.benchmark_note}. A full one-time regulatory engagement like
                this is typically scoped and billed separately on top of that retainer.
              </p>
            </div>
          </div>

          {/* Comparison table */}
          <ComparisonTable result={result} />

          {/* Invoice */}
          <div
            className="animate-slide-up overflow-hidden rounded-3xl border border-border bg-card shadow-card"
            style={{ animationDelay: "0.18s" }}
          >
            {/* Invoice header */}
            <div className="flex items-center justify-between border-b border-border px-6 py-4">
              <div>
                <div className="text-[11px] uppercase tracking-wider text-text-muted">
                  Line-item breakdown
                </div>
                <div className="mt-0.5 text-[15px] font-semibold text-text-primary">
                  What a law firm would invoice
                </div>
              </div>
              <div className="text-right">
                <div className="text-[11px] text-text-muted">
                  At {fmt(result.hourly_rate)}/hr · {result.matched_bill_count} relevant bills
                </div>
              </div>
            </div>

            {/* Column labels */}
            <div className="grid grid-cols-[1fr_72px_100px_140px] gap-2 border-b border-border px-6 py-2">
              <div className="text-[11px] uppercase tracking-wider text-text-muted">Service</div>
              <div className="text-right text-[11px] uppercase tracking-wider text-text-muted">Hrs</div>
              <div className="text-right text-[11px] uppercase tracking-wider text-text-muted">Cost</div>
              <div className="text-center text-[11px] uppercase tracking-wider text-text-muted">Legi-Bill status</div>
            </div>

            {result.categories.map((cat) => (
              <div key={cat.category} className="border-b border-border last:border-0">
                {/* Category header */}
                <button
                  onClick={() => toggle(cat.category)}
                  className="grid w-full grid-cols-[1fr_72px_100px_140px] gap-2 px-6 py-3 transition-colors hover:bg-chip-alt"
                >
                  <div className="flex items-center gap-2">
                    {expanded[cat.category]
                      ? <ChevronUp className="h-3.5 w-3.5 shrink-0 text-text-muted" />
                      : <ChevronDown className="h-3.5 w-3.5 shrink-0 text-text-muted" />}
                    <span className={`text-[13px] font-semibold ${CATEGORY_ACCENT[cat.category] ?? "text-text-primary"}`}>
                      {cat.category}
                    </span>
                  </div>
                  <div className="self-center text-right text-[13px] font-medium tabular-nums text-text-primary">
                    {cat.subtotal_hours}h
                  </div>
                  <div className="self-center text-right text-[13px] tabular-nums">
                    <span className="text-text-muted line-through">{fmt(cat.subtotal_cost)}</span>
                  </div>
                  <div className="flex items-center justify-center">
                    <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${CATEGORY_BADGE_BG[cat.category] ?? "bg-chip text-text-muted"}`}>
                      {cat.badge}
                    </span>
                  </div>
                </button>

                {/* Task rows */}
                {expanded[cat.category] && cat.tasks.map((task) => (
                  <div
                    key={task.name}
                    className="grid grid-cols-[1fr_72px_100px_140px] gap-2 bg-chip-alt/50 px-6 py-2.5"
                  >
                    <div className="pl-5">
                      <div className="text-[13px] text-text-primary">{task.name}</div>
                      <div className="mt-0.5 text-[11px] text-text-muted">{task.description}</div>
                    </div>
                    <div className="self-center text-right text-[12px] tabular-nums text-text-secondary">
                      {task.hours}h
                    </div>
                    <div className="self-center text-right text-[12px] tabular-nums">
                      <span className="text-text-muted line-through">{fmt(task.cost)}</span>
                    </div>
                    <div className="flex items-center justify-center self-center">
                      <div className="flex items-center gap-1 rounded-full bg-status-chaptered-bg px-2 py-0.5">
                        <CheckCircle2 className="h-3 w-3 text-status-chaptered-text" strokeWidth={2.5} />
                        <span className="text-[10px] font-semibold text-status-chaptered-text">Automated</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ))}

            {/* Total */}
            <div className="border-t-2 border-accent-gold/30 bg-accent-gold/8 px-6 py-5">
              <div className="flex items-end justify-between">
                <div className="flex items-center gap-3">
                  <Clock className="h-5 w-5 text-text-muted" strokeWidth={1.5} />
                  <div>
                    <div className="text-[12px] text-text-muted">Total attorney hours</div>
                    <div className="text-[28px] font-bold tabular-nums text-text-primary">
                      {result.total_hours}
                      <span className="ml-1 text-[14px] font-normal text-text-muted">hours</span>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[12px] text-text-muted">Estimated attorney fees</div>
                  <div className="text-[28px] font-bold tabular-nums text-accent-gold">
                    {fmt(result.total_cost)}
                  </div>
                  <div className="mt-1 text-[12px] font-semibold text-status-chaptered-text">
                    Included in your Legi-Bill subscription
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Source footnote */}
          <p
            className="animate-slide-up text-[11px] leading-relaxed text-text-muted"
            style={{ animationDelay: "0.22s" }}
          >
            Bill volume: <span className="font-medium">4,821 bills introduced</span> and{" "}
            <span className="font-medium">1,684 signed into law</span> in the 2023-24 CA session
            (Capitol Weekly; CalMatters; LAist). Attorney rates:{" "}
            <span className="font-medium">2024 Clio Legal Trends Report</span>,{" "}
            <span className="font-medium">ABA Legal Technology Survey</span>, and{" "}
            <span className="font-medium">BLS Occupational Employment Statistics (SOC 23-1011, May 2023)</span>.
            State adjustments based on BLS regional wage indices. Hours estimates reflect typical
            compliance engagement scope; actual engagements vary by firm and complexity.
          </p>
        </div>
      )}
    </div>
  );
}
