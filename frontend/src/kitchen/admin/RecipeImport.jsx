import { useState } from "react";
import AdminHeader from "../../admin/AdminHeader.jsx";
import { api } from "../../lib/api.js";
import { navigate } from "../../lib/router.js";
import { reload, toast } from "../../lib/store.js";

export default function RecipeImport() {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function go() {
    const clean = url.trim();
    if (!/^https?:\/\//.test(clean)) return setError("Klistra in hela länken, den börjar med https://");
    setBusy(true);
    setError(null);
    try {
      const r = await api.post("/api/recipes/import", { url: clean });
      reload("recipes");
      toast(r.existing ? "Receptet fanns redan." : "Receptet är sparat.", "ok");
      navigate(`/admin/recept/${r.id}`);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }

  return (
    <div className="admin admin-form">
      <AdminHeader title="Importera recept" back="/admin/recept" />
      <p className="hint" style={{ display: "block" }}>
        Öppna receptet på ica.se (eller en annan receptsajt) i mobilen, kopiera länken och klistra in den här.
      </p>
      <label className="field">
        <span className="field-label">Länk till receptet</span>
        <input className="input" type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.ica.se/recept/…" />
      </label>
      {error && <p className="error">{error}</p>}
      <button className="btn btn-primary" onClick={go} disabled={busy || !url.trim()}>{busy ? "Hämtar…" : "Hämta recept"}</button>
    </div>
  );
}
