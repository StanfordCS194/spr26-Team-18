import { useState } from "react";
import BillDetail from "./BillDetail";

function statusClass(status) {
  const s = (status || "").toLowerCase();
  if (s.includes("chaptered")) return "status-chaptered";
  if (s.includes("enrolled")) return "status-enrolled";
  if (s.includes("committee") || s.includes("introduced")) return "status-committee";
  return "status-default";
}

export default function BillCard({ bill }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`bill-card${expanded ? " expanded" : ""}`}
      onClick={() => setExpanded((e) => !e)}
    >
      <div className="bill-card-top">
        <span className="bill-number">{bill.bill_number}</span>
        <span className="bill-title">{bill.title}</span>
      </div>
      <div className="bill-meta">
        <span className={`status-badge ${statusClass(bill.status)}`}>{bill.status || "Unknown"}</span>
        {bill.subjects?.slice(0, 3).map((s) => (
          <span key={s} className="subject-chip">{s}</span>
        ))}
      </div>
      {expanded && <BillDetail billNumber={bill.bill_number} />}
    </div>
  );
}
