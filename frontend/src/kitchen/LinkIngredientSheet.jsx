import { useState } from "react";
import { api } from "../lib/api.js";
import { toast, useStore } from "../lib/store.js";
import { isKiosk } from "../lib/router.js";
import KioskInput from "./KioskInput.jsx";
import { capitalize } from "./labels.js";
import Sheet from "./Sheet.jsx";

const fold = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

export default function LinkIngredientSheet({ recipeId, ingredient, onClose, onDone }) {
  const { items } = useStore();
  const [q, setQ] = useState("");
  const words = fold(ingredient.name).split(" ").filter((w) => w.length > 2);
  const query = fold(q.trim());
  const candidates = items
    .filter((i) => (query ? fold(i.name).includes(query) : words.some((w) => fold(i.name).includes(w) || w.includes(fold(i.name)))))
    .slice(0, isKiosk ? 8 : 12);
  const newName = capitalize((q.trim() || ingredient.name).slice(0, 40));
  const exists = items.some((i) => i.name.toLowerCase() === newName.toLowerCase());

  async function send(body) {
    try {
      onDone(await api.patch(`/api/recipes/${recipeId}/ingredients/${ingredient.id}`, body));
    } catch (e) {
      toast(e.message);
    }
  }

  async function createAndLink() {
    try {
      const item = await api.post("/api/items", { name: newName, category: "Skafferi", status: "out" });
      await send({ item_id: item.id });
    } catch (e) {
      toast(e.message);
    }
  }

  return (
    <Sheet
      title={`Koppla ”${ingredient.text}”`}
      full
      onClose={onClose}
      actions={<button className="btn btn-ghost" onClick={onClose}>Avbryt</button>}
    >
      <div className="link-choices">
        {candidates.map((i) => (
          <button key={i.id} className="freq" aria-pressed={ingredient.item_id === i.id} onClick={() => send({ item_id: i.id })}>
            {i.name}
          </button>
        ))}
        {newName && !exists && (
          <button className="btn" onClick={createAndLink}>Ny vara ”{newName}”</button>
        )}
        {ingredient.state === "ignored" ? (
          <button className="btn btn-ghost" onClick={() => send({ ignored: false })}>Räkna med raden igen</button>
        ) : (
          <button className="btn btn-ghost" onClick={() => send({ ignored: true })}>Ingen vara, räkna inte</button>
        )}
      </div>
      <KioskInput value={q} onChange={setQ} placeholder="Sök vara" keyboardOpen />
    </Sheet>
  );
}
