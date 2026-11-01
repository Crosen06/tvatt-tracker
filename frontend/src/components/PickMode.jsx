import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";
import { careLabel, colorInfo, plural, spinLabel, tempLabel } from "../lib/labels.js";
import { CheckIcon } from "./Icons.jsx";

export default function PickMode({ basket, busy, onStart }) {
  const [selected, setSelected] = useState([]);
  const [result, setResult] = useState(null);
  const seq = useRef(0);

  // Drop selections that left the basket (e.g. someone else started a wash).
  const basketIds = basket.map((g) => g.id).join(",");
  useEffect(() => {
    setSelected((sel) => sel.filter((id) => basket.some((g) => g.id === id)));
  }, [basketIds]);

  const key = selected.join(",");
  useEffect(() => {
    if (!selected.length) {
      setResult(null);
      return;
    }
    const n = ++seq.current;
    api.post("/api/suggestions/check", { garment_ids: selected }).then(
      (r) => n === seq.current && setResult({ ...r, key }),
      () => n === seq.current && setResult(null),
    );
  }, [key, basketIds]);

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  // Only trust an answer that belongs to the current selection.
  const current = result && result.key === key ? result : null;
  const checking = selected.length > 0 && !current;
  const compatible = new Set(current?.compatible_ids || []);
  const group = current?.group;

  return (
    <>
      <div className="pick-grid">
        {basket.map((g) => {
          const isSel = selected.includes(g.id);
          const cls = isSel ? " is-selected" : compatible.has(g.id) ? " is-compatible" : selected.length ? " is-faded" : "";
          return (
            <button key={g.id} className={`pick${cls}`} onClick={() => toggle(g.id)} aria-pressed={isSel} aria-label={g.name}>
              {g.thumb_url && <img src={g.thumb_url} alt="" draggable="false" />}
              {isSel && (
                <span className="pick-check">
                  <CheckIcon width={16} height={16} />
                </span>
              )}
            </button>
          );
        })}
      </div>
      <div className="pick-panel">
        {!selected.length && <p className="hint">Tryck på plaggen du vill tvätta. De som passar ihop markeras.</p>}
        {checking && <p className="hint">Kollar vad som passar ihop…</p>}
        {current?.conflicts?.length > 0 && (
          <div className="conflicts">
            {current.conflicts.map((c) => (
              <p key={c}>{c}</p>
            ))}
          </div>
        )}
        {group && (
          <>
            <div className="chips">
              <span className="chip chip-strong">
                <span className="swatch" style={{ background: colorInfo(group.color).swatch }} />
                {colorInfo(group.color).label} {tempLabel(group.temp)}
              </span>
              <span className="chip">{careLabel(group.care)}</span>
              <span className="chip">{spinLabel(group.spin)}</span>
              {compatible.size > 0 && <span className="hint">{plural(compatible.size, "plagg till passar", "plagg till passar")}</span>}
            </div>
            <div className="row">
              {compatible.size > 0 && (
                <button className="btn" onClick={() => setSelected([...selected, ...compatible])}>
                  Ta med alla som passar
                </button>
              )}
              <button className="btn btn-primary" disabled={busy} onClick={() => onStart(group)}>
                Starta tvätt ({selected.length})
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
