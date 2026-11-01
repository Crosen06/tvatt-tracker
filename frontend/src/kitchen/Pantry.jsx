import { useState } from "react";
import { PlusIcon } from "../components/Icons.jsx";
import { useStore } from "../lib/store.js";
import ItemSheet from "./ItemSheet.jsx";
import ItemTile from "./ItemTile.jsx";
import { CATEGORIES } from "./labels.js";
import NewItemSheet from "./NewItemSheet.jsx";

const FILTERS = [
  { value: "all", label: "Alla", test: () => true },
  { value: "home", label: "Hemma", test: (i) => i.status !== "out" },
  { value: "low", label: "Snart slut", test: (i) => i.status === "low" },
  { value: "out", label: "Slut", test: (i) => i.status === "out" },
];

export default function Pantry() {
  const { items } = useStore();
  const [filter, setFilter] = useState("all");
  const [openId, setOpenId] = useState(null);
  const [adding, setAdding] = useState(false);
  const f = FILTERS.find((x) => x.value === filter);
  const shown = items.filter(f.test);

  return (
    <section className="pantry">
      <div className="pantry-bar">
        <div className="segmented" role="tablist" aria-label="Visa">
          {FILTERS.map((x) => (
            <button key={x.value} role="tab" aria-selected={filter === x.value} onClick={() => setFilter(x.value)}>
              {x.label} <span className="count">{items.filter(x.test).length}</span>
            </button>
          ))}
        </div>
        <button className="btn" onClick={() => setAdding(true)}>
          <PlusIcon width={20} height={20} />
          Ny vara
        </button>
      </div>
      {shown.length === 0 && <p className="hint pantry-empty">Inga varor här.</p>}
      {CATEGORIES.map((cat) => {
        const inCat = shown.filter((i) => i.category === cat);
        if (!inCat.length) return null;
        return (
          <div key={cat} className="pantry-group">
            <h2 className="section-title">{cat}</h2>
            <div className="item-grid">
              {inCat.map((i) => (
                <ItemTile key={i.id} item={i} onClick={(x) => setOpenId(x.id)} />
              ))}
            </div>
          </div>
        );
      })}
      {openId && <ItemSheet itemId={openId} onClose={() => setOpenId(null)} />}
      {adding && <NewItemSheet onClose={() => setAdding(false)} />}
    </section>
  );
}
