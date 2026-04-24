export function LegislatorVoteSection({ bill }) {
  return (
    <section className="drawer-section">
      <h4>Legislator vote</h4>
      <p>Most recent tracked position: {bill.outcome}.</p>
    </section>
  );
}
