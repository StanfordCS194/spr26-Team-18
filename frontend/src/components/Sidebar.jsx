import {
  Home,
  Scale,
  Sparkles,
  MessageCircle,
  Gauge,
  ShieldAlert,
  FlaskConical,
  LogOut,
  RotateCcw,
} from "lucide-react";
import logo from "../assets/logo.png";

const TABS = [
  { id: "home",      label: "Home",            Icon: Home },
  { id: "scanner",   label: "Repo Scanner",    Icon: ShieldAlert },
  { id: "benchmark", label: "Benchmark",       Icon: FlaskConical },
  { id: "startup",   label: "Startup Health",  Icon: Sparkles },
  { id: "legal",     label: "Legal",           Icon: Scale },
  { id: "recs",      label: "Recommendations", Icon: MessageCircle },
  { id: "financial", label: "Financial",       Icon: Gauge },
];

export default function Sidebar({ activeTab, onTabChange, profile, onLogout, onResetDemo }) {
  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-64 flex-col bg-sidebar-gradient border-r border-white/10">
      {/* Logo */}
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

      <div className="mx-3 mb-6 space-y-3">
        {profile && (
          <div className="rounded-xl bg-white/5 px-4 py-3">
            <div className="text-[10px] uppercase tracking-[0.16em] text-white/35">Workspace</div>
            <div className="mt-1 truncate text-[13px] font-semibold text-white">
              {profile.companyName || "Demo company"}
            </div>
            <div className="mt-0.5 truncate text-[11px] text-white/40">
              {profile.repoUrl || "No repo selected"}
            </div>
          </div>
        )}
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={onResetDemo}
            className="flex items-center justify-center gap-1.5 rounded-xl bg-white/5 px-2 py-2 text-[11px] font-semibold text-white/50 transition-colors hover:bg-white/10 hover:text-white"
          >
            <RotateCcw className="h-3.5 w-3.5" strokeWidth={2.1} />
            Reset
          </button>
          <button
            onClick={onLogout}
            className="flex items-center justify-center gap-1.5 rounded-xl bg-white/5 px-2 py-2 text-[11px] font-semibold text-white/50 transition-colors hover:bg-white/10 hover:text-white"
          >
            <LogOut className="h-3.5 w-3.5" strokeWidth={2.1} />
            Log out
          </button>
        </div>
      </div>
    </aside>
  );
}
