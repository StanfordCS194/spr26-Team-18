import { CheckCircle2, Circle, ArrowRight, Sparkles, MessageCircle, Scale, Gauge } from "lucide-react";

const STEPS = [
  {
    id: "grade",
    n: "01",
    tab: "startup",
    Icon: Sparkles,
    iconColor: "#0052ff",
    iconBg: "#eef3ff",
    accentColor: "#0052ff",
    accentBg: "#eef3ff",
    accentBorder: "#bfdbfe",
    title: "Grade your startup",
    description:
      "Upload your GitHub repo, PRD, and finance CSV. Get a letter grade across 5 axes — Engineering, Legal, Financial, Compliance, and Product — in under 30 seconds.",
    cta: "Go to Startup Health",
    doneLine: "Grade complete",
  },
  {
    id: "review",
    n: "02",
    tab: "recs",
    Icon: MessageCircle,
    iconColor: "#00874a",
    iconBg: "#ccfce7",
    accentColor: "#00874a",
    accentBg: "#f0fdf4",
    accentBorder: "#86efac",
    title: "Review your recommendations",
    description:
      "See your top 5 highest-leverage fixes, ranked by dollar impact and grade weight. Each recommendation links to the exact file and line that needs to change.",
    cta: "Go to Recommendations",
    doneLine: "Recommendations reviewed",
  },
  {
    id: "fix",
    n: "03",
    tab: "legal",
    Icon: Scale,
    iconColor: "#c2410c",
    iconBg: "#ffedd5",
    accentColor: "#c2410c",
    accentBg: "#fff7ed",
    accentBorder: "#fed7aa",
    title: "Fix & explore tools",
    description:
      "Dive into Legal Intelligence to see the attorney fees Legi-Bill automates, or run a Financial compliance scan. Understand your full exposure before your next raise.",
    cta: "Go to Legal",
    doneLine: "Tools explored",
  },
];

function StepCard({ step, done, isCurrent, locked, onTabChange, delay }) {
  return (
    <div
      className="animate-slide-up relative flex flex-col rounded-3xl border-2 bg-white p-7 shadow-card transition-all hover:-translate-y-1 hover:shadow-card-hover"
      style={{
        animationDelay: delay,
        borderColor: done
          ? "#86efac"
          : isCurrent
          ? step.accentColor + "66"
          : "#d4e0ff",
        backgroundColor: done ? "#f0fdf4" : isCurrent ? step.accentBg : "#fff",
        opacity: locked ? 0.5 : 1,
      }}
    >
      {/* Step number + status */}
      <div className="mb-5 flex items-center justify-between">
        <div
          className="flex h-11 w-11 items-center justify-center rounded-2xl"
          style={{ backgroundColor: done ? "#ccfce7" : step.iconBg }}
        >
          {done ? (
            <CheckCircle2 className="h-6 w-6 text-[#00874a]" strokeWidth={2.5} />
          ) : (
            <step.Icon
              className="h-6 w-6"
              style={{ color: step.iconColor }}
              strokeWidth={2.2}
            />
          )}
        </div>

        <div className="flex items-center gap-2">
          {done ? (
            <span className="rounded-full bg-[#ccfce7] px-3 py-1 text-[11px] font-bold text-[#00874a]">
              {step.doneLine}
            </span>
          ) : isCurrent ? (
            <span
              className="rounded-full px-3 py-1 text-[11px] font-bold text-white"
              style={{ backgroundColor: step.accentColor }}
            >
              Up next
            </span>
          ) : (
            <span className="rounded-full bg-chip px-3 py-1 text-[11px] font-bold text-text-muted">
              Locked
            </span>
          )}
          <span
            className="text-[11px] font-bold uppercase tracking-[0.2em]"
            style={{ color: done ? "#00874a" : step.accentColor }}
          >
            Step {step.n}
          </span>
        </div>
      </div>

      {/* Content */}
      <h3 className="mb-2 text-[20px] font-bold leading-snug text-text-primary">
        {step.title}
      </h3>
      <p className="flex-1 text-[14px] leading-relaxed text-text-secondary">
        {step.description}
      </p>

      {/* CTA */}
      <button
        disabled={locked}
        onClick={() => onTabChange(step.tab)}
        className="mt-6 flex items-center gap-2 self-start rounded-xl px-5 py-2.5 text-[13px] font-bold text-white transition-all hover:opacity-90 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
        style={{ backgroundColor: done ? "#00874a" : step.accentColor }}
      >
        {done ? "Revisit" : step.cta}
        <ArrowRight className="h-4 w-4" strokeWidth={2.5} />
      </button>
    </div>
  );
}

export default function GetStarted({ completedSteps, onTabChange }) {
  const currentIdx = completedSteps.size;
  const allDone = completedSteps.size >= STEPS.length;

  return (
    <div className="space-y-10 pb-4">

      {/* Header */}
      <div className="animate-slide-up space-y-3" style={{ animationDelay: "0s" }}>
        <div className="flex items-center gap-2 text-text-secondary">
          <Gauge className="h-4 w-4 text-[#0052ff]" strokeWidth={2.4} />
          <span className="text-[12px] font-bold uppercase tracking-[0.18em] text-[#0052ff]">
            Your journey
          </span>
        </div>
        <h1 className="animate-shimmer-text text-[40px] font-bold leading-tight tracking-tight">
          Get started with Legi-Bill
        </h1>
        <p className="max-w-[560px] text-[16px] leading-relaxed text-text-secondary">
          Three steps to full compliance clarity. Complete them in order — each step unlocks the next.
        </p>
      </div>

      {/* Progress bar */}
      <div
        className="animate-slide-up rounded-2xl border-2 border-[#d4e0ff] bg-white p-5 shadow-card"
        style={{ animationDelay: "0.08s" }}
      >
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[13px] font-bold text-text-primary">
            {allDone ? "All steps complete!" : `Step ${Math.min(currentIdx + 1, 3)} of 3`}
          </span>
          <span className="text-[12px] font-semibold text-text-muted">
            {completedSteps.size} / {STEPS.length} complete
          </span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-chip">
          <div
            className="h-full rounded-full bg-[#0052ff] transition-all duration-700"
            style={{ width: `${(completedSteps.size / STEPS.length) * 100}%` }}
          />
        </div>
        {allDone && (
          <p className="mt-3 text-[13px] font-semibold text-[#00874a]">
            You've completed the full Legi-Bill workflow. Explore any tool freely from the nav above.
          </p>
        )}
      </div>

      {/* Step cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        {STEPS.map((step, i) => {
          const done = completedSteps.has(step.id);
          const isCurrent = !done && i === currentIdx;
          const locked = !done && i > currentIdx;
          return (
            <StepCard
              key={step.id}
              step={step}
              done={done}
              isCurrent={isCurrent}
              locked={locked}
              onTabChange={onTabChange}
              delay={`${0.12 + i * 0.09}s`}
            />
          );
        })}
      </div>

      {/* Bottom hint */}
      <p
        className="animate-slide-up text-center text-[12px] text-text-muted"
        style={{ animationDelay: "0.4s" }}
      >
        You can always return to this page from the nav above.
      </p>
    </div>
  );
}
