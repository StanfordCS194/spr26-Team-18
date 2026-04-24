export function VotingPatternSummaryCard({ summaryVote }) {
  return (
    <section className="panel emphasis-card">
      <p className="eyebrow">Voting Pattern Summary</p>
      <h3>Momentum is trending toward stricter compliance signaling.</h3>
      <p>
        The latest notable bill is <strong>{summaryVote.title}</strong>, which {summaryVote.outcome.toLowerCase()}.
      </p>
    </section>
  );
}
