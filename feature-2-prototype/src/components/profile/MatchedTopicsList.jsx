export function MatchedTopicsList({ topics }) {
  return (
    <section className="panel">
      <p className="eyebrow">Matched topics</p>
      <ul className="topic-list">
        {topics.map((topic) => (
          <li key={topic}>{topic}</li>
        ))}
      </ul>
    </section>
  );
}
