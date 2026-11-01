import { useState } from "react";
import { api } from "../lib/api.js";
import { reload, toast, useStore } from "../lib/store.js";
import { STATUSES } from "./labels.js";
import Sheet from "./Sheet.jsx";

export default function CookedSheet({ recipe, onClose }) {
  const { items } = useStore();
  const used = [...new Set(recipe.ingredients.filter((i) => i.item_id && i.state !== "ignored").map((i) => i.item_id))]
    .map((id) => items.find((x) => x.id === id))
    .filter((x) => x && !x.staple);
  const [choice, setChoice] = useState(() => Object.fromEntries(used.map((i) => [i.id, i.status])));
  const [busy, setBusy] = useState(false);

  async function done() {
    setBusy(true);
    const updates = used.filter((i) => choice[i.id] !== i.status).map((i) => ({ item_id: i.id, status: choice[i.id] }));
    try {
      await api.post(`/api/recipes/${recipe.id}/cooked`, { updates });
      reload("recipes", "items", "shopping");
      const listed = updates.filter((u) => u.status === "out").map((u) => used.find((i) => i.id === u.item_id).name);
      toast(listed.length ? `${listed.join(", ")} lades på inköpslistan` : "Smaklig måltid!", "ok");
      onClose();
    } catch (e) {
      toast(e.message);
      setBusy(false);
    }
  }

  return (
    <Sheet
      title="Vad tog slut?"
      onClose={onClose}
      actions={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Avbryt</button>
          <button className="btn btn-primary" onClick={done} disabled={busy}>Klart</button>
        </>
      }
    >
      {used.length === 0 && <p className="hint">Receptet använder inga varor från skafferiet.</p>}
      <div className="cooked-list">
        {used.map((i) => (
          <div key={i.id} className="cooked-row">
            <span className="grow">{i.name}</span>
            <div className="segmented" role="radiogroup" aria-label={i.name}>
              {STATUSES.map((s) => (
                <button key={s.value} role="radio" aria-checked={choice[i.id] === s.value} aria-selected={choice[i.id] === s.value} onClick={() => setChoice({ ...choice, [i.id]: s.value })}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Sheet>
  );
}
