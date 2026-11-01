import { navigate } from "../lib/router.js";

export function haveLine(ev) {
  const missing = [...ev.missing, ...ev.unknown].map((m) => m.name);
  if (ev.total > 0 && missing.length === 0) return { ok: true, text: "Allt finns hemma" };
  if (ev.total === 0) return { ok: false, text: "Inga ingredienser" };
  const shown = missing.slice(0, 3).join(", ") + (missing.length > 3 ? " …" : "");
  return { ok: false, text: `Saknar ${missing.length}: ${shown}` };
}

export default function RecipeCard({ recipe }) {
  const line = haveLine(recipe.eval);
  return (
    <button className="recipe-card" onClick={() => navigate(`/kok/recept/${recipe.id}`)}>
      <span className="recipe-thumb">{recipe.thumb_url && <img src={recipe.thumb_url} alt="" loading="lazy" />}</span>
      <span className="recipe-card-main">
        <span className="recipe-card-title">{recipe.title}</span>
        <span className={`recipe-have${line.ok ? " is-ok" : ""}`}>{line.text}</span>
        <span className="hint">
          {[recipe.minutes && `${recipe.minutes} min`, recipe.source === "ica" && "ICA"].filter(Boolean).join(" · ")}
        </span>
      </span>
    </button>
  );
}
