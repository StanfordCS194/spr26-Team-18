import { FileText, Landmark, Building2 } from "lucide-react";
import logo from "../assets/logo.png";

const TABS = [
  { id: "bills", label: "Bill Lookup", Icon: FileText },
  { id: "legislators", label: "Legislator Tracker", Icon: Landmark },
  { id: "company", label: "Company Match", Icon: Building2 },
];

export default function Sidebar({ activeTab, onTabChange }) {
  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-border bg-sidebar-gradient">
      <div className="flex items-center gap-2.5 px-6 pt-7 pb-6">
        <img src={logo} alt="" className="h-8 w-8 rounded-lg object-contain" />
        <span className="text-[17px] font-bold tracking-tight text-text-primary">
          Legi-Bill
        </span>
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-3">
        {TABS.map(({ id, label, Icon }) => {
          const isActive = activeTab === id;
          return (
            <button
              key={id}
              onClick={() => onTabChange(id)}
              className={
                "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[14px] font-medium transition-all " +
                (isActive
                  ? "bg-card text-text-primary shadow-card"
                  : "text-text-secondary hover:bg-card/60 hover:text-text-primary")
              }
            >
              <Icon
                className={
                  "h-[18px] w-[18px] transition-colors " +
                  (isActive ? "text-accent-gold" : "text-text-muted group-hover:text-text-primary")
                }
                strokeWidth={2}
              />
              <span>{label}</span>
            </button>
          );
        })}
      </nav>

      <div className="px-6 pb-6 pt-4 text-[11px] leading-relaxed text-text-muted">
        California environmental legislation
        <br />
        for mid-market companies.
      </div>
    </aside>
  );
}
