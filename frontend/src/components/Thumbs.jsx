export default function Thumbs({ items, people, max = 10 }) {
  const colorOf = (pid) => people.find((p) => p.id === pid)?.color;
  const shown = items.slice(0, max);
  const rest = items.length - shown.length;
  return (
    <div className="thumbs">
      {shown.map((g) => (
        <span className="thumb" key={g.id} title={g.name}>
          {g.thumb_url && <img src={g.thumb_url} alt={g.name} loading="lazy" draggable="false" />}
          <span className="thumb-dot" style={{ background: colorOf(g.person_id) }} />
        </span>
      ))}
      {rest > 0 && <span className="thumb thumb-more">+{rest}</span>}
    </div>
  );
}
