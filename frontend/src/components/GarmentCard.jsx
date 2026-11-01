import { colorInfo, tempLabel } from "../lib/labels.js";
import { BasketIcon } from "./Icons.jsx";

export default function GarmentCard({ garment, accent, onToggle }) {
  const { in_basket, in_wash } = garment;
  const color = colorInfo(garment.color);
  const state = in_wash ? "I maskinen" : in_basket ? "I tvättkorgen" : "Inte i tvättkorgen";
  return (
    <button
      type="button"
      className={`garment${in_basket ? " is-in" : ""}${in_wash ? " is-washing" : ""}`}
      style={{ "--accent": accent }}
      onClick={() => !in_wash && onToggle(garment)}
      aria-pressed={in_basket}
      aria-label={`${garment.name}, ${state}`}
      disabled={in_wash}
    >
      <span className="garment-photo">
        {garment.thumb_url ? <img src={garment.thumb_url} alt="" loading="lazy" draggable="false" /> : <span className="garment-nophoto" />}
        {in_basket && !in_wash && (
          <span className="garment-badge">
            <BasketIcon width={18} height={18} />
          </span>
        )}
        {in_wash && <span className="garment-washing">I maskinen</span>}
      </span>
      <span className="garment-name">{garment.name}</span>
      <span className="garment-tags">
        <span className="swatch" style={{ background: color.swatch }} />
        {tempLabel(garment.max_temp)}
      </span>
    </button>
  );
}
