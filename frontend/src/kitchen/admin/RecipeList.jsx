import AdminHeader from "../../admin/AdminHeader.jsx";
import { navigate } from "../../lib/router.js";
import { useStore } from "../../lib/store.js";

export default function RecipeList() {
  const { recipes } = useStore();
  const sorted = [...recipes].sort((a, b) => a.title.localeCompare(b.title, "sv"));
  return (
    <div className="admin">
      <AdminHeader title="Recept" />
      <div className="row">
        <button className="btn btn-primary grow" onClick={() => navigate("/admin/recept/ny")}>Nytt recept</button>
        <button className="btn grow" onClick={() => navigate("/admin/recept/import")}>Importera från länk</button>
      </div>
      {sorted.length === 0 && <p className="hint">Inga recept än. Skriv in ett eget eller klistra in en länk från ICA eller en annan receptsajt.</p>}
      <div className="list">
        {sorted.map((r) => (
          <button key={r.id} className="list-row" onClick={() => navigate(`/admin/recept/${r.id}`)}>
            <span className="thumb">{r.thumb_url && <img src={r.thumb_url} alt="" loading="lazy" />}</span>
            <span className="list-row-main">
              <span className="list-row-name">{r.title}</span>
              <span className="hint">{r.source === "ica" ? "ICA" : r.source === "web" ? "Från webben" : "Eget recept"}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
