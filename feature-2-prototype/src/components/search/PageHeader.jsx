export function PageHeader({ title, subtitle }) {
  return (
    <section className="hero-card">
      <p className="eyebrow">Search Workspace</p>
      <h2>{title}</h2>
      <p>{subtitle}</p>
    </section>
  );
}
