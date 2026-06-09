import { X, MessageCircle } from "lucide-react";

const AXIS_TITLES = {
  emissions: "Emissions",
  water: "Water",
  packaging: "Packaging",
  labor: "Labor",
  disclosure: "Disclosure",
};

const AXIS_DESCRIPTIONS = {
  emissions: "Greenhouse gas, air quality, oil & gas, transportation emissions.",
  water: "Water quality, water rights, drought, wastewater, agricultural water use.",
  packaging: "Producer responsibility, single-use plastics, recycling, textile recovery.",
  labor: "Workplace heat standards, hazardous-materials worker safety, environmental justice.",
  disclosure: "Corporate climate disclosure (SB-253, SB-261), voluntary carbon market reporting.",
};

export default function AxisDrilldown({ axis, score, evidence, onClose, onChatAboutBill }) {
  const isHighlight = axis === "disclosure";

  return (
    <div className="rounded-3xl border border-border bg-card p-6 shadow-card">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
              Why this score?
            </span>
            {isHighlight && <span className="text-[11px] text-accent-gold">disclosure axis · weighted 1.5×</span>}
          </div>
          <h3 className="mt-1 text-[20px] font-bold capitalize tracking-tight">
            {AXIS_TITLES[axis] || axis}
            <span className="ml-3 font-mono text-[20px] tabular-nums text-text-secondary">
              {score}/100
            </span>
          </h3>
          <p className="mt-1 max-w-[640px] text-[13px] leading-relaxed text-text-secondary">
            {AXIS_DESCRIPTIONS[axis]}
          </p>
        </div>
        <button
          onClick={onClose}
          aria-label="Close drilldown"
          className="flex h-8 w-8 items-center justify-center rounded-full border border-border text-text-secondary transition-colors hover:bg-chip-alt hover:text-text-primary"
        >
          <X className="h-4 w-4" strokeWidth={2.4} />
        </button>
      </div>

      {(!evidence || evidence.length === 0) ? (
        <div className="rounded-xl border border-border-muted bg-chip-alt px-4 py-6 text-center text-[13px] text-text-secondary">
          No specific bills drove this axis. The score reflects baseline relevance only.
        </div>
      ) : (
        <ul className="space-y-3">
          {evidence.map((e, i) => (
            <li
              key={`${e.bill_number}-${i}`}
              className="rounded-2xl border border-border-muted bg-chip-alt px-5 py-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[13px] font-semibold text-text-primary">
                  {e.bill_number}
                </span>
              </div>
              {e.rationale && (
                <p className="mt-2 text-[13px] leading-relaxed text-text-primary">
                  {e.rationale}
                </p>
              )}
              {(e.bill_quote || e.quote) && (
                <div className="mt-3">
                  <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                    From the bill
                  </div>
                  <blockquote className="border-l-2 border-accent-gold-soft pl-3 text-[12px] italic leading-relaxed text-text-secondary">
                    &ldquo;{e.bill_quote || e.quote}&rdquo;
                  </blockquote>
                </div>
              )}
              {e.company_quote && (
                <div className="mt-3">
                  <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                    From the 10-K
                  </div>
                  <blockquote className="border-l-2 border-action-dark/40 pl-3 text-[12px] italic leading-relaxed text-text-secondary">
                    &ldquo;{e.company_quote}&rdquo;
                  </blockquote>
                </div>
              )}
              {onChatAboutBill && (
                <button
                  onClick={() => onChatAboutBill({ bill_number: e.bill_number, title: e.bill_number })}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-border-chip bg-card px-3 py-1.5 text-[12px] font-medium text-text-secondary transition-colors hover:text-text-primary"
                >
                  <MessageCircle className="h-3 w-3" strokeWidth={2.4} />
                  Chat about {e.bill_number}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
