export default function PlaceholderTab({ Icon, title, description }) {
  return (
    <div className="flex min-h-[320px] flex-col items-center justify-center rounded-[14px] bg-card p-12 text-center shadow-card">
      {Icon && <Icon className="mb-4 h-10 w-10 text-text-primary" strokeWidth={1.5} />}
      <h2 className="mb-2 text-xl font-bold text-text-primary">{title}</h2>
      <p className="max-w-[380px] text-sm leading-relaxed text-text-muted">{description}</p>
      <span className="mt-4 inline-block rounded-full bg-accent-gold px-3.5 py-[5px] text-xs font-bold uppercase tracking-wider text-text-primary">
        Coming Soon
      </span>
    </div>
  );
}
