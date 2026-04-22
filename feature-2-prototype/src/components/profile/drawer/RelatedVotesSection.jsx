export function RelatedVotesSection({ relatedVotes }) {
  return (
    <section className="drawer-section">
      <h4>Related votes</h4>
      <ul className="topic-list">
        {relatedVotes.map((vote) => (
          <li key={vote}>{vote}</li>
        ))}
      </ul>
    </section>
  );
}
