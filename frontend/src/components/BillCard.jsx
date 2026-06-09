import { useState } from "react";
import { MessageCircle, ChevronDown } from "lucide-react";
import BillDetail from "./BillDetail";

const STATUS_STYLES = {
  chaptered: "bg-status-chaptered-bg text-status-chaptered-text",
  enrolled:  "bg-status-enrolled-bg text-status-enrolled-text",
  committee: "bg-status-committee-bg text-status-committee-text",
  default:   "bg-status-default-bg text-status-default-text",
};

const STATUS_BORDER = {
  chaptered: "bg-status-chaptered-text",
  enrolled:  "bg-status-enrolled-text",
  committee: "bg-status-committee-text",
  default:   "bg-status-default-text",
};

const TIER_DOT = {
  High:   "bg-status-chaptered-text",
  Medium: "bg-status-committee-text",
  Low:    "bg-status-default-text",
};

const TIER_BG = {
  High:   "bg-status-chaptered-bg text-status-chaptered-text",
  Medium: "bg-status-committee-bg text-status-committee-text",
  Low:    "bg-status-default-bg text-status-default-text",
};

function statusKey(status) {
  const s = (status || "").toLowerCase();
  if (s.includes("chaptered")) return "chaptered";
  if (s.includes("enrolled"))  return "enrolled";
  if (s.includes("committee") || s.includes("introduced")) return "committee";
  return "default";
}

export default function BillCard({ bill, relevance, onChatAbout }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      onClick={() => setExpanded((e) => !e)}
      className={
        "cursor-pointer overflow-hidden rounded-2xl border bg-card shadow-card transition-all flex " +
        "hover:shadow-card-hover " +
        (expanded ? "border-accent-gold" : "border-border-muted hover:border-border-chip")
      }
    >
      {/* Left accent strip */}
      <div className={"w-1 flex-shrink-0 " + STATUS_BORDER[statusKey(bill.status)]} />

      {/* Card content */}
      <div className="flex-1 px-6 py-5">
        <div className="flex items-start gap-3.5">
          <span className="flex-shrink-0 whitespace-nowrap rounded-lg bg-action px-3 py-1.5 text-[13px] font-bold text-text-primary">
            {bill.bill_number}
          </span>
          <span className="flex-1 text-[15px] font-semibold leading-snug text-text-primary">
            {bill.title}
          </span>
          <ChevronDown
            className={
              "ml-2 h-4 w-4 flex-shrink-0 text-text-muted transition-transform duration-200 " +
              (expanded ? "rotate-180" : "rotate-0")
            }
            strokeWidth={2}
          />
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          {relevance && (
            <span
              className={
                "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold " +
                TIER_BG[relevance.tier]
              }
              title={`Relevance score: ${relevance.score}`}
            >
              <span className={"h-1.5 w-1.5 rounded-full " + TIER_DOT[relevance.tier]} />
              {relevance.tier} relevance
            </span>
          )}
          <span
            className={
              "rounded-full px-2.5 py-1 text-[11px] font-semibold " +
              STATUS_STYLES[statusKey(bill.status)]
            }
          >
            {bill.status || "Unknown"}
          </span>
          {bill.subjects?.slice(0, 3).map((s) => (
            <span
              key={s}
              className="rounded-full border border-border-chip bg-chip px-2.5 py-1 text-[11px] text-text-secondary"
            >
              {s}
            </span>
          ))}
        </div>

        {onChatAbout && (
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onChatAbout(bill); }}
              className="inline-flex items-center gap-1.5 rounded-full border border-border-chip bg-chip-alt px-3 py-1.5 text-[12px] font-semibold text-text-secondary transition-colors hover:border-action-dark hover:bg-card hover:text-action-dark"
            >
              <MessageCircle className="h-3.5 w-3.5" />
              Chat about this bill
            </button>
          </div>
        )}

        {expanded && <BillDetail billNumber={bill.bill_number} />}
      </div>
    </div>
  );
}
