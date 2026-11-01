import { statusLabel } from "./labels.js";

export default function ItemTile({ item, onClick }) {
  return (
    <button className={`item-tile is-${item.status}`} onClick={() => onClick(item)} aria-label={`${item.name}, ${statusLabel(item)}`}>
      <span className="item-tile-name">{item.name}</span>
      <span className="item-tile-meta">
        <span className="status-dot" />
        {statusLabel(item)}
        {item.on_list && <span className="item-tile-list" title="På inköpslistan">· på listan</span>}
      </span>
    </button>
  );
}
