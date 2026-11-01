import { useState } from "react";
import { api } from "../lib/api.js";
import { reload, toast, useStore } from "../lib/store.js";
import { remainingMs, useNow } from "../lib/time.js";
import { DryerOffIcon } from "./Icons.jsx";
import Porthole from "./Porthole.jsx";
import Thumbs from "./Thumbs.jsx";

export default function DoneOverlay() {
  const { wash, serverOffsetMs, people } = useStore();
  const now = useNow(1000);
  const [busy, setBusy] = useState(false);
  if (!wash || remainingMs(wash, serverOffsetMs, now) > 0) return null;

  const noDry = wash.items.filter((g) => !g.tumble_dry).map((g) => g.name);

  async function finish() {
    setBusy(true);
    try {
      await api.post(`/api/washes/${wash.id}/finish`);
      reload("wash", "garments");
    } catch (e) {
      toast(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="done" role="alertdialog" aria-labelledby="done-title">
      <div className="done-inner">
        <Porthole size={128} progress={1} done />
        <h1 id="done-title">Tvätten är klar!</h1>
        <p className="done-sub">{wash.name}</p>
        <Thumbs items={wash.items} people={people} max={14} />
        {noDry.length > 0 && (
          <p className="suggestion-note">
            <DryerOffIcon width={18} height={18} />
            Tål inte torktumlare: {noDry.join(", ")}
          </p>
        )}
        <button className="btn btn-primary done-btn" onClick={finish} disabled={busy}>
          Tömt maskinen
        </button>
      </div>
    </div>
  );
}
