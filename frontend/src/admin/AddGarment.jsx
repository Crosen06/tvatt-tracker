import { useState } from "react";
import GarmentForm from "../components/GarmentForm.jsx";
import { api } from "../lib/api.js";
import { DEFAULT_TAGS, genitive } from "../lib/labels.js";
import { navigate } from "../lib/router.js";
import { reload, useStore } from "../lib/store.js";
import AdminHeader from "./AdminHeader.jsx";

const KEY = "tvatt.person";
function rememberedPerson(people) {
  let id = null;
  try {
    id = Number(localStorage.getItem(KEY));
  } catch {
    /* storage unavailable */
  }
  return people.some((p) => p.id === id) ? id : people[0]?.id;
}

export default function AddGarment() {
  const { people } = useStore();
  const [round, setRound] = useState(0);
  const [saved, setSaved] = useState(null);

  async function save(values, blob) {
    const fd = new FormData();
    for (const [k, v] of Object.entries(values)) fd.append(k, String(v));
    fd.append("photo", blob, "photo.jpg");
    const g = await api.upload("/api/garments", fd);
    try {
      localStorage.setItem(KEY, String(values.person_id));
    } catch {
      /* ignore */
    }
    reload("garments");
    setSaved(g);
  }

  if (saved) {
    const person = people.find((p) => p.id === saved.person_id);
    return (
      <div className="admin">
        <AdminHeader title="Sparat" />
        <div className="card" style={{ justifyItems: "center", textAlign: "center" }}>
          {saved.thumb_url && <img src={saved.thumb_url} alt="" style={{ width: 160, height: 160, objectFit: "cover", borderRadius: 16 }} />}
          <p>
            <b>{saved.name}</b> finns nu under {person?.name}.
          </p>
          <button className="btn btn-primary btn-block" onClick={() => { setSaved(null); setRound((r) => r + 1); }}>
            Lägg till ett plagg till
          </button>
          <button className="btn btn-block" onClick={() => navigate(`/p/${saved.person_id}`)}>
            Visa {genitive(person?.name)} plagg
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="admin">
      <AdminHeader title="Lägg till plagg" />
      <GarmentForm
        key={round}
        initial={{ ...DEFAULT_TAGS, name: "", person_id: rememberedPerson(people) }}
        photoRequired
        submitLabel="Spara plagg"
        onSubmit={save}
      />
    </div>
  );
}
