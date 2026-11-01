import { useEffect, useRef, useState } from "react";
import AdminHeader from "../../admin/AdminHeader.jsx";
import EmptyState from "../../components/EmptyState.jsx";
import { api } from "../../lib/api.js";
import { plural } from "../../lib/labels.js";
import { navigate } from "../../lib/router.js";
import { toast, useStore } from "../../lib/store.js";

const SOURCE = { learn: "Lär in", scan: "Streckkod", confirm: "Bekräftad" };
const UNDO_MS = 6000;

// Items with learned pictures (phone: Hantera → Inlärda bilder).
export function VisionItemList() {
  const { vision, visionStatus } = useStore();
  const [rows, setRows] = useState(null);
  useEffect(() => {
    api.get("/api/vision/items").then(setRows, (e) => toast(e.message));
  }, [vision.seq, visionStatus.images]);

  return (
    <div className="admin">
      <AdminHeader title="Inlärda bilder" />
      {!visionStatus.available && visionStatus.message && <p className="vision-help">{visionStatus.message}</p>}
      {rows && rows.length === 0 && (
        <EmptyState title="Inga inlärda bilder än">Tryck på Lär in i Skanna på skärmen i köket, eller skanna varor med streckkod.</EmptyState>
      )}
      <section className="list">
        {(rows || []).map((r) => (
          <button key={r.item_id} className="list-row" onClick={() => navigate(`/admin/bilder/${r.item_id}`)}>
            <span className="thumb"><img src={r.cover} alt="" /></span>
            <span className="list-row-main">
              <span className="list-row-name">{r.name}</span>
              <span className="chips"><span className="chip">{plural(r.count, "bild", "bilder")}</span></span>
            </span>
          </button>
        ))}
      </section>
    </div>
  );
}

// One item's learned pictures; tap a picture to remove it (with Ångra).
export function VisionItemImages({ id }) {
  const { items, vision, visionStatus } = useStore();
  const item = items.find((i) => i.id === id);
  const [images, setImages] = useState(null);
  const [hidden, setHidden] = useState(() => new Set());
  const timers = useRef(new Map());

  function load() {
    api.get(`/api/items/${id}/images`).then(setImages, (e) => toast(e.message));
  }
  useEffect(load, [id, vision.seq, visionStatus.images]);
  // Deletes wait for the Ångra window; leaving the page still deletes them.
  useEffect(() => () => timers.current.forEach((fn, key) => {
    clearTimeout(key);
    fn();
  }), []);

  function remove(img) {
    setHidden((h) => new Set(h).add(img.id));
    const doDelete = () => api.del(`/api/vision/images/${img.id}`).catch(() => {});
    const t = setTimeout(() => {
      timers.current.delete(t);
      doDelete();
    }, UNDO_MS);
    timers.current.set(t, doDelete);
    toast("Bilden togs bort", "ok", {
      label: "Ångra",
      run: () => {
        clearTimeout(t);
        timers.current.delete(t);
        setHidden((h) => {
          const n = new Set(h);
          n.delete(img.id);
          return n;
        });
      },
    });
  }

  async function removeAll() {
    if (!window.confirm(`Ta bort alla inlärda bilder av ${item?.name || "varan"}? Appen känner inte igen den på bilden efter det.`)) return;
    try {
      await api.del(`/api/items/${id}/images`);
      navigate("/admin/bilder");
    } catch (e) {
      toast(e.message);
    }
  }

  const shown = (images || []).filter((i) => !hidden.has(i.id));
  return (
    <div className="admin">
      <AdminHeader title={item ? item.name : "Inlärda bilder"} back="/admin/bilder" />
      {images && shown.length === 0 && <EmptyState title="Inga bilder">Den här varan har inga inlärda bilder.</EmptyState>}
      {shown.length > 0 && (
        <>
          <p className="vision-help">{plural(shown.length, "bild", "bilder")}. Tryck på en bild som visar fel vara för att ta bort den.</p>
          <div className="vision-grid">
            {shown.map((img) => (
              <button key={img.id} className="vision-pic" onClick={() => remove(img)} aria-label="Ta bort bilden">
                <img src={img.url} alt="" loading="lazy" />
                <span>{SOURCE[img.source] || img.source}</span>
              </button>
            ))}
          </div>
          <div className="row">
            <button className="btn btn-danger" onClick={removeAll}>Ta bort alla</button>
          </div>
        </>
      )}
    </div>
  );
}
