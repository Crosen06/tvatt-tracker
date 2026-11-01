import { useState } from "react";
import { api } from "../lib/api.js";
import { reload, toast, useStore } from "../lib/store.js";
import AdminHeader from "./AdminHeader.jsx";

function PersonRow({ person }) {
  const [name, setName] = useState(person.name);
  const [color, setColor] = useState(person.color);
  const dirty = name.trim() !== person.name || color !== person.color;

  async function save() {
    if (!name.trim()) return toast("Namnet kan inte vara tomt.");
    try {
      await api.patch(`/api/people/${person.id}`, { name: name.trim(), color });
      reload("people");
      toast("Sparat.", "ok");
    } catch (e) {
      toast(e.message);
    }
  }

  return (
    <div className="row">
      <input className="input grow" value={name} onChange={(e) => setName(e.target.value)} maxLength={40} aria-label="Namn" />
      <input type="color" value={color} onChange={(e) => setColor(e.target.value)} aria-label={`Färg för ${person.name}`} style={{ width: 56, height: 52, border: 0, background: "none", padding: 0 }} />
      {dirty && <button className="btn btn-primary" onClick={save}>Spara</button>}
    </div>
  );
}

export default function Settings() {
  const { people, settings } = useStore();

  async function setSetting(patch) {
    try {
      await api.patch("/api/settings", patch);
      reload("settings");
    } catch (e) {
      toast(e.message);
    }
  }

  return (
    <div className="admin">
      <AdminHeader title="Inställningar" />
      <section className="card">
        <h2 className="section-title">Personer</h2>
        {people.map((p) => (
          <PersonRow key={`${p.id}-${p.name}-${p.color}`} person={p} />
        ))}
      </section>
      <section className="card">
        <h2 className="section-title">Tvättregler</h2>
        <label className="toggle">
          <input type="checkbox" checked={settings.split_hot} onChange={(e) => setSetting({ split_hot: e.target.checked })} />
          <span>
            Tvätta 60° och varmare för sig
            <span className="hint" style={{ display: "block" }}>
              Handdukar och lakan som tål 60° tvättas varmt i en egen tvätt i stället för att följa med en 40-gradstvätt.
            </span>
          </span>
        </label>
      </section>
      <section className="card">
        <h2 className="section-title">Kök</h2>
        <label className="toggle">
          <input type="checkbox" checked={settings.auto_list !== false} onChange={(e) => setSetting({ auto_list: e.target.checked })} />
          <span>
            Lägg på inköpslistan när något tar slut
            <span className="hint" style={{ display: "block" }}>
              När en vara markeras som slut hamnar den på inköpslistan av sig själv.
            </span>
          </span>
        </label>
      </section>
      <p className="hint">Appen nås från mobilen på http://tvatt.local när du är på hemmets wifi.</p>
    </div>
  );
}
