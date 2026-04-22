export function CompanyImpactCard({ companyImpact }) {
  return (
    <section className="panel">
      <p className="eyebrow">{companyImpact.title}</p>
      <p>{companyImpact.summary}</p>
    </section>
  );
}
