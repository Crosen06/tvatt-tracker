import { useState } from "react";
import AdminHeader from "../../admin/AdminHeader.jsx";
import { navigate } from "../../lib/router.js";
import { useStore } from "../../lib/store.js";
import { CATEGORIES, statusLabel } from "../labels.js";
import NewItemSheet from "../NewItemSheet.jsx";

export default function ItemList() {
  const { items } = useStore();
  const [q, setQ] = useState("");
  const [adding, setAdding] = useState(false);
  const match = (i) => i.name.toLowerCase().includes(q.trim().toLowerCase());

  return (
    <div className="admin">
      <AdminHeader title="Varor" />
      <div className="row">
        <input className="input grow" type="search" placeholder="Sök vara" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Sök vara" />
        <button className="btn btn-primary" onClick={() => setAdding(true)}>Ny vara</button>
      </div>
      {CATEGORIES.map((cat) => {
        const inCat = items.filter((i) => i.category === cat && match(i));
        if (!inCat.length) return null;
        return (
          <section key={cat} className="list">
            <h2 className="section-title">{cat}</h2>
            {inCat.map((i) => (
              <button key={i.id} className="list-row" onClick={() => navigate(`/admin/varor/${i.id}`)}>
                <span className="list-row-main">
                  <span className="list-row-name">{i.name}</span>
                  <span className="chips">
                    <span className={`chip status-chip is-${i.status}`}>{statusLabel(i)}</span>
                    {i.staple && <span className="chip">Basvara</span>}
                  </span>
                </span>
              </button>
            ))}
          </section>
        );
      })}
      {adding && <NewItemSheet onClose={() => setAdding(false)} onCreated={(it) => navigate(`/admin/varor/${it.id}`)} status="out" />}
    </div>
  );
}
