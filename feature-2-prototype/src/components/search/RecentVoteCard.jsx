export function RecentVoteCard({ vote, onInspect }) {
  return (
    <article className="panel vote-card">
      <div>
        <p className="eyebrow">{vote.date}</p>
        <h4>{vote.title}</h4>
        <p>{vote.outcome}</p>
      </div>
      <button onClick={onInspect}>Inspect bill</button>
    </article>
  );
}
