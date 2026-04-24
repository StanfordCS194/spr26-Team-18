export function LegislatorProfileHeader({ legislator, onBack }) {
  return (
    <section className="panel profile-header">
      <button className="ghost-button" onClick={onBack}>
        Back to search
      </button>
      <div>
        <p className="eyebrow">
          {legislator.party} · {legislator.state}
        </p>
        <h2>{legislator.name}</h2>
        <p>{legislator.focus}</p>
      </div>
    </section>
  );
}
