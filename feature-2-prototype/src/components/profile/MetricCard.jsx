export function MetricCard({ metric }) {
  return (
    <article className="panel metric-card">
      <span>{metric.label}</span>
      <strong>{metric.value}</strong>
    </article>
  );
}
