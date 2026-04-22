export function TopNav({ activePage, onNavigate }) {
  return (
    <header className="top-nav">
      <div>
        <p className="eyebrow">Policy Intelligence Prototype</p>
        <h1>Legislator Tracker</h1>
      </div>
      <nav className="nav-actions" aria-label="Primary navigation">
        <button
          className={activePage === "search" ? "active" : ""}
          onClick={() => onNavigate("search")}
        >
          Search
        </button>
        <button
          className={activePage === "profile" ? "active" : ""}
          onClick={() => onNavigate("profile")}
        >
          Profile
        </button>
      </nav>
    </header>
  );
}
