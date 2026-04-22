export function BillSummarySection({ bill }) {
  return (
    <section className="drawer-section">
      <h4>Bill summary</h4>
      <p>{bill.outcome}</p>
    </section>
  );
}
