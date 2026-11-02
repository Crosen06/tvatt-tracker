import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api.js";
import { toast } from "../lib/store.js";
import Sheet from "./Sheet.jsx";

export const LEARN_TARGET = 24;
const MAX_TRIES = 48;
const EVERY_MS = 400;
const HINT_AFTER = 5; // tries in a row without an item in the box

// Takes pictures of an item while it is turned in the guide box; the live picture shows its outline.
export default function LearnSheet({ item, onClose }) {
  const [saved, setSaved] = useState(0);
  const [missing, setMissing] = useState(0);
  const [error, setError] = useState(null);
  const [streamKey] = useState(() => Date.now());
  const stopped = useRef(false);

  useEffect(() => {
    stopped.current = false;
    let count = 0;
    let misses = 0;
    (async () => {
      for (let tries = 0; tries < MAX_TRIES && count < LEARN_TARGET && !stopped.current; tries++) {
        try {
          const r = await api.post("/api/vision/capture", { item_id: item.id });
          if (r.saved) {
            count += 1;
            setSaved(count);
          }
          misses = r.found === false ? misses + 1 : 0;
          setMissing(misses);
        } catch (e) {
          setError(e.message);
          return;
        }
        if (count < LEARN_TARGET) await new Promise((res) => setTimeout(res, EVERY_MS));
      }
      if (stopped.current) return;
      toast(count ? `Lärde in ${count} ${count === 1 ? "bild" : "bilder"} av ${item.name}` : `Fick inga nya bilder av ${item.name}`, count ? "ok" : "error");
      onClose();
    })();
    return () => {
      stopped.current = true;
    };
  }, [item.id]);

  return (
    <Sheet title={`Lär in ${item.name}`} onClose={onClose} actions={<button className="btn btn-ghost" onClick={onClose}>{error ? "Stäng" : "Avbryt"}</button>}>
      {error ? (
        <p className="error">{error}</p>
      ) : (
        <div className="learn">
          <div className="scan-preview learn-preview">
            <img src={`/api/scan/stream?k=${streamKey}`} alt="Kamerabild" />
          </div>
          <div className="learn-side">
            <p className="scan-idle-title">Håll varan i rutan och vrid den långsamt – visa fram, bak och sidor</p>
            <div className="learn-bar" role="progressbar" aria-valuemin={0} aria-valuemax={LEARN_TARGET} aria-valuenow={saved}>
              <span style={{ width: `${(saved / LEARN_TARGET) * 100}%` }} />
            </div>
            <p className="hint">{saved} av {LEARN_TARGET} bilder</p>
            {missing >= HINT_AFTER && <p className="learn-hint">Håll varan i rutan</p>}
          </div>
        </div>
      )}
    </Sheet>
  );
}
