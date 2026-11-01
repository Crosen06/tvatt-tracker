import { useState } from "react";
import { api } from "../lib/api.js";
import { getState, reload, toast } from "../lib/store.js";
import { addItemToList, entryForItem, removeFromList, updateItem } from "./actions.js";
import ItemPickerSheet from "./ItemPickerSheet.jsx";
import { statusLabel } from "./labels.js";
import NewItemSheet from "./NewItemSheet.jsx";

const fresh = (item) => getState().items.find((i) => i.id === item.id) || item;

function KnownItem({ item, onDone }) {
  async function intoPantry() {
    const it = fresh(item);
    const ok = await updateItem(it, it.counted ? { count_delta: 1 } : { status: "in_stock" });
    if (!ok) return;
    const entry = entryForItem(it.id);
    if (entry) await removeFromList(entry.id);
    toast(`${it.name} finns nu i skafferiet`, "ok");
    onDone();
  }
  async function toList() {
    const it = fresh(item);
    if (it.on_list) toast(`${it.name} står redan på inköpslistan`, "ok");
    else {
      await addItemToList(it);
      toast(`${it.name} lades på inköpslistan`, "ok");
    }
    onDone();
  }
  async function out() {
    const it = fresh(item);
    const wasOut = it.status === "out";
    const updated = await updateItem(it, { status: "out" });
    if (!updated) return;
    // Going from home to out puts it on the list (with Ångra). Already out but not listed: list it now.
    if (wasOut && !updated.on_list && getState().settings.auto_list !== false) {
      await addItemToList(updated);
      toast(`${it.name} lades på inköpslistan`, "ok");
    } else if (updated.on_list === it.on_list) {
      toast(`${it.name} är markerad som slut`, "ok");
    }
    onDone();
  }
  return (
    <div className="scan-result">
      <h2>{item.name}</h2>
      <p className="hint">{item.category} · {statusLabel(fresh(item))}</p>
      <div className="scan-actions">
        <button className="btn btn-primary" onClick={intoPantry}>In i skafferiet</button>
        <button className="btn" onClick={toList}>På inköpslistan</button>
        <button className="btn" onClick={out}>Slut</button>
      </div>
    </div>
  );
}

function UnknownItem({ result, onResult }) {
  const [creating, setCreating] = useState(false);
  const [searching, setSearching] = useState(false);
  const product = result.product;

  async function link(itemId) {
    try {
      const item = await api.post("/api/barcodes", { code: result.code, item_id: itemId, product_name: product?.name ?? null });
      reload("items");
      onResult({ ...result, item });
    } catch (e) {
      toast(e.message);
    }
  }

  return (
    <div className="scan-result">
      <h2>{product ? product.name : "Okänd vara"}</h2>
      <p className="hint">
        {product
          ? "Ny streckkod. Vilken vara är det här?"
          : result.lookup_failed
            ? "Kunde inte slå upp koden just nu. Välj vilken vara det är."
            : "Produkten finns inte i Open Food Facts – välj vara eller skriv in ett namn."}
      </p>
      {result.candidates.length > 0 && (
        <div className="frequent">
          {result.candidates.map((c) => (
            <button key={c.id} className="freq" onClick={() => link(c.id)}>{c.name}</button>
          ))}
        </div>
      )}
      <div className="scan-actions">
        <button className="btn btn-primary" onClick={() => setCreating(true)}>Ny vara</button>
        <button className="btn" onClick={() => setSearching(true)}>Sök vara</button>
      </div>
      <p className="hint scan-code">Kod {result.code}</p>
      {creating && (
        <NewItemSheet
          initialName={product?.short_name || ""}
          initialCategory={product?.category || "Skafferi"}
          status="out"
          onClose={() => setCreating(false)}
          onCreated={(item) => link(item.id)}
        />
      )}
      {searching && (
        <ItemPickerSheet
          title="Vilken vara är det?"
          onClose={() => setSearching(false)}
          onPick={(i) => {
            setSearching(false);
            link(i.id);
          }}
        />
      )}
    </div>
  );
}

export default function ScanResult({ result, onResult, onDone }) {
  return result.item ? <KnownItem item={result.item} onDone={onDone} /> : <UnknownItem result={result} onResult={onResult} />;
}
