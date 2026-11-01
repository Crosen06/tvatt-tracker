import { useState } from "react";
import { api } from "../lib/api.js";
import { colorInfo, spinLabel, tempLabel } from "../lib/labels.js";
import { reload, toast } from "../lib/store.js";
import { formatClock, formatRemaining, progress, remainingMs, useNow } from "../lib/time.js";
import Porthole from "./Porthole.jsx";
import Thumbs from "./Thumbs.jsx";

export default function RunningWash({ wash, offset, people }) {
  const now = useNow(1000);
  const [confirm, setConfirm] = useState(false);
  const left = remainingMs(wash, offset, now);
  const endsAt = Date.parse(wash.ends_at) - offset;
  const color = colorInfo(wash.items[0]?.color);

  async function cancel() {
    try {
      await api.post(`/api/washes/${wash.id}/cancel`);
      reload("wash", "garments");
    } catch (e) {
      toast(e.message);
    }
  }

  return (
    <section className="running" aria-label="Pågående tvätt">
      <Porthole size={116} progress={progress(wash, offset, now)} running={left > 0} done={left <= 0} />
      <div className="running-info">
        <div className="row">
          <span className="swatch" style={{ background: color.swatch }} />
          <h2>{wash.name}</h2>
        </div>
        <p className="running-time">{formatRemaining(left)}</p>
        <div className="chips">
          <span className="hint">Klar ungefär {formatClock(endsAt)}</span>
          <span className="chip">{tempLabel(wash.temp)}</span>
          <span className="chip">{spinLabel(wash.spin)}</span>
        </div>
        <Thumbs items={wash.items} people={people} max={12} />
      </div>
      <div className="running-actions">
        {confirm ? (
          <>
            <span className="hint">Plaggen ligger kvar i korgen.</span>
            <button className="btn btn-danger" onClick={cancel}>
              Avbryt tvätten
            </button>
            <button className="btn btn-ghost" onClick={() => setConfirm(false)}>
              Fortsätt tvätta
            </button>
          </>
        ) : (
          <button className="btn btn-ghost" onClick={() => setConfirm(true)}>
            Avbryt tvätt
          </button>
        )}
      </div>
    </section>
  );
}
