import { useState } from "react";
import { plural } from "../lib/labels.js";
import { useStore } from "../lib/store.js";
import EmptyState from "./EmptyState.jsx";
import { BasketIcon } from "./Icons.jsx";
import PickMode from "./PickMode.jsx";
import RunningWash from "./RunningWash.jsx";
import StartWashSheet from "./StartWashSheet.jsx";
import SuggestionCard from "./SuggestionCard.jsx";

export default function WashTab() {
  const { garments, suggestions, people, wash, serverOffsetMs } = useStore();
  const [mode, setMode] = useState("suggest");
  const [sheet, setSheet] = useState(null);
  const basket = garments.filter((g) => g.in_basket && !g.in_wash);
  const byId = Object.fromEntries(garments.map((g) => [g.id, g]));
  const busy = Boolean(wash);

  return (
    <section>
      {wash && <RunningWash wash={wash} offset={serverOffsetMs} people={people} />}
      <div className="wash-head">
        <div className="segmented" role="tablist">
          <button role="tab" aria-selected={mode === "suggest"} onClick={() => setMode("suggest")}>
            Förslag
          </button>
          <button role="tab" aria-selected={mode === "pick"} onClick={() => setMode("pick")}>
            Välj själv
          </button>
        </div>
        <p className="hint">
          {busy ? "Maskinen är upptagen. " : ""}
          {plural(basket.length, "plagg", "plagg")} i tvättkorgen
        </p>
      </div>
      {basket.length === 0 ? (
        <EmptyState icon={<BasketIcon width={40} height={40} />} title="Tvättkorgen är tom">
          När någon trycker i sina plagg dyker tvättförslagen upp här.
        </EmptyState>
      ) : mode === "suggest" ? (
        <div className="suggestions">
          {suggestions.map((g) => (
            <SuggestionCard key={g.key} group={g} byId={byId} people={people} busy={busy} onStart={() => setSheet(g)} />
          ))}
        </div>
      ) : (
        <PickMode basket={basket} busy={busy} onStart={setSheet} />
      )}
      {sheet && <StartWashSheet group={sheet} onClose={() => setSheet(null)} />}
    </section>
  );
}
