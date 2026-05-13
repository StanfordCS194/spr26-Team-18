import { CheckCircle2, Circle } from "lucide-react";

const STEPS = [
  { id: "grade",  label: "Grade your startup",      tab: "startup" },
  { id: "review", label: "Review recommendations",  tab: "recs" },
  { id: "fix",    label: "Fix & explore tools",     tab: "legal" },
];

export default function WorkflowBanner({ completedSteps, onTabChange }) {
  const currentIdx = completedSteps.size;
  const allDone = completedSteps.size >= STEPS.length;

  return (
    <div className="fixed left-0 right-0 z-30 flex h-10 items-center border-b border-[#d4e0ff] bg-white/90 px-6 backdrop-blur-sm" style={{ top: "88px" }}>
      <div className="flex items-center gap-1 text-[11px] font-bold uppercase tracking-[0.15em] text-text-muted mr-5">
        Your journey
      </div>

      <div className="flex items-center gap-2">
        {STEPS.map((step, i) => {
          const done = completedSteps.has(step.id);
          const isCurrent = !done && i === currentIdx;

          return (
            <div key={step.id} className="flex items-center gap-2">
              <button
                onClick={() => onTabChange(step.tab)}
                className={
                  "flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-semibold transition-all " +
                  (done
                    ? "bg-[#ccfce7] text-[#00874a]"
                    : isCurrent
                    ? "bg-[#0052ff] text-white shadow-glow animate-pulse-ring"
                    : "bg-chip text-text-muted opacity-50")
                }
              >
                {done ? (
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0" strokeWidth={2.5} />
                ) : (
                  <Circle className="h-3.5 w-3.5 shrink-0" strokeWidth={2.5} />
                )}
                {step.label}
              </button>

              {i < STEPS.length - 1 && (
                <div
                  className={
                    "h-px w-8 transition-colors " +
                    (done ? "bg-[#00874a]/40" : "bg-[#d4e0ff]")
                  }
                />
              )}
            </div>
          );
        })}
      </div>

      {allDone && (
        <span className="ml-4 rounded-full bg-[#ccfce7] px-3 py-0.5 text-[11px] font-bold text-[#00874a]">
          All steps done
        </span>
      )}

      <div className="ml-auto text-[11px] text-text-muted">
        {completedSteps.size} / {STEPS.length} complete
      </div>
    </div>
  );
}
