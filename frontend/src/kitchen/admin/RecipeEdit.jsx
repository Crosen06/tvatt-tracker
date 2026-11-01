import { useEffect, useState } from "react";
import AdminHeader from "../../admin/AdminHeader.jsx";
import { api } from "../../lib/api.js";
import { resizeImage } from "../../lib/resizeImage.js";
import { navigate } from "../../lib/router.js";
import { reload, toast } from "../../lib/store.js";

const EMPTY = { title: "", servings: "4", minutes: "", ingredients: "", steps: "" };

// id undefined = new recipe.
export default function RecipeEdit({ id }) {
  const [form, setForm] = useState(id ? null : EMPTY);
  const [photo, setPhoto] = useState(null);
  const [thumb, setThumb] = useState(null);
  const [busy, setBusy] = useState(false);
  const [preparing, setPreparing] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.get(`/api/recipes/${id}`).then(
      (r) => {
        setForm({
          title: r.title, servings: r.servings ? String(r.servings) : "", minutes: r.minutes ? String(r.minutes) : "",
          ingredients: r.ingredients.map((i) => i.text).join("\n"), steps: r.steps.join("\n"),
        });
        setThumb(r.thumb_url);
      },
      (e) => toast(e.message),
    );
  }, [id]);

  if (!form) return <div className="admin"><AdminHeader title="Recept" back="/admin/recept" /></div>;
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function pick(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setPreparing(true);
    try {
      const blob = await resizeImage(file);
      setPhoto(blob);
      setThumb(URL.createObjectURL(blob));
    } catch {
      toast("Bildformatet stöds inte.");
    } finally {
      setPreparing(false);
    }
  }

  async function save() {
    if (!form.title.trim()) return toast("Skriv vad receptet heter.");
    setBusy(true);
    try {
      if (id) {
        await api.patch(`/api/recipes/${id}`, { ...form, servings: form.servings || null, minutes: form.minutes || null });
        if (photo) {
          const fd = new FormData();
          fd.append("photo", photo, "photo.jpg");
          await api.upload(`/api/recipes/${id}/photo`, fd);
        }
        toast("Sparat.", "ok");
      } else {
        const fd = new FormData();
        for (const [k, v] of Object.entries(form)) fd.append(k, v);
        if (photo) fd.append("photo", photo, "photo.jpg");
        const r = await api.upload("/api/recipes", fd);
        toast("Receptet är sparat.", "ok");
        navigate(`/admin/recept/${r.id}`);
      }
      reload("recipes");
    } catch (e) {
      toast(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Ta bort ${form.title}?`)) return;
    try {
      await api.del(`/api/recipes/${id}`);
      reload("recipes");
      navigate("/admin/recept");
    } catch (e) {
      toast(e.message);
    }
  }

  return (
    <div className="admin admin-form">
      <AdminHeader title={id ? "Ändra recept" : "Nytt recept"} back="/admin/recept" />
      <label className="field">
        <span className="field-label">Titel</span>
        <input className="input" value={form.title} maxLength={120} onChange={set("title")} placeholder="Till exempel Pasta carbonara" />
      </label>
      <div className="row">
        <label className="field grow">
          <span className="field-label">Portioner</span>
          <input className="input" inputMode="numeric" value={form.servings} onChange={set("servings")} />
        </label>
        <label className="field grow">
          <span className="field-label">Minuter</span>
          <input className="input" inputMode="numeric" value={form.minutes} onChange={set("minutes")} />
        </label>
      </div>
      <label className="field">
        <span className="field-label">Ingredienser</span>
        <textarea className="input textarea" rows={8} value={form.ingredients} onChange={set("ingredients")} placeholder={"En per rad, till exempel:\n400 g pasta\n2 dl grädde"} />
      </label>
      <label className="field">
        <span className="field-label">Gör så här</span>
        <textarea className="input textarea" rows={8} value={form.steps} onChange={set("steps")} placeholder="Ett steg per rad" />
      </label>
      <label className={`photo-pick${thumb ? " has-photo" : ""}`} style={{ aspectRatio: "16 / 9" }}>
        {thumb && <img src={thumb} alt="" />}
        <input type="file" accept="image/*" onChange={pick} aria-label="Foto" />
        <span className="photo-pick-label">{preparing ? "Förbereder bilden…" : thumb ? "Byt foto" : "Lägg till foto (valfritt)"}</span>
      </label>
      <div className="row">
        <button className="btn btn-primary grow" onClick={save} disabled={busy || preparing}>{id ? "Spara" : "Spara recept"}</button>
        {id && <button className="btn" onClick={() => navigate(`/kok/recept/${id}`)}>Visa</button>}
        {id && <button className="btn btn-danger" onClick={remove}>Ta bort</button>}
      </div>
    </div>
  );
}
