import { useEffect, useState } from "react";
import AdminHeader from "../../admin/AdminHeader.jsx";
import { api } from "../../lib/api.js";
import { navigate } from "../../lib/router.js";
import { reload, toast } from "../../lib/store.js";
import { CATEGORIES } from "../labels.js";

export default function ItemEdit({ id }) {
  const [item, setItem] = useState(null);
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const it = await api.get(`/api/items/${id}`);
      setItem(it);
      setForm({ name: it.name, category: it.category, staple: it.staple, counted: it.counted, words: it.match_words.join(", ") });
    } catch (e) {
      toast(e.message);
    }
  }
  useEffect(() => {
    load();
  }, [id]);

  if (!form) return <div className="admin"><AdminHeader title="Vara" back="/admin/varor" /></div>;
  const set = (k) => (v) => setForm({ ...form, [k]: v });

  async function save() {
    setBusy(true);
    try {
      await api.patch(`/api/items/${id}`, {
        name: form.name, category: form.category, staple: form.staple, counted: form.counted,
        match_words: form.words.split(",").map((w) => w.trim()).filter(Boolean),
      });
      reload("items");
      toast("Sparat.", "ok");
      await load();
    } catch (e) {
      toast(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    if (!window.confirm(`Ta bort ${item.name}? Streckkoder och receptkopplingar till varan försvinner.`)) return;
    try {
      await api.del(`/api/items/${id}`);
      reload("items", "shopping");
      navigate("/admin/varor");
    } catch (e) {
      toast(e.message);
    }
  }

  async function removeCode(code) {
    try {
      await api.del(`/api/barcodes/${code}`);
      await load();
    } catch (e) {
      toast(e.message);
    }
  }

  return (
    <div className="admin admin-form">
      <AdminHeader title={item.name} back="/admin/varor" />
      <label className="field">
        <span className="field-label">Namn</span>
        <input className="input" value={form.name} maxLength={40} onChange={(e) => set("name")(e.target.value)} />
      </label>
      <div className="field">
        <span className="field-label">Kategori</span>
        <div className="options" role="radiogroup" aria-label="Kategori">
          {CATEGORIES.map((c) => (
            <button key={c} className="option" role="radio" aria-checked={form.category === c} onClick={() => set("category")(c)}>
              {c}
            </button>
          ))}
        </div>
      </div>
      <label className="toggle">
        <input type="checkbox" checked={form.staple} onChange={(e) => set("staple")(e.target.checked)} />
        <span>Basvara</span>
      </label>
      <p className="hint">Basvaror som salt och olja räknas alltid som hemma när appen föreslår recept.</p>
      <label className="toggle">
        <input type="checkbox" checked={form.counted} onChange={(e) => set("counted")(e.target.checked)} />
        <span>Räkna antal</span>
      </label>
      <p className="hint">För saker man har flera av, till exempel burkar eller ägg.</p>
      <label className="field">
        <span className="field-label">Andra namn i recept</span>
        <input className="input" value={form.words} placeholder="Till exempel: vispgrädde, matlagningsgrädde" onChange={(e) => set("words")(e.target.value)} />
        <span className="hint">Kommaseparerat. Hjälper appen att känna igen varan i recept.</span>
      </label>
      {item.barcodes?.length > 0 && (
        <div className="field">
          <span className="field-label">Streckkoder</span>
          {item.barcodes.map((b) => (
            <div key={b.code} className="row">
              <span className="grow">
                {b.code}
                {b.product_name && <span className="hint"> · {b.product_name}</span>}
              </span>
              <button className="btn btn-ghost" onClick={() => removeCode(b.code)}>Ta bort</button>
            </div>
          ))}
        </div>
      )}
      <div className="row">
        <button className="btn btn-primary grow" onClick={save} disabled={busy}>Spara</button>
        <button className="btn btn-danger" onClick={archive}>Ta bort vara</button>
      </div>
    </div>
  );
}
