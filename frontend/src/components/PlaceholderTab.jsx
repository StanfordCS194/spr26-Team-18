export default function PlaceholderTab({ Icon, title, description }) {
  return (
    <div className="flex min-h-[360px] flex-col items-center justify-center rounded-3xl border border-border-muted bg-card p-14 text-center shadow-card">
      {Icon && (
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-chip">
          <Icon className="h-7 w-7 text-accent-gold" strokeWidth={1.75} />
        </div>
      )}
      <h2 className="mb-2 text-[22px] font-bold text-text-primary">{title}</h2>
      <p className="max-w-[420px] text-[14px] leading-relaxed text-text-muted">
        {description}
      </p>
      <span className="mt-5 inline-block rounded-full bg-accent-gold/40 px-4 py-1.5 text-[11px] font-bold uppercase tracking-[0.08em] text-text-primary">
        Coming Soon
      </span>
    </div>
  );
}
