import { useState } from "react";
import EmptyState from "../components/EmptyState.jsx";
import GarmentForm from "../components/GarmentForm.jsx";
import { api } from "../lib/api.js";
import { navigate } from "../lib/router.js";
import { reload, toast, useStore } from "../lib/store.js";
import AdminHeader from "./AdminHeader.jsx";

const FIELDS = ["person_id", "name", "max_temp", "color", "max_spin", "care", "tumble_dry"];

export default function GarmentEdit({ id }) {
  const { garments } = useStore();
  const [confirm, setConfirm] = useState(false);
  const g = garments.find((x) => x.id === id);

  if (!g) {
    return (
      <div className="admin">
        <AdminHeader title="Plagg" back="/admin/plagg" />
        <EmptyState title="Plagget finns inte längre">Det kan ha tagits bort från en annan skärm.</EmptyState>
      </div>
    );
  }

  async function save(values, blob) {
    await api.patch(`/api/garments/${g.id}`, values);
    if (blob) {
      const fd = new FormData();
      fd.append("photo", blob, "photo.jpg");
      await api.upload(`/api/garments/${g.id}/photo`, fd);
    }
    reload("garments");
    toast("Ändringarna är sparade.", "ok");
    navigate("/admin/plagg");
  }

  async function remove() {
    try {
      await api.del(`/api/garments/${g.id}`);
      reload("garments");
      toast(`${g.name} är borttaget.`, "ok");
      navigate("/admin/plagg");
    } catch (e) {
      toast(e.message);
    }
  }

  const initial = Object.fromEntries(FIELDS.map((k) => [k, g[k]]));
  return (
    <div className="admin">
      <AdminHeader title={g.name} back="/admin/plagg" />
      <GarmentForm key={g.id} initial={initial} photoUrl={g.photo_url} submitLabel="Spara ändringar" onSubmit={save}>
        <div className="card">
          {confirm ? (
            <div className="row">
              <span className="grow">Ta bort {g.name} för gott?</span>
              <button type="button" className="btn btn-danger" onClick={remove}>
                Ta bort
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setConfirm(false)}>
                Behåll
              </button>
            </div>
          ) : (
            <button type="button" className="btn btn-danger" onClick={() => setConfirm(true)} disabled={g.in_wash}>
              {g.in_wash ? "Ligger i maskinen just nu" : "Ta bort plagg"}
            </button>
          )}
        </div>
      </GarmentForm>
    </div>
  );
}
