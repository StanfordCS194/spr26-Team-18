export function LegislatorCard({ legislator, onSelect }) {
  return (
    <article className="panel card">
      <div>
        <p className="eyebrow">
          {legislator.party} · {legislator.state}
        </p>
        <h4>{legislator.name}</h4>
        <p>{legislator.focus}</p>
      </div>
      <button onClick={onSelect}>Open profile</button>
    </article>
  );
}
