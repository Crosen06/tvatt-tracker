import { useState } from "react";
import { api } from "../lib/api.js";
import { reload, toast } from "../lib/store.js";
import KioskInput from "./KioskInput.jsx";
import { CATEGORIES, capitalize } from "./labels.js";
import Sheet from "./Sheet.jsx";

// Create an item. onCreated(item) is called with the new item (used by the scan flow).
export default function NewItemSheet({ onClose, onCreated, initialName = "", initialCategory = "Skafferi", status = "in_stock" }) {
  const [name, setName] = useState(initialName);
  const [category, setCategory] = useState(initialCategory);
  const [busy, setBusy] = useState(false);

  async function save() {
    const clean = capitalize(name.trim());
    if (!clean) return toast("Skriv vad varan heter.");
    setBusy(true);
    try {
      const item = await api.post("/api/items", { name: clean, category, status });
      reload("items");
      onCreated?.(item);
      onClose();
    } catch (e) {
      toast(e.message);
      setBusy(false);
    }
  }

  return (
    <Sheet
      title="Ny vara"
      full
      onClose={onClose}
      actions={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Avbryt</button>
          <button className="btn btn-primary" onClick={save} disabled={busy}>Spara vara</button>
        </>
      }
    >
      <div className="cat-choices" role="radiogroup" aria-label="Kategori">
        {CATEGORIES.map((c) => (
          <button key={c} className="option" role="radio" aria-checked={category === c} onClick={() => setCategory(c)}>
            {c}
          </button>
        ))}
      </div>
      <KioskInput value={name} onChange={setName} onSubmit={save} placeholder="Vad heter varan?" label="Namn på varan" keyboardOpen autoFocus maxLength={40} />
    </Sheet>
  );
}
