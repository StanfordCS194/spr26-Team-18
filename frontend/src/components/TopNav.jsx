import logo from "../assets/logo.png";

const TABS = [
  { id: "bills", label: "Bill Lookup" },
  { id: "legislators", label: "Legislator Tracker" },
  { id: "company", label: "Company Match" },
];

export default function TopNav({ activeTab, onTabChange }) {
  return (
    <nav className="nav">
      <img src={logo} alt="Legi-Bill" className="nav-logo" />
      <div className="nav-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`nav-tab${activeTab === tab.id ? " active" : ""}`}
            onClick={() => onTabChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </nav>
  );
}
