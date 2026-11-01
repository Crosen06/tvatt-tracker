import { useState } from "react";
import { api } from "../lib/api.js";
import { reload, toast } from "../lib/store.js";
import Sheet from "./Sheet.jsx";

export default function UnpackSheet({ entries, onClose }) {
  const [checked, setChecked] = useState(() => new Set(entries.map((e) => e.id)));
  const [busy, setBusy] = useState(false);

  function flip(id) {
    const next = new Set(checked);
    next.has(id) ? next.delete(id) : next.add(id);
    setChecked(next);
  }

  async function done() {
    setBusy(true);
    try {
      await api.post("/api/shopping/unpack", { entry_ids: [...checked] });
      reload("items", "shopping");
      toast("Uppackat. Varorna finns nu i skafferiet.", "ok");
      onClose();
    } catch (e) {
      toast(e.message);
      setBusy(false);
    }
  }

  return (
    <Sheet
      title="Packa upp"
      onClose={onClose}
      actions={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Avbryt</button>
          <button className="btn btn-primary" onClick={done} disabled={busy || checked.size === 0}>Det här köptes</button>
        </>
      }
    >
      <p className="hint">Bocka ur det ni inte fick med er. Resten markeras som hemma och tas bort från listan.</p>
      <div className="unpack-list">
        {entries.map((e) => (
          <label key={e.id} className="unpack-row">
            <input type="checkbox" checked={checked.has(e.id)} onChange={() => flip(e.id)} />
            <span>{e.text}</span>
          </label>
        ))}
      </div>
    </Sheet>
  );
}
