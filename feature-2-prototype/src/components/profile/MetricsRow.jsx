import { MetricCard } from "./MetricCard";

export function MetricsRow({ metrics }) {
  return (
    <section className="metrics-row">
      {metrics.map((metric) => (
        <MetricCard key={metric.label} metric={metric} />
      ))}
    </section>
  );
}
