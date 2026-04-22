export function ComplianceRelevanceSection({ bill }) {
  return (
    <section className="drawer-section">
      <h4>Compliance relevance</h4>
      <p>{bill.relevance}</p>
    </section>
  );
}
