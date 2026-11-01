import { useState } from "react";
import { useStore } from "../lib/store.js";
import KioskInput from "./KioskInput.jsx";
import Sheet from "./Sheet.jsx";

const fold = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

// Search the pantry and pick an item.
export default function ItemPickerSheet({ title, onPick, onClose }) {
  const { items } = useStore();
  const [q, setQ] = useState("");
  const query = fold(q.trim());
  const hits = query ? items.filter((i) => fold(i.name).includes(query)).slice(0, 8) : [];
  return (
    <Sheet title={title} full onClose={onClose} actions={<button className="btn btn-ghost" onClick={onClose}>Avbryt</button>}>
      <div className="link-choices">
        {hits.map((i) => (
          <button key={i.id} className="freq" onClick={() => onPick(i)}>{i.name}</button>
        ))}
        {query && hits.length === 0 && <p className="hint">Ingen vara heter så.</p>}
        {!query && <p className="hint">Skriv början på varans namn.</p>}
      </div>
      <KioskInput value={q} onChange={setQ} placeholder="Sök vara" keyboardOpen />
    </Sheet>
  );
}
