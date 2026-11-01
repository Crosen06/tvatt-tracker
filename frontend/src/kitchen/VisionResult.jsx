import { useState } from "react";
import { api } from "../lib/api.js";
import ItemPickerSheet from "./ItemPickerSheet.jsx";
import NewItemSheet from "./NewItemSheet.jsx";
import { KnownItem } from "./ScanResult.jsx";

// What the camera picture looked like: the best item's card (sure), or a choice (maybe / none).
// Choosing or acting on an item confirms it, which teaches the app this picture.
export default function VisionResult({ result, onDone, onLearn }) {
  const { token, decision, matches } = result;
  const [chosen, setChosen] = useState(null);
  const [searching, setSearching] = useState(false);
  const [creating, setCreating] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  function confirm(itemId) {
    if (confirmed) return;
    setConfirmed(true);
    api.post("/api/vision/confirm", { token, item_id: itemId }).catch(() => {});
  }
  function choose(item) {
    setSearching(false);
    confirm(item.id);
    setChosen(item);
  }

  const pickers = (
    <>
      {searching && <ItemPickerSheet title="Vilken vara är det?" allowNew onClose={() => setSearching(false)} onPick={choose} />}
      {creating && <NewItemSheet status="out" onClose={() => setCreating(false)} onCreated={choose} />}
    </>
  );

  if (chosen) return <KnownItem item={chosen} onDone={onDone} onLearn={onLearn} />;

  if (decision === "sure" && matches.length) {
    const best = matches[0].item;
    const others = matches.slice(1);
    return (
      <>
        <KnownItem
          item={best}
          onDone={onDone}
          onLearn={onLearn}
          onAction={() => confirm(best.id)}
          note="Känd igen på bilden"
          extra={
            <div className="vision-others">
              {others.length > 0 && <span className="vision-or">Eller:</span>}
              {others.map((m) => (
                <button key={m.item.id} className="freq" onClick={() => choose(m.item)}>{m.item.name}</button>
              ))}
              <button className="freq" onClick={() => setSearching(true)}>Fel vara?</button>
            </div>
          }
        />
        {pickers}
      </>
    );
  }

  return (
    <div className="scan-result">
      <h2>{matches.length ? "Är det någon av de här?" : "Känner inte igen varan"}</h2>
      <p className="hint">
        {matches.length ? "Tryck på rätt vara." : "Sök upp varan eller skapa en ny."}
      </p>
      {matches.length > 0 && (
        <div className="frequent">
          {matches.map((m) => (
            <button key={m.item.id} className="freq" onClick={() => choose(m.item)}>{m.item.name}</button>
          ))}
        </div>
      )}
      <div className="scan-actions">
        <button className="btn" onClick={() => setSearching(true)}>Sök vara</button>
        <button className="btn" onClick={() => setCreating(true)}>Ny vara</button>
        <button className="btn btn-ghost" onClick={onDone}>Ingen av dem</button>
      </div>
      {pickers}
    </div>
  );
}
