import logo from "../assets/logo.png";

const TABS = [
  { id: "bills", label: "Bill Lookup" },
  { id: "legislators", label: "Legislator Tracker" },
  { id: "company", label: "Company Match" },
];

export default function TopNav({ activeTab, onTabChange }) {
  return (
    <nav className="sticky top-0 z-50 flex h-16 items-center gap-8 bg-nav px-8">
      <img src={logo} alt="Legi-Bill" className="h-9 w-auto object-contain" />
      <div className="flex flex-1 justify-center gap-2">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={
                "rounded-full border-[1.5px] px-5 py-[7px] text-sm font-medium transition-colors " +
                (isActive
                  ? "border-accent-gold bg-accent-gold text-text-primary font-semibold"
                  : "border-accent-gold-soft bg-transparent text-white/75 hover:border-accent-gold hover:text-white")
              }
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
