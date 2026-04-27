import { useState } from "react";
import BillDetail from "./BillDetail";

const STATUS_STYLES = {
  chaptered: "bg-status-chaptered-bg text-status-chaptered-text",
  enrolled: "bg-status-enrolled-bg text-status-enrolled-text",
  committee: "bg-status-committee-bg text-status-committee-text",
  default: "bg-status-default-bg text-status-default-text",
};

const TIER_STYLES = {
  High: "bg-status-chaptered-bg text-status-chaptered-text",
  Medium: "bg-status-committee-bg text-status-committee-text",
  Low: "bg-status-default-bg text-status-default-text",
};

function statusKey(status) {
  const s = (status || "").toLowerCase();
  if (s.includes("chaptered")) return "chaptered";
  if (s.includes("enrolled")) return "enrolled";
  if (s.includes("committee") || s.includes("introduced")) return "committee";
  return "default";
}

export default function BillCard({ bill, relevance }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      onClick={() => setExpanded((e) => !e)}
      className={
        "cursor-pointer rounded-[14px] border-[1.5px] bg-card px-5 py-[18px] shadow-card transition-all " +
        "hover:shadow-card-hover " +
        (expanded
          ? "border-accent-gold"
          : "border-transparent hover:border-text-primary")
      }
    >
      <div className="flex items-start gap-3.5">
        <span className="flex-shrink-0 whitespace-nowrap rounded-md bg-action-dark px-2.5 py-[3px] text-[13px] font-bold text-white">
          {bill.bill_number}
        </span>
        <span className="flex-1 text-[15px] font-semibold leading-snug text-text-primary">
          {bill.title}
        </span>
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-2.5">
        {relevance && (
          <span
            className={
              "rounded-full px-2.5 py-[3px] text-xs font-semibold " +
              TIER_STYLES[relevance.tier]
            }
            title={`Relevance score: ${relevance.score}`}
          >
            {relevance.tier} relevance
          </span>
        )}
        <span
          className={
            "rounded-full px-2.5 py-[3px] text-xs font-semibold " +
            STATUS_STYLES[statusKey(bill.status)]
          }
        >
          {bill.status || "Unknown"}
        </span>
        {bill.subjects?.slice(0, 3).map((s) => (
          <span
            key={s}
            className="rounded-full border border-border-chip bg-chip px-2.5 py-[2px] text-[11px] text-[#4a607a]"
          >
            {s}
          </span>
        ))}
      </div>
      {expanded && <BillDetail billNumber={bill.bill_number} />}
    </div>
  );
}
