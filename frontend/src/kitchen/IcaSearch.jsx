import { useEffect, useRef, useState } from "react";
import { BackIcon } from "../components/Icons.jsx";
import { api } from "../lib/api.js";
import { navigate } from "../lib/router.js";
import { reload, toast, useStore } from "../lib/store.js";
import KioskInput from "./KioskInput.jsx";

const CHIP_ORDER = ["Kyl", "Frukt & grönt", "Frys", "Skafferi"];
const PARALLEL = 4;

function useChips(items) {
  return items
    .filter((i) => i.status !== "out" && !i.staple && CHIP_ORDER.includes(i.category))
    .sort((a, b) => CHIP_ORDER.indexOf(a.category) - CHIP_ORDER.indexOf(b.category))
    .slice(0, 12);
}

export default function IcaSearch() {
  const { items } = useStore();
  const chips = useChips(items);
  const [picked, setPicked] = useState([]);
  const [text, setText] = useState("");
  const [results, setResults] = useState(null);
  const [previews, setPreviews] = useState({});
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const generation = useRef(0);

  const query = [...picked, text.trim()].filter(Boolean).join(" ");

  async function search() {
    if (!query) return;
    const gen = ++generation.current;
    setBusy(true);
    setError(null);
    setResults(null);
    setPreviews({});
    try {
      const r = await api.get(`/api/ica/search?q=${encodeURIComponent(query)}`);
      if (gen !== generation.current) return;
      setResults(r.results);
      loadPreviews(r.results, gen);
    } catch (e) {
      if (gen === generation.current) setError(e.message);
    } finally {
      if (gen === generation.current) setBusy(false);
    }
  }

  // Fetch "har X av Y" for each hit, a few at a time so the Pi and ica.se aren't flooded.
  async function loadPreviews(list, gen) {
    const queue = [...list];
    async function worker() {
      while (queue.length && gen === generation.current) {
        const hit = queue.shift();
        try {
          const p = await api.get(`/api/ica/preview?url=${encodeURIComponent(hit.url)}`);
          if (gen === generation.current) setPreviews((s) => ({ ...s, [hit.url]: p }));
        } catch (e) {
          if (gen === generation.current) setPreviews((s) => ({ ...s, [hit.url]: { error: e.message } }));
        }
      }
    }
    await Promise.all(Array.from({ length: PARALLEL }, worker));
  }

  useEffect(() => () => void generation.current++, []);

  async function save(hit) {
    try {
      const r = await api.post("/api/recipes/import", { url: hit.url });
      setPreviews((s) => ({ ...s, [hit.url]: { ...s[hit.url], saved_id: r.id } }));
      reload("recipes");
      toast("Receptet är sparat.", "ok");
    } catch (e) {
      toast(e.message);
    }
  }

  const toggle = (name) => setPicked(picked.includes(name) ? picked.filter((n) => n !== name) : [...picked, name]);

  return (
    <section className="ica">
      <header className="recipe-head">
        <button className="icon-btn" onClick={() => navigate("/kok/recept")} aria-label="Tillbaka">
          <BackIcon />
        </button>
        <h1 className="grow">Sök recept på ICA</h1>
      </header>
      {chips.length > 0 && (
        <div className="frequent ica-chips" aria-label="Det här finns hemma">
          {chips.map((i) => (
            <button key={i.id} className="freq" aria-pressed={picked.includes(i.name)} onClick={() => toggle(i.name)}>
              {i.name}
            </button>
          ))}
        </div>
      )}
      <div className="ica-search-row">
        <div className="grow">
          <KioskInput value={text} onChange={setText} onSubmit={search} placeholder="Sök recept" maxLength={60} />
        </div>
        <button className="btn btn-primary" onClick={search} disabled={!query || busy}>Sök</button>
      </div>
      {error && <p className="error">{error}</p>}
      {busy && <p className="hint">Söker…</p>}
      {results && results.length === 0 && <p className="hint">Hittade inga recept. Prova andra ord.</p>}
      {results && (
        <div className="ica-list">
          {results.map((hit) => {
            const p = previews[hit.url];
            // The recipe page itself (read for "har X av Y") has the real title and picture;
            // the search page often only has a generic placeholder.
            const title = (p && !p.error && p.title) || hit.title || (p ? "Recept" : "Hämtar…");
            const image = (p && !p.error && p.image) || hit.image;
            return (
              <div key={hit.url} className="ica-card recipe-card">
                <span className="recipe-thumb">
                  {image && <img key={image} src={image} alt="" loading="lazy" referrerPolicy="no-referrer" />}
                </span>
                <span className="recipe-card-main">
                  <span className="recipe-card-title">{title}</span>
                  <span className={`recipe-have${p && !p.error && p.have === p.total ? " is-ok" : ""}`}>
                    {!p ? "Kollar…" : p.error ? "Kunde inte läsa receptet" : `har ${p.have} av ${p.total}`}
                    {p?.minutes ? ` · ${p.minutes} min` : ""}
                  </span>
                  {p?.missing?.length > 0 && <span className="hint">Saknar {p.missing.slice(0, 3).join(", ")}</span>}
                </span>
                {p?.saved_id ? (
                  <button className="btn" onClick={() => navigate(`/kok/recept/${p.saved_id}`)}>Öppna</button>
                ) : (
                  <button className="btn btn-primary" onClick={() => save(hit)} disabled={p?.error}>Spara</button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
