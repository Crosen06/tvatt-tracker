import { useState } from "react";
import EmptyState from "../components/EmptyState.jsx";
import { CameraIcon } from "../components/Icons.jsx";
import { careLabel, colorInfo, tempLabel } from "../lib/labels.js";
import { navigate } from "../lib/router.js";
import { useStore } from "../lib/store.js";
import AdminHeader from "./AdminHeader.jsx";

export default function GarmentList() {
  const { people, garments } = useStore();
  const [q, setQ] = useState("");
  const match = (g) => g.name.toLowerCase().includes(q.trim().toLowerCase());

  return (
    <div className="admin">
      <AdminHeader title="Alla plagg" />
      {garments.length === 0 ? (
        <EmptyState
          icon={<CameraIcon width={40} height={40} />}
          title="Inga plagg än"
          action={<button className="btn btn-primary" onClick={() => navigate("/admin/ny")}>Lägg till plagg</button>}
        >
          Fota ett plagg och tagga hur det ska tvättas.
        </EmptyState>
      ) : (
        <>
          <input className="input" type="search" placeholder="Sök plagg" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Sök plagg" />
          {people.map((p) => {
            const mine = garments.filter((g) => g.person_id === p.id && match(g));
            if (!mine.length) return null;
            return (
              <section key={p.id} className="list">
                <h2 className="section-title">
                  <span className="swatch" style={{ background: p.color }} />
                  {p.name}
                </h2>
                {mine.map((g) => (
                  <button key={g.id} className="list-row" onClick={() => navigate(`/admin/plagg/${g.id}`)}>
                    <span className="thumb">{g.thumb_url && <img src={g.thumb_url} alt="" loading="lazy" />}</span>
                    <span className="list-row-main">
                      <span className="list-row-name">{g.name}</span>
                      <span className="chips">
                        <span className="chip">
                          <span className="swatch" style={{ background: colorInfo(g.color).swatch }} />
                          {colorInfo(g.color).label}
                        </span>
                        <span className="chip">{tempLabel(g.max_temp)}</span>
                        <span className="chip">{careLabel(g.care)}</span>
                      </span>
                    </span>
                  </button>
                ))}
              </section>
            );
          })}
        </>
      )}
    </div>
  );
}
