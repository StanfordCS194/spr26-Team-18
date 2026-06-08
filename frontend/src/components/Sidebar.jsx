import { Home, Scale, Sparkles, MessageCircle, Gauge, ShieldAlert, FlaskConical } from "lucide-react";
import logo from "../assets/logo.png";

const TABS = [
  { id: "home",      label: "Home",            Icon: Home },
  { id: "scanner",   label: "Risk Scanner",    Icon: ShieldAlert },
  { id: "benchmark", label: "Benchmark",       Icon: FlaskConical },
  { id: "startup",   label: "Startup Health",  Icon: Sparkles },
  { id: "legal",     label: "Legal",           Icon: Scale },
  { id: "recs",      label: "Recommendations", Icon: MessageCircle },
  { id: "financial", label: "Financial",       Icon: Gauge },
];

export default function Sidebar({ activeTab, onTabChange }) {
  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-64 flex-col bg-sidebar-gradient border-r border-white/10">
      <div className="flex items-center gap-3 px-6 pt-7 pb-7">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#0052ff]">
          <img src={logo} alt="" className="h-6 w-6 rounded object-contain" />
        </div>
        <span className="text-[18px] font-bold tracking-tight text-white">
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
                "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[14px] font-semibold transition-all " +
                (isActive
                  ? "bg-[#0052ff] text-white shadow-glow"
                  : "text-white/50 hover:bg-white/10 hover:text-white")
              }
            >
              <Icon
                className={
                  "h-[18px] w-[18px] shrink-0 transition-colors " +
                  (isActive ? "text-white" : "text-white/40 group-hover:text-white")
                }
                strokeWidth={2.2}
              />
              <span>{label}</span>
            </button>
          );
        })}
      </nav>

      <div className="mx-3 mb-6 rounded-xl bg-white/5 px-4 py-3 text-[11px] leading-relaxed text-white/40">
        Startup risk &amp; compliance intelligence.
        <br />
        Powered by static analysis + LLMs.
      </div>
    </aside>
  );
}
