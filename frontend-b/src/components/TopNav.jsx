import { Home, Scale, Sparkles, MessageCircle, Gauge, MapPin } from "lucide-react";
import logo from "../assets/logo.png";

const TABS = [
  { id: "home",        label: "Home",            Icon: Home },
  { id: "get-started", label: "Get Started",     Icon: MapPin },
  { id: "startup",     label: "Startup Health",  Icon: Sparkles },
  { id: "legal",       label: "Legal",           Icon: Scale },
  { id: "recs",        label: "Recommendations", Icon: MessageCircle },
  { id: "financial",   label: "Financial",       Icon: Gauge },
];

export default function TopNav({ activeTab, onTabChange, recsBadge = false }) {
  return (
    <header className="fixed top-0 left-0 right-0 z-40 flex h-14 items-center border-b border-white/10 bg-sidebar-gradient px-6">
      {/* Logo */}
      <button
        onClick={() => onTabChange("home")}
        className="flex items-center gap-2.5 mr-8 shrink-0"
      >
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#0052ff]">
          <img src={logo} alt="" className="h-5 w-5 rounded object-contain" />
        </div>
        <span className="text-[16px] font-bold tracking-tight text-white">
          Legi-Bill
        </span>
      </button>

      {/* Nav links */}
      <nav className="flex items-center gap-1">
        {TABS.map(({ id, label, Icon }) => {
          const isActive = activeTab === id;
          const showBadge = id === "recs" && recsBadge;
          return (
            <button
              key={id}
              onClick={() => onTabChange(id)}
              className={
                "group relative flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-[13px] font-semibold transition-all " +
                (isActive
                  ? "bg-[#0052ff] text-white shadow-glow"
                  : "text-white/50 hover:bg-white/10 hover:text-white")
              }
            >
              <Icon
                className={
                  "h-[15px] w-[15px] shrink-0 transition-colors " +
                  (isActive ? "text-white" : "text-white/40 group-hover:text-white")
                }
                strokeWidth={2.2}
              />
              <span>{label}</span>
              {showBadge && (
                <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-[#FF6B00] text-[9px] font-bold text-white">
                  !
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Right side badge */}
      <div className="ml-auto rounded-lg bg-white/5 px-3 py-1 text-[11px] font-semibold text-white/40">
        CA compliance · founders
      </div>
    </header>
  );
}
