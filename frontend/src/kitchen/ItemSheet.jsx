import { useStore } from "../lib/store.js";
import { toggleOnList, updateItem } from "./actions.js";
import { STATUSES } from "./labels.js";
import Sheet from "./Sheet.jsx";

export default function ItemSheet({ itemId, onClose }) {
  const { items } = useStore();
  const item = items.find((i) => i.id === itemId);
  if (!item) return null;

  async function pick(status) {
    onClose();
    await updateItem(item, { status });
  }

  return (
    <Sheet
      title={item.name}
      onClose={onClose}
      actions={<button className="btn btn-ghost" onClick={onClose}>Stäng</button>}
    >
      <p className="hint">
        {item.category}
        {item.staple && " · basvara, räknas alltid som hemma i recept"}
      </p>
      <div className="status-choices">
        {STATUSES.map((s) => (
          <button key={s.value} className={`status-choice is-${s.value}`} aria-pressed={item.status === s.value} onClick={() => pick(s.value)}>
            <span className="status-dot" />
            {s.label}
          </button>
        ))}
      </div>
      {item.counted && (
        <div className="counter" aria-live="polite">
          <button className="btn" aria-label="Minska antal" disabled={!item.count} onClick={() => updateItem(item, { count: Math.max(0, (item.count || 0) - 1) })}>
            −
          </button>
          <span className="counter-value">{item.count || 0} st</span>
          <button className="btn" aria-label="Öka antal" onClick={() => updateItem(item, { count: (item.count || 0) + 1 })}>
            +
          </button>
        </div>
      )}
      <button className="btn btn-block" onClick={() => toggleOnList(item)}>
        {item.on_list ? "Ta bort från inköpslistan" : "På inköpslistan"}
      </button>
    </Sheet>
  );
}
