import { careLabel, colorInfo, plural, spinLabel, tempLabel } from "../lib/labels.js";
import { DryerOffIcon } from "./Icons.jsx";
import Thumbs from "./Thumbs.jsx";

export function noDryText(ids, byId) {
  const names = ids.map((id) => byId[id]?.name).filter(Boolean);
  if (!names.length) return null;
  return `Tål inte torktumlare: ${names.join(", ")}`;
}

export default function SuggestionCard({ group, byId, people, busy, onStart }) {
  const color = colorInfo(group.color);
  const items = group.item_ids.map((id) => byId[id]).filter(Boolean);
  const noDry = noDryText(group.no_dry_ids, byId);
  return (
    <article className="suggestion" style={{ "--swatch": color.swatch }}>
      <span className="suggestion-stripe" />
      <div className="suggestion-body">
        <div className="suggestion-title">
          <h3>
            {color.label} {tempLabel(group.temp)}
          </h3>
          <span className="hint">{plural(items.length, "plagg", "plagg")}</span>
        </div>
        <div className="chips">
          <span className="chip">{careLabel(group.care)}</span>
          <span className="chip">{spinLabel(group.spin)}</span>
        </div>
        <Thumbs items={items} people={people} />
        {noDry && (
          <p className="suggestion-note">
            <DryerOffIcon width={18} height={18} />
            {noDry}
          </p>
        )}
      </div>
      <button className="btn btn-primary" onClick={onStart} disabled={busy}>
        Starta tvätt
      </button>
    </article>
  );
}
