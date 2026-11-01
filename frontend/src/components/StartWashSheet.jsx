import { useState } from "react";
import { api } from "../lib/api.js";
import { careLabel, colorInfo, programAllowed, spinLabel, tempLabel } from "../lib/labels.js";
import { reload, toast, useStore } from "../lib/store.js";

export default function StartWashSheet({ group, onClose }) {
  const { programs } = useStore();
  const [programId, setProgramId] = useState(group.program_id);
  const [busy, setBusy] = useState(false);
  const color = colorInfo(group.color);

  async function start() {
    setBusy(true);
    try {
      await api.post("/api/washes", { program_id: programId, garment_ids: group.item_ids, temp: group.temp, spin: group.spin });
      reload("wash", "garments", "suggestions");
      toast("Tvätten är igång.", "ok");
      onClose();
    } catch (e) {
      toast(e.message);
      setBusy(false);
    }
  }

  return (
    <div className="scrim" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title" onClick={(e) => e.stopPropagation()}>
        <div className="row">
          <h2 id="sheet-title" className="grow">
            Välj program för {color.label.toLowerCase()} {tempLabel(group.temp)}
          </h2>
          <span className="chip">{spinLabel(group.spin)}</span>
        </div>
        <div className="program-list" role="radiogroup" aria-label="Tvättprogram">
          {programs.map((p) => {
            const tooHot = p.temp > group.temp;
            const tooHarsh = !programAllowed(group.care, p.care);
            const otherCare = p.care !== group.care;
            return (
              <button
                key={p.id}
                className="program"
                role="radio"
                aria-checked={programId === p.id}
                disabled={tooHot || tooHarsh}
                onClick={() => setProgramId(p.id)}
              >
                <span className="program-name">{p.name}</span>
                <span className="program-meta">
                  {p.duration_min} min
                  {p.id === group.program_id && <b> · föreslaget</b>}
                  {tooHot && ` · för varmt, plaggen tål ${tempLabel(group.temp)}`}
                  {!tooHot && tooHarsh && ` · för hårt för ${careLabel(group.care).toLowerCase()}`}
                  {!tooHot && !tooHarsh && otherCare && ` · gjort för ${careLabel(p.care).toLowerCase()}`}
                </span>
              </button>
            );
          })}
        </div>
        <div className="sheet-actions">
          <button className="btn btn-ghost" onClick={onClose}>
            Avbryt
          </button>
          <button className="btn btn-primary" disabled={!programId || busy} onClick={start}>
            {busy ? "Startar…" : "Starta tvätt"}
          </button>
        </div>
      </div>
    </div>
  );
}
