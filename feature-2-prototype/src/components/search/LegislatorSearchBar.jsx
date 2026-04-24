export function LegislatorSearchBar() {
  return (
    <section className="panel inline-panel">
      <label className="search-field">
        <span>Search legislators or topics</span>
        <input type="text" placeholder="Try “procurement”, “CA”, or a legislator name" />
      </label>
      <button>Search</button>
    </section>
  );
}
