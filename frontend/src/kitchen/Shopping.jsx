import { useState } from "react";
import { useStore } from "../lib/store.js";
import { addTextToList, removeFromList, toggleOnList } from "./actions.js";
import KioskInput from "./KioskInput.jsx";
import { capitalize } from "./labels.js";
import Sheet from "./Sheet.jsx";
import UnpackSheet from "./UnpackSheet.jsx";

function TextEntrySheet({ onClose }) {
  const [text, setText] = useState("");
  async function add() {
    if (await addTextToList(capitalize(text))) onClose();
  }
  return (
    <Sheet
      title="Lägg till på listan"
      full
      onClose={onClose}
      actions={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Avbryt</button>
          <button className="btn btn-primary" onClick={add} disabled={!text.trim()}>Lägg till</button>
        </>
      }
    >
      <KioskInput value={text} onChange={setText} onSubmit={add} placeholder="Vad behöver ni köpa?" keyboardOpen autoFocus />
    </Sheet>
  );
}

export default function Shopping() {
  const { shopping } = useStore();
  const [typing, setTyping] = useState(false);
  const [unpacking, setUnpacking] = useState(false);
  const { entries, frequent } = shopping;
  const onList = new Set(entries.map((e) => e.item_id).filter(Boolean));

  return (
    <section className="shopping">
      <div className="card shop-card">
        <div className="row">
          <h2 className="grow">Inköpslista <span className="count">{entries.length}</span></h2>
        </div>
        {entries.length === 0 ? (
          <p className="hint shop-empty">Listan är tom. Tryck på det ni behöver under Ofta köpta, eller markera varor som slut i skafferiet.</p>
        ) : (
          <ul className="shop-list">
            {entries.map((e) => (
              <li key={e.id} className="shop-row">
                <span className="shop-row-main">
                  <span className="shop-row-text">{e.text}</span>
                  {e.note && <span className="hint">{e.note}</span>}
                </span>
                <button className="icon-btn" aria-label={`Ta bort ${e.text}`} onClick={() => removeFromList(e.id)}>
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="shop-actions">
          <button className="btn" onClick={() => setTyping(true)}>Annat…</button>
          <button className="btn btn-primary" onClick={() => setUnpacking(true)} disabled={entries.length === 0}>
            Packa upp
          </button>
        </div>
      </div>
      <div className="card frequent-card">
        <h2>Ofta köpta</h2>
        {frequent.length === 0 ? (
          <p className="hint">Det ni lägger på listan hamnar här, så ni kan lägga till det med ett tryck nästa gång.</p>
        ) : (
          <div className="frequent">
            {frequent.map((i) => (
              <button key={i.id} className="freq" aria-pressed={onList.has(i.id)} onClick={() => toggleOnList(i)}>
                {i.name}
              </button>
            ))}
          </div>
        )}
      </div>
      {typing && <TextEntrySheet onClose={() => setTyping(false)} />}
      {unpacking && <UnpackSheet entries={entries} onClose={() => setUnpacking(false)} />}
    </section>
  );
}
