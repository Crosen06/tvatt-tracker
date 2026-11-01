import { useState } from "react";
import TagPicker from "../components/TagPicker.jsx";
import { api } from "../lib/api.js";
import { CARES, TEMPS, tempLabel } from "../lib/labels.js";
import { reload, toast, useStore } from "../lib/store.js";
import AdminHeader from "./AdminHeader.jsx";

function ProgramEditor({ program, onDone }) {
  const [v, setV] = useState(program ?? { name: "", duration_min: 60, temp: 40, care: "normal" });
  const [confirm, setConfirm] = useState(false);
  const set = (k) => (x) => setV((s) => ({ ...s, [k]: x }));
  const dirty = !program || ["name", "duration_min", "temp", "care"].some((k) => v[k] !== program[k]);

  async function save() {
    const body = { name: v.name.trim(), duration_min: Number(v.duration_min), temp: v.temp, care: v.care };
    if (!body.name) return toast("Ge programmet ett namn.");
    if (!(body.duration_min >= 1 && body.duration_min <= 600)) return toast("Längden ska vara mellan 1 och 600 minuter.");
    try {
      if (program) await api.patch(`/api/programs/${program.id}`, body);
      else await api.post("/api/programs", body);
      reload("programs");
      toast(program ? "Programmet är sparat." : "Programmet är tillagt.", "ok");
      onDone?.();
    } catch (e) {
      toast(e.message);
    }
  }

  async function remove() {
    try {
      await api.del(`/api/programs/${program.id}`);
      reload("programs");
    } catch (e) {
      toast(e.message);
    }
  }

  return (
    <div className="card">
      <div className="row">
        <label className="field grow">
          <span className="field-label">Namn</span>
          <input className="input" value={v.name} onChange={(e) => set("name")(e.target.value)} maxLength={40} placeholder="Till exempel Bomull 40°" />
        </label>
        <label className="field" style={{ width: 120 }}>
          <span className="field-label">Minuter</span>
          <input className="input" type="number" inputMode="numeric" min={1} max={600} value={v.duration_min} onChange={(e) => set("duration_min")(e.target.value)} />
        </label>
      </div>
      <TagPicker label="Temperatur" options={TEMPS.map((t) => ({ value: t, label: tempLabel(t) }))} value={v.temp} onChange={set("temp")} />
      <TagPicker label="Passar för" options={CARES} value={v.care} onChange={set("care")} />
      <div className="row">
        {dirty && (
          <button className="btn btn-primary" onClick={save}>
            {program ? "Spara" : "Lägg till program"}
          </button>
        )}
        {program &&
          (confirm ? (
            <>
              <button className="btn btn-danger" onClick={remove}>Ta bort {program.name}</button>
              <button className="btn btn-ghost" onClick={() => setConfirm(false)}>Behåll</button>
            </>
          ) : (
            <button className="btn btn-ghost" onClick={() => setConfirm(true)}>Ta bort</button>
          ))}
        {!program && (
          <button className="btn btn-ghost" onClick={onDone}>Avbryt</button>
        )}
      </div>
    </div>
  );
}

export default function Programs() {
  const { programs } = useStore();
  const [adding, setAdding] = useState(false);
  return (
    <div className="admin">
      <AdminHeader title="Tvättprogram" />
      <p className="hint">Ställ in samma tider som er tvättmaskin visar, så stämmer nedräkningen.</p>
      {programs.map((p) => (
        <ProgramEditor key={`${p.id}-${p.name}-${p.duration_min}-${p.temp}-${p.care}`} program={p} />
      ))}
      {adding ? (
        <ProgramEditor onDone={() => setAdding(false)} />
      ) : (
        <button className="btn btn-block" onClick={() => setAdding(true)}>Nytt program</button>
      )}
    </div>
  );
}
