export default function PlaceholderTab({ icon, title, description }) {
  return (
    <div className="placeholder-tab">
      <div className="placeholder-icon">{icon}</div>
      <h2>{title}</h2>
      <p>{description}</p>
      <span className="coming-soon-badge">Coming Soon</span>
    </div>
  );
}
